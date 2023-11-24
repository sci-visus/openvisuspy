
import os,sys,json,logging,shutil,glob,time,copy
from datetime import datetime
import numpy as np
import h5py

# python3 -m pip install nexusformat
from nexusformat.nexus import NXfield, NXlinkfield,NXdata,nxsave,nxload
from nexusformat.nexus.tree import NX_CONFIG 
NX_CONFIG['memory']=32000  # alllow data to be 32GB

import OpenVisus as ov
from openvisuspy import LoadJSON

logger = logging.getLogger("nsdf-convert")


# //////////////////////////////////////////////////////////////////
def ReadImage(filename):
	ext=os.path.splitext(filename)[1]
	if ext==".cbf":
		import fabio
		return fabio.open(filename).data
	else:
		from skimage import io
		return io.imread(filename)


# //////////////////////////////////////////////////////////////////
def TraverseNexus(cur,nrec=0):
	yield (nrec,cur)

	try:
		childs=cur.entries.items()
	except:
		return

	for _k, child in childs: 
		yield from TraverseNexus(child,nrec+1)


def PrintNexus(cur):
	for depth, node in TraverseNexus(cur):
		if isinstance(node,NXfield) and not isinstance(node,NXlinkfield) and(len(node.shape)==3 or len(node.shape)==4):
			logger.info("   "*(depth+0) +  f"{node.nxname}::{type(node)} shape={node.shape} dtype={node.dtype} ***********************************")
		else:
			logger.info("   "*(depth+0) + f"{node.nxname}::{type(node)}")
		for k,v in node.attrs.items():
			logger.info("  "*(depth+1) + f"@{k} = {v}")

def SaveNexus(filename,dst):
		t1=time.time()
		logger.info(f"Creating streamable version {filename}")
		if os.path.isfile(filename): os.remove(filename)			
		nxsave(filename, dst , mode='w')
		logger.info(f"DoConvert::run streamable={filename} reduced-size={os.path.getsize(filename):,}")

# ///////////////////////////////////////////////////////////////////
def CopyNexus(src, dst, extra_attrs={}):

	ret=[]

	if isinstance(src,NXfield) and not isinstance(src,NXlinkfield):

		src_field=src;src_parent=src_field.nxgroup
		dst_field=dst;dst_parent=dst_field.nxgroup

		if len(src_field.shape)==3 or len(src_field.shape)==4:

			# replace any 'big' field with something virtually empty
			# TODO: read nexus by slabs
			t1=time.time()
			logger.info(f"Reading Nexus field name={src_field.nxname} dtype={src_field.dtype} shape={src_field.shape} ...")
			data = src_field.nxdata
			logger.info(f"Read Nexus field in {time.time()-t1} seconds")

			# e.g. 1x1441x676x2048 -> 1x1441x676x2048
			if len(data.shape)==4:
				assert(data.shape[0]==1)
				data=data[0,:,:,:]

			if hasattr(src_parent,"attr") and "axes" in src_parent.attrs:
				idx_axis=[]
				idx_physic_box=[]
				axis=[src_parent[it] for it in src_parent.attrs["axes"]]
				for it in axis:
					idx_physic_box=[str(it.nxdata[0]),str(it.nxdata[-1])] + idx_physic_box
					idx_axis=[it.nxname] +idx_axis
				idx_axis=" ".join(idx_axis)
				logger.info(f"Found axis={idx_axis} idx_physic_box={idx_physic_box}")
				idx_physic_box=" ".join(idx_physic_box)
			else:
				idx_axis="X Y Z"
				D,H,W=data.shape
				idx_physic_box=f"0 {W} 0 {H} 0 {D}"

			idx_physic_box=ov.BoxNd.fromString(idx_physic_box)
			
			# this is the version without any data
			dst_field=NXfield(value=None, shape=src_field.shape, dtype=src_field.dtype)
			
			dst_parent[src_field.nxname]=dst_field

			for _k,_v in extra_attrs.items():
				dst_field.attrs[_k]=repr(_v)

			ret.append((data, idx_axis, idx_physic_box))

		else:

			# deepcopy does not seem to copy nxdata (maybe for the lazy evalation?)
			dst_field.nxdata=copy.copy(src_field.nxdata)
	
	# recurse
	try:
		childs=src.entries
	except:
		childs=[]

	for name in childs:
			src_child=src.entries[name]
			dst_child=dst.entries[name]
			ret = ret + CopyNexus(src_child, dst_child, extra_attrs)

	return ret


