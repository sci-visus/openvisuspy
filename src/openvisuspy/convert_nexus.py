
import os ,sys, time, logging,shutil,copy
from datetime import datetime
import numpy as np
from nexusformat.nexus import * 
import OpenVisus as ov


# ////////////////////////////////////////////////////////////
class ConvertNexus:

	# constructor
	def __init__(self,src, dst, compression="raw",streamable=None, arco="modvisus"):
		self.src=src
		self.dst=dst
		self.streamable=streamable
		self.compression=compression
		self.num_bin_fields=0
		self.arco=arco

	@staticmethod
	def traverse(cur,nrec=0):
		yield (nrec,cur)

		try:
			childs=cur.entries.items()
		except:
			return

		for _k, child in childs: 
			yield from ConvertNexus.traverse(child,nrec+1)

	@staticmethod
	def print(cur):
		for depth, node in ConvertNexus.traverse(cur):
			if isinstance(node,NXfield) and not isinstance(node,NXlinkfield) and(len(node.shape)==3 or len(node.shape)==4):
				print("   "*(depth+0) +  f"{node.nxname}::{type(node)} shape={node.shape} dtype={node.dtype} ***********************************")
			else:
				print("   "*(depth+0) + f"{node.nxname}::{type(node)}")
			for k,v in node.attrs.items():
				print("  "*(depth+1) + f"@{k} = {v}")

	# run
	def run(self):
		print(f"ConvertNexus::run src={self.src} full-size={os.path.getsize(self.src):,}")
		src=nxload(self.src)
		dst=copy.deepcopy(src)
		dst.attrs["streamable"]=True
		self._convertNexusFieldsToOpenVisus(src, dst)

		if self.streamable:
			t1=time.time()
			print(f"Creating streamable version {self.streamable}")
			if os.path.isfile(self.streamable): os.remove(self.streamable)			
			nxsave(self.streamable, dst , mode='w')
			print(f"ConvertNexus::run streamable={self.streamable} reduced-size={os.path.getsize(self.streamable):,}")
		return dst
	
	# _convertNexusFieldsToOpenVisus
	def _convertNexusFieldsToOpenVisus(self, src, dst):

		if isinstance(src,NXfield) and not isinstance(src,NXlinkfield):

			src_field=src;src_parent=src_field.nxgroup
			dst_field=dst;dst_parent=dst_field.nxgroup

			if len(src_field.shape)==3 or len(src_field.shape)==4:

				# TODO: support more than once
				assert(self.num_bin_fields==0)

				# replace any 'big' field with something virtually empty
				# TODO: read nexus by slabs
				t1=time.time()
				print(f"Reading Nexus field name={src_field.nxname} dtype={src_field.dtype} shape={src_field.shape} ...")
				data = src_field.nxdata
				vmin,vmax=np.min(data),np.max(data)
				print(f"Read Nexus field in {time.time()-t1} seconds vmin={vmin} vmax={vmax}")

				# e.g. 1x1441x676x2048 -> 1x1441x676x2048
				if len(data.shape)==4:
					assert(data.shape[0]==1)
					data=data[0,:,:,:]

				t1=time.time()
				print(f"Creating IDX file {self.dst}")
				ov_field=ov.Field.fromString(f"""DATA {str(src_field.dtype)} format(row_major) min({vmin}) max({vmax})""")

				assert(isinstance(src_parent,NXdata))

				if "axes" in src_parent.attrs:
					idx_axis=[]
					idx_physic_box=[]
					axis=[src_parent[it] for it in src_parent.attrs["axes"]]
					for it in axis:
						idx_physic_box=[str(it.nxdata[0]),str(it.nxdata[-1])] + idx_physic_box
						idx_axis=[it.nxname] +idx_axis
					idx_axis=" ".join(idx_axis)
					print(f"Found axis={idx_axis} idx_physic_box={idx_physic_box}")
					idx_physic_box=" ".join(idx_physic_box)
				else:
					idx_axis="X Y Z"
					D,H,W=data.shape
					idx_physic_box=f"0 {W} 0 {H} 0 {D}"

				db=ov.CreateIdx(
					url=self.dst, 
					dims=list(reversed(data.shape)), 
					fields=[ov_field], 
					compression="raw",
					physic_box=ov.BoxNd.fromString(idx_physic_box),
					arco=self.arco,
					axis=idx_axis
				)

				t1=time.time()
				print(f"Writing IDX data...")
				db.write(data)
				print(f"Wrote IDX data in {time.time()-t1} seconds")

				if self.compression and self.compression!="raw":
					t1 = time.time()
					print(f"Compressing dataset compression={self.compression}...")
					db.compressDataset([self.compression])
					print(f"Compressed dataset to {self.compression} in {time.time()-t1} seconds")

				# this is the version without any data
				dst_field=NXfield(value=None, shape=src_field.shape, dtype=src_field.dtype)
				dst_field.attrs["openvisus"]=repr([self.dst])
				dst_parent[src_field.nxname]=dst_field

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
				self._convertNexusFieldsToOpenVisus(src_child, dst_child)
