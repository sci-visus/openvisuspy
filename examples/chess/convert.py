import os ,sys, time, logging,shutil,glob,json, string, random, argparse, shutil, base64,copy,subprocess
from datetime import datetime

import urllib3
urllib3.disable_warnings()
import pika
import sqlite3 
import numpy as np
from skimage import io

# python3 -m pip install nexusformat
from nexusformat.nexus import * 
from nexusformat.nexus.tree import NX_CONFIG 
NX_CONFIG['memory']=32000 # alllow data to be 32GB

import OpenVisus as ov

logger = logging.getLogger("nsdf-convert")

# for debugging
# ov.SetupLogger(logging.getLogger("OpenVisus"), output_stdout=True) 

log_filename=os.environ["NSDF_CONVERT_LOG_FILENAME"]
sqlite3_filename=os.environ["NSDF_CONVERT_SQLITE3_FILENAME"]
modvisus_group_filename=os.environ["NSDF_CONVERT_MODVISUS_CONFIG"]
converted_url_template=os.environ["NSDF_CONVERTED_URL_TEMPLATE"]
group_config_filename=os.environ["NSDF_CONVERT_GROUP_CONFIG"]
modvisus_root_filename=os.environ["MODVISUS_CONFIG"]
chessdata_uri=os.environ["CHESSDATA_URI"]