# ///////////////////////////////////////////////////////////////////
def NextPowerOf2(x):  
	return 1 if x == 0 else 2**(x - 1).bit_length()

# ///////////////////////////////////////////////////////////////////
# new bitmask VZZZZZ.... so that the access along the z is better
# assert(len(GuessBitmask(366,2048,2048),"V(2*)(.*)")==len("V0120120120120120120120120120101"))
def GuessBitmask(dims, bitmask="V(.*)"):
	
	dims=[NextPowerOf2(it) for it in dims]

	assert(bitmask[0]=="V")
	bitmask=bitmask[1:]

	ret="V"

	# access will be on the z
	if bitmask[0:4]=="(2*)":
		while dims[2]!=1: 
			ret+="2"
			dims[2]>>=1
		bitmask=bitmask[4:]

	# complete the bitmask this is the openvisus version
	assert(bitmask)=="(.*)"
	while dims != [1,1,1]:
			if dims[0]>1: ret+="0";dims[0]>>=1
			if dims[1]>1: ret+="1";dims[1]>>=1
			if dims[2]>1: ret+="2";dims[2]>>=1;

	return ret

# ///////////////////////////////////////////////////////////////////
def ConvertData(specs):

	T1=time.time()

	src         = specs["src"]
	dst         = specs["dst"]
	compression = specs.get("compression","zip")
	arco        = specs.get("arco","8mb")
	c_size      = os.path.getsize(src) if os.path.isfile(src) else 0

	logger.info(f"src={src} dst={dst} compression={compression} arco={arco} c_size={c_size} start...")

	# NOTE: this is dangerous but I have to do it: I need to remove all openvisus files in case I crashed in a middle of compression
	# e.g assuyming /mnt/data1/nsdf/tmp/near-field-scrgiorgio-20230912-01/visus.idx I need to clean up the parent directory
	# SO MAKE SURE you are using unique directories!	
	if True:
		data_dir=os.path.splitext(dst)[0]	
		logger.info(f" DANGEROUS but needed: removing any old data file from {data_dir}")
		shutil.rmtree(data_dir, ignore_errors=True)

	idx_axis,idx_physic_box=None,None

	extra_args={}

	logger.info(f"Loading src={src}...")

	t1=time.time()
	ext=os.path.splitext(src)[1]

	# ___________________________________________
	if ext in (".tif",".cbf") and "*" in src:
		filenames=list(sorted(glob.glob(src)))
		logger.info(f"Found {len(filenames)} files src={src} [{filenames[0]}..{filenames[-1]}]")
		assert(len(filenames))
		img = ReadImage(filenames[0])
		D,H,W=len(filenames),*img.shape
		data=np.zeros((D,H,W),dtype=img.dtype)
		for Z,filename in enumerate(filenames):
			data[Z,:,:]=ReadImage(filename)

	else:

		# single file case
		# allow glob if it ends up with a single file
		if "*" in src:
			v=list(glob.glob(src))
			if len(v)!=1: raise Exception(f"Got src={src} which is not a single file")
			src=v[0]

		# ___________________________________________
		if ext == ".npy":
			data=np.load(src)

		# ___________________________________________
		elif ext == ".h5":
			expression  = specs.get("expression","/imageseries/images") # how to reach the field
			logger.info(f"expression={expression}")

			f = h5py.File(src, 'r')

			data=f
			for it in expression.split("/")[1:]: data=data[it]

			t1=time.time()
			logger.info(f"Reading H5 data...")
			data=data[:,:,:]
			logger.info(f"Read H5 data in {time.time()-t1} seconds")

		# ___________________________________________
		elif ext ==".nxs":

			# allow glob if it ends up with a single file
			if "*" in src:
				v=list(glob.glob(src))
				if len(v)!=1: raise Exception(f"Got src={src} which is not a single file")
				src=v[0]

			

			if True:
				expression  = specs["expression"]
				logger.info(f"expression={expression}")

				f=nxload(src)

				field=f
				for it in expression.split("/")[1:]: field=field[it]

				# replace any 'big' field with something virtually empty
				# TODO: read nexus by slabs
				t1=time.time()
				logger.info(f"Reading Nexus field name={field.nxname} dtype={field.dtype} shape={field.shape} ...")
				data = field.nxdata
				logger.info(f"Read Nexus field in {time.time()-t1} seconds")

				# e.g. 1x1441x676x2048 -> 1x1441x676x2048
				if len(data.shape)==4:
					assert(data.shape[0]==1)
					data=data[0,:,:,:]

				parent=field.nxgroup
				if hasattr(parent,"attr") and "axes" in parent.attrs:
					axis=[parent[it] for it in parent.attrs["axes"]]
					idx_axis,idx_physic_box=[],[]
					for it in axis:
						idx_physic_box=[str(it.nxdata[0]),str(it.nxdata[-1])] + idx_physic_box
						idx_axis=[it.nxname] +idx_axis
					idx_axis=" ".join(idx_axis)
					logger.info(f"Found axis={idx_axis} idx_physic_box={idx_physic_box}")
					idx_physic_box=" ".join(idx_physic_box)
				else:
					idx_axis="X Y Z"
					D,H,W=data.shape
					idx_physic_box=f"0 {W} 0 {H} 0 {D}"
				idx_physic_box=ov.BoxNd.fromString(idx_physic_box)

			else:
				nexus_src=nxload(src)
				streamable=copy.deepcopy(nexus_src)
				found=CopyNexus(nexus_src,streamable,{"openvisus":dst})

				# TODO: not supporting multiple fields inside a nexus file

				if len(found)>1:
					logger.info(f"NEXUS Found two fields, talking the first one")
				assert(len(found))
				data, idx_axis, idx_physic_box=found[0]

				# TODO: with some nexus file I am unable to create shrinked streamable (probably related to NXlinkfield)
				if False:
					streamable.attrs["streamable"]=True # add an attribute to remember
					SaveNexus(os.path.splitext(dst)[0]+".nxs", streamable)

				# LocalFileToMetadata(metadata,streamable_nexus)

		# ___________________________________________
		else:
			raise Exception(f"Cannot handle src={src}")

	# why I am forcing it to be float32? I don't rememeber, maybe for openvisus/bokeh?
	data=data.astype(np.float32) 
	
	logger.info(f"Data loaded in {time.time() - t1} seconds shape={data.shape} dtype={data.dtype} nbytes={data.nbytes:,}")

	D,H,W=data.shape

	# example ofd bitmask with preference along Z "V(2*)(.*)"
	bitmask=specs.get("bitmask",None)
	if bitmask: 
		if "*" in bitmask:
			bitmask=GuessBitmask([W,H,D],bitmask)
		extra_args["bitmask"]= bitmask

	if idx_axis is None:
		idx_axis="X Y Z"

	if idx_physic_box is None:
		idx_physic_box=ov.BoxNd.fromString(f"0 {W} 0 {H} 0 {D}")

	# create idx
	if True:
		vmin,vmax=np.min(data),np.max(data)
		field = ov.Field.fromString(f"""DATA {str(data.dtype)} format(row_major) min({vmin}) max({vmax})""")

		db=ov.CreateIdx(
			url=dst, 
			dims=[W,H,D], 
			fields=[field], 
			compression="raw",  # first I write uncompressed
			arco=arco, 
			axis=idx_axis, 
			physic_box=idx_physic_box,
			**extra_args)

		# print(db.getDatasetBody().toString())
		logger.info(f"IDX file={dst} created shape={data.shape} dtype={data.dtype} nbytes={data.nbytes} vmin={vmin} vmax={vmax}")

	# write data
	if True:
		os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
		logger.info(f"Writing IDX data...")
		t1 = time.time()
		db.write(data, time=0)
		write_sec=time.time() - t1
		logger.info(f"Wrote IDX data in {write_sec} seconds")

	# compress data
	if compression and compression!="raw":
		t1 = time.time()
		logger.info(f"Compressing dataset to {compression}...")
		db.compressDataset([compression])
		logger.info(f"Compressed dataset to {compression} in {time.time()-t1} seconds")

	logger.info(f"src={src} dst={dst} compression={compression} arco={arco} DONE in {time.time()-T1} seconds")
	