# ///////////////////////////////////////////////////////////////////////
class Datasets:

	# constructor
	def __init__(self, db_filename):
		self.conn = sqlite3.connect(db_filename)
		self.conn.row_factory = sqlite3.Row
		#self.dropTable()
		self.createTable()
		self.generateFiles()

	# dropTable
	def dropTable(self):
		self.conn.execute("""DROP TABLE IF EXISTS datasets""")
		self.conn.commit()		

	# createTable
	def createTable(self):
		self.conn.execute("""
		CREATE TABLE IF NOT EXISTS datasets (
			id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
			'group' TEXT NOT NULL, 
			name TEXT NOT NULL,
			src TEXT NOT NULL,
			dst TEXT NOT NULL,
			compression TEXT,
			arco TEXT,
			metadata TEXT,
			insert_time timestamp NOT NULL, 
			conversion_start timestep ,
			conversion_end   timestamp 
		)
		""")
		self.conn.commit()
		self.generateFiles()		
	
	# pushPendingConvert
	def pushPendingConvert(self, group, name, src, dst, compression="zip", arco="modvisus", metadata=[]):
		# TODO: if multiple converters?
		self.conn.executemany("INSERT INTO datasets ('group', name, src, dst, compression, arco, metadata, insert_time) values(?,?,?,?,?,?,?,?)",[
			(group, name, src, dst, compression, arco, json.dumps(metadata), datetime.now())
		])
		self.conn.commit()

	# popPendingConvert
	def popPendingConvert(self):
		data = self.conn.execute("SELECT * FROM datasets WHERE conversion_end is NULL order by id ASC LIMIT 1")
		row=data.fetchone()
		if row is None: return None
		row={k:row[k] for k in row.keys()}
		row["metadata"]=json.loads(row["metadata"])
		row["conversion_start"]=str(datetime.now())
		data = self.conn.execute("UPDATE datasets SET conversion_start==? where id=?",(row["conversion_start"],row["id"], ))
		self.conn.commit()
		return row

	# setConvertDone
	def setConvertDone(self, row):
		row["conversion_end"]=str(datetime.now())
		data = self.conn.execute("UPDATE datasets SET conversion_end==? where id=?",(row["conversion_end"],row["id"], ))
		self.conn.commit()
		self.generateFiles()

	# getAll
	def getAll(self):
		for row in self.conn.execute("SELECT * FROM datasets ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# getConverted
	def getConverted(self):
		for row in self.conn.execute("SELECT * FROM datasets WHERE conversion_end is not NULL ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# generateFiles
	def generateFiles(self):
		logger.info(f"generateFiles begin...")

		# create the json file if not exist
		if not os.path.isfile(group_config_filename):
			with open(group_config_filename,"w") as fp:
				json.dump({"datasets": []}, fp, indent=2)
			logger.info(f"Create group JSON file={group_config_filename}")
		else:
			Touch(group_config_filename)
			logger.info(f"Touched group JSON file={group_config_filename}")

		v=[]
		converted=self.getConverted()

		N=0
		for row in converted:
			v.append(f"""<dataset name='{row["group"]}/{row["name"]}' url='{row["dst"]}' group='{row["group"]}' convert_id='{row["id"]}' />""")
			N+=1
		body="\n".join([f"<!-- file automatically generated {str(datetime.now())} -->"] + v + [""])

		# save the file
		with open(modvisus_group_filename,"w") as f:
			f.write(body)
		logger.info(f"Saved file {modvisus_group_filename}")
		logger.info(f"generateFiles end #datasets={N} modvisus_group_filename={modvisus_group_filename}")
		Touch(modvisus_root_filename) # force modvisus reload

# # ///////////////////////////////////////////////////////////////////
def ConvertImageStack(src, dst, compression="raw",arco="modvisus"):

	logger.info(f"ConvertImageStack src={src} dst={dst} compression={compression} arco={arco} start...")

	ext=os.path.splitext(src)[1]
	logger.info(f"Finding files with ext={ext}")
	t1=time.time()
	filenames=list(sorted(glob.glob(src)))
	logger.info(f"Found {len(filenames)} {ext} files")

	logger.info(f"Loading {filenames[0]}..{filenames[-1]}")
	img = io.imread(filenames[0])
	D=len(filenames)
	H,W=img.shape
	data=np.zeros((D,H,W),dtype=img.dtype)
	for Z,filename in enumerate(filenames):
			#print(f"Loading {filename}")
			data[Z,:,:]=io.imread(filename)

	# why I am forcing it to be float32? I don't rememeber, maybe for openvisus/bokeh?
	data=data.astype(np.float32)

	vmin,vmax=np.min(data),np.max(data)
	D,H,W=data.shape
	logger.info(f"Image stack loaded in {time.time() - t1} seconds shape={data.shape} dtype={data.dtype} c_size={W*H*D*4:,} vmin={vmin} vmax={vmax}")
	D,H,W=data.shape

	# write uncompressed
	idx_filename=dst
	field=ov.Field.fromString(f"""DATA {str(data.dtype)} format(row_major) min({vmin}) max({vmax})""")

	# TODO: I can I get this information from image stack???
	idx_physic_box=ov.BoxNd.fromString(f"0 {W} 0 {H} 0 {D}")
	idx_axis="X Y Z"
	db=ov.CreateIdx(
		url=idx_filename, 
		dims=[W,H,D], 
		fields=[field], 
		compression="raw", 
		arco=arco, 
		axis=idx_axis, 
		physic_box=idx_physic_box)

	# print(db.getDatasetBody().toString())
	logger.info(f"IDX file={idx_filename} created")

	os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
	logger.info(f"Writing IDX data...")
	t1 = time.time()
	db.write(data, time=0)
	write_sec=time.time() - t1
	logger.info(f"Wrote IDX data in {write_sec} seconds")

	if compression and compression!="raw":
		t1 = time.time()
		logger.info(f"Compressing dataset to {compression}")
		db.compressDataset([compression])
		logger.info(f"Compressed dataset to {compression} in {time.time()-t1} seconds")

	logger.info(f"ConvertImageStack src={src} dst={dst} compression={compression} arco={arco} done")


# # ///////////////////////////////////////////////////////////////////
def ConvertNumPy(src, dst, compression="raw", arco="modvisus"):

	logger.info(f"ConvertNumPy src={src} dst={dst} compression={compression} arco={arco} start...")

	logger.info(f"Loading {src}...")
	t1=time.time()
	data=np.load(src)
	D,H,W=data.shape
	m,M=np.min(data),np.max(data)

	# why I am forcing it to be float32? I don't rememeber, maybe for openvisus/bokeh?
	data=data.astype(np.float32)

	vmin,vmax=np.min(data),np.max(data)
	D,H,W=data.shape
	logger.info(f"numpy loaded in {time.time() - t1} seconds shape={data.shape} dtype={data.dtype} c_size={W*H*D*4:,} vmin={vmin} vmax={vmax}")
	D,H,W=data.shape

	# write uncompressed
	idx_filename=dst
	field=ov.Field.fromString(f"""DATA {str(data.dtype)} format(row_major) min({vmin}) max({vmax})""")

	# TODO: I can I get this information from image stack???
	idx_physic_box=ov.BoxNd.fromString(f"0 {W} 0 {H} 0 {D}")
	idx_axis="X Y Z"
	db=ov.CreateIdx(
		url=idx_filename, 
		dims=[W,H,D], 
		fields=[field], 
		compression="raw", 
		arco=arco)

	# print(db.getDatasetBody().toString())
	logger.info(f"IDX file={idx_filename} created")

	os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
	logger.info(f"Writing IDX data...")
	t1 = time.time()
	db.write(data, time=0)
	write_sec=time.time() - t1
	logger.info(f"Wrote IDX data in {write_sec} seconds")

	if compression and compression!="raw":
		t1 = time.time()
		logger.info(f"Compressing dataset to {compression}")
		db.compressDataset([compression])
		logger.info(f"Compressed dataset to {compression} in {time.time()-t1} seconds")

	logger.info(f"ConvertNumPy src={src} dst={dst} compression={compression} arco={arco} done")



# ////////////////////////////////////////////////////////////
class ConvertNexus:

	# constructor
	def __init__(self,src, dst, compression="raw", arco="modvisus", streamable=None):
		self.src=src
		self.dst=dst
		self.streamable=streamable
		self.compression=compression
		self.arco=arco
		self.num_bin_fields=0

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
				logger.info("   "*(depth+0) +  f"{node.nxname}::{type(node)} shape={node.shape} dtype={node.dtype} ***********************************")
			else:
				logger.info("   "*(depth+0) + f"{node.nxname}::{type(node)}")
			for k,v in node.attrs.items():
				logger.info("  "*(depth+1) + f"@{k} = {v}")

	# run
	def run(self):
		logger.info(f"ConvertNexus::run src={self.src} full-size={os.path.getsize(self.src):,}")
		src=nxload(self.src)
		dst=copy.deepcopy(src)
		dst.attrs["streamable"]=True
		self._convertNexusFieldsToOpenVisus(src, dst)

		if self.streamable:
			t1=time.time()
			logger.info(f"Creating streamable version {self.streamable}")
			if os.path.isfile(self.streamable): os.remove(self.streamable)			
			nxsave(self.streamable, dst , mode='w')
			logger.info(f"ConvertNexus::run streamable={self.streamable} reduced-size={os.path.getsize(self.streamable):,}")
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
				logger.info(f"Reading Nexus field name={src_field.nxname} dtype={src_field.dtype} shape={src_field.shape} ...")
				data = src_field.nxdata
				vmin,vmax=np.min(data),np.max(data)
				logger.info(f"Read Nexus field in {time.time()-t1} seconds vmin={vmin} vmax={vmax}")

				# e.g. 1x1441x676x2048 -> 1x1441x676x2048
				if len(data.shape)==4:
					assert(data.shape[0]==1)
					data=data[0,:,:,:]

				t1=time.time()
				logger.info(f"Creating IDX file {self.dst}")
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
					logger.info("Found axis={idx_axis} idx_physic_box={idx_physic_box}")
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
					axis=idx_axis,
					arco=self.arco
				)

				t1=time.time()
				logger.info(f"Writing IDX data...")
				db.write(data)
				logger.info(f"Wrote IDX data in {time.time()-t1} seconds")

				if self.compression and self.compression!="raw":
					t1 = time.time()
					logger.info(f"Compressing dataset compression={self.compression}...")
					db.compressDataset([self.compression])
					logger.info(f"Compressed dataset to {self.compression} in {time.time()-t1} seconds")

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


# ///////////////////////////////////////////////////////////////////
def SetupLogger(filename):
	logger.setLevel(logging.INFO)
	formatter = logging.Formatter('%(asctime)s,%(msecs)d %(filename)s::%(lineno)d %(levelname)s %(message)s')

	stdout_handler = logging.StreamHandler(sys.stdout)
	stdout_handler.setLevel(logging.DEBUG)
	stdout_handler.setFormatter(formatter)

	logger_filename=filename
	os.makedirs(os.path.dirname(logger_filename), exist_ok=True)
	file_handler = logging.FileHandler(logger_filename)
	file_handler.setLevel(logging.DEBUG)
	file_handler.setFormatter(formatter)

	logger.addHandler(file_handler)
	logger.addHandler(stdout_handler)	


# ///////////////////////////////////////////////////////////////////
def LoadMetadataFromFile(filename):
	
	ext=os.path.splitext(filename)[1]
	with open(filename,mode='rb') as f:
		body=f.read()

	if ext==".json":
		item={
			'type':'json-object',
			'filename': filename, 
			'object': json.loads(body)
		}
	else:
		encoded=base64.b64encode(body).decode('ascii') # this should work with streamable nexus data too! or any binary file not too big (i.e. without big 3d data )
		item={
			'type':'b64encode',
			'filename' : filename,
			'encoded': encoded
		}
	logger.info(f"Read metadata type={type} filename={filename} ext={ext} body_c_size={len(body)}")
	return item


# ///////////////////////////////////////////////////////////////////
def LoadMetadataFromChess(query=None,uri=None):
	"""
	python -m pip install chessdata-pyclient
	# modified /mnt/data1/nsdf/miniforge3/envs/my-env/lib/python3.9/site-packages/chessdata/__init__.py added at line 49 `verify=False`
	# otherwise I need a certificate `export REQUESTS_CA_BUNDLE=`
	"""
	import chessdata 
	records = chessdata.query(query,url=uri) 
	logger.info(f"Read CHESS metadata from uri={uri} CHESS query={query}] #records={len(records)}")

	return {
		'type':'json-object',
		'filename': '/dev/null', 
		'query'   : query,
		'records' : records,
	}

# ///////////////////////////////////////////////////////////////////
def Touch(filename):
	from pathlib import Path
	Path(filename).touch(exist_ok=True)

# ///////////////////////////////////////////////////////////////////
def RunSingleConvert(specs):

	logger.info(f"RunSingleConvert spec={json.dumps(specs,indent=2)}")

	src,dst=specs["src"],specs["dst"]

	# extract group_name (name should be in the form `group/whatever`)
	group_name, dataset_name=specs['group'],specs['name']
	logger.info(f"group={group_name} name={dataset_name}")

	# read metatada (can be a binary file too?)
	metadata=[]
	for it in specs["metadata"]:
		type=it['type']
		if type=="file":
			filename=it['path']
			try:
				metadata.append(LoadMetadataFromFile(filename))
			except Exception as ex:
				logger.info(f"LoadMetadataFromFile filename={filename} failed {ex}. Skipping it")
		elif type=="chess-metadata":
			query=json.dumps(it['query'])
			try:
				metadata.append(LoadMetadataFromChess(query, uri=chessdata_uri))
			except Exception as ex:
				logger.info(f"LoadMetadataFromChess query={query} uri={chessdata_uri} failed {ex}. Skipping it")
		else:
			raise Exception("todo")

	if True:
			# NOTE: this is dangerous but I have to do it: I need to remove all openvisus files in case I crashed in a middle of compression
		# e.g assuyming /mnt/data1/nsdf/tmp/near-field-scrgiorgio-20230912-01/visus.idx I need to clean up the parent directory
		# SO MAKE SURE you are using unique directories!			
		logger.info(f" DANGEROUS but needed: removing any file from {os.path.dirname(dst)}")
		shutil.rmtree(os.path.dirname(dst), ignore_errors=True)

	src_ext=os.path.splitext(src)[1]

	# image stack 
	if src_ext==".tif" and "*" in src:
		ConvertImageStack(src, dst, compression=specs["compression"], arco=specs["arco"])

	# nexus file
	elif src_ext ==".nxs":
		# TODO: not supporting multiple fields inside a nexus file
		# TODO: with some nexus file I am unable to create shrinked streamable (probably related to NXlinkfield)
		streamable=None # os.path.splitext(dst)[0]+".nxs"
		ConvertNexus(src, dst, compression=specs["compression"], arco=specs["arco"], streamable=None).run()
		# LocalFileToMetadata(metadata,streamable_nexus)

	elif src_ext == ".npy":
		ConvertNumPy(src, dst, compression=specs["compression"], arco=specs["arco"])
	
	else:
		raise Exception("to handle... ")

	specs["conversion_end"]=str(datetime.now())

	# read group config (if not exists create a new one)
	group_json_config={"datasets": []}
	if os.path.isfile(group_config_filename) and os.path.getsize(group_config_filename):
		with open(group_config_filename,"r") as f:
			try:
				group_json_config=json.load(f)
				logger.info(f"Loaded JSON file {group_config_filename}")
			except Exception as ex:
				logger.info(f"Loading of JSON file {group_config_filename} failed {ex} ")

	# save group config file 
	group_json_config["datasets"].append({
		"name" : f"{group_name}/{dataset_name}", # for displaying
		"url" : converted_url_template.format(group=group_name, name=dataset_name),
		"color-mapper-type":"log",
		"metadata" : metadata + [{
			'type':'json-object', 
			'filename': 'generated-nsdf-convert.json',  
			'object' : {k:str(v) for k,v in specs.items() if k!="metadata"}
		}]
	})		

	with open(group_config_filename,"w") as fp:
		json.dump(group_json_config, fp, indent=2)
		logger.info(f"Saved group config to filename={group_config_filename}")


# ///////////////////////////////////////////////////////////////////
class PullEvents:
	
	# constructor
	def __init__(self,db):
		self.db=db

class PullEventsFromLocalDirectory(PullEvents):

	# constructor	
	def __init__(self,db, pattern):
		super().__init__(db)
		self.pattern=pattern

	# doPullEvents
	def doPullEvents(self):
		for filename in list(glob.glob(pattern)):
				try:
					with open(filename,"rt") as f:
						specs=json.load(f)
						logger.info(f"json.loads('{filename}') ok")
				except Exception as ex:
					logger.info(f"json.loads('{filename}') failed {ex}")
					continue

				print(specs)
				self.db.pushPendingConvert(**specs)
				shutil.move(filename,filename + ".~pushed")

class PullEventsFromRabbitMq(PullEvents):

	# constructor
	def __init__(self,db,url, queue):
		super().__init__(db)
		self.queue=queue
		self.connection_in = pika.BlockingConnection(pika.URLParameters(url))
		self.channel_in = self.connection_in.channel()
		self.channel_in.queue_declare(queue=queue)

	# doPullEvents
	def doPullEvents(self):

			# add all the messages to the database
			# https://pika.readthedocs.io/en/stable/examples/blocking_consumer_generator.html
			for method_frame, properties, body in self.channel_in.consume(self.queue, auto_ack=False,inactivity_timeout=0.1):

				if method_frame is None:  break  # timeout
				body=body.decode("utf-8").strip()
				specs=json.loads(body)
				logger.info(f"PubSub received message from queue={self.queue} body=\n{json.dumps(specs,indent=2)} ")
				logger.info(f"Adding item top local db")
				db.pushPendingConvert(**specs)

				# important to do only here, I don't want to loose any message
				self.channel_in.basic_ack(delivery_tag=method_frame.delivery_tag) 

			 # from PICKA: When you escape out of the loop, be sure to call consumer.cancel() to return any unprocessed messages.			
			self.channel_in.cancel()



# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":

	SetupLogger(log_filename)

	if sys.argv[1]=="test-chess-metadata":
		import chessdata 
		query="""{"_id": "65032a84d2f7654ee374db59"}"""
		records = chessdata.query(query, url=chessdata_uri)
		logger.info(f"Read metadata from CHESS #records={len(records)}")
		#print(records)
		sys.exit(0)		
	
	if sys.argv[1]=="init-db":
		db=Datasets(sqlite3_filename)
		db.dropTable()
		db.createTable()
		for row in db.getAll():
			logger.info(row)
		logger.info(f"init-db done filename={sqlite3_filename}")	
		sys.exit(0)

	if sys.argv[1]=="run-single-convert":
		with open(sys.argv[2],"rt") as f:
			specs = json.load(f)
		RunSingleConvert(specs)
		sys.exit(0)

	if sys.argv[1]=="run-convert-loop":
		logger.info(f"RunConvertLoop start")

		db=Datasets(sqlite3_filename)

		if "*" in sys.argv[2]:
			pattern=sys.argv[2]
			puller=PullEventsFromLocalDirectory(db,pattern)

		elif "amqps://" in sys.argv[2]:
			url,queue=sys.argv[2:]
			puller=PullEventsFromRabbitMq(db,sys.argv[2],queue)

		else:
			raise Exception(f"unknown loop for {sys.argv[2]}")

		while True:
			puller.doPullEvents()
			specs=db.popPendingConvert()

			# no database to convert? just wait
			if not specs:
				time.sleep(1.0)
				continue

			RunSingleConvert(specs)
			db.setConvertDone(specs)
			
			logger.info(f"*** Re-entering loop ***")

		logger.info(f"RunConvertLoop end")
		sys.exit(0)

	raise Exception(f"unknown action={sys.argv[1]}")


