import os ,sys, time, logging,shutil,glob,json, string, random, argparse, shutil, base64,copy,subprocess
from datetime import datetime
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

# ///////////////////////////////////////////////////////////////////////
class Datasets:

	def __init__(self, db_filename):
		self.conn = sqlite3.connect(db_filename)
		self.conn.row_factory = sqlite3.Row
		#self.dropTable()
		self.createTable()

	def dropTable(self):
		self.conn.execute("""DROP TABLE IF EXISTS datasets""")
		self.conn.commit()

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
	
	# pushPendingConvert
	def pushPendingConvert(self, group, name, src, dst, compression="zip", arco="modvisus", metadata=[]):
		# TODO: if multiple converters?
		self.conn.executemany("INSERT INTO datasets ('group', name, src, dst, compression, arco, metadata, insert_time) values(?,?,?,?,?,?,?,?)",[
			(group, name, src, dst, compression, arco, json.dumps(metadata), datetime.now())
		])
		self.conn.commit()

	# popPendingConvert
	def popPendingConvert(self):
		# TODO: if multiple converters?
		data = self.conn.execute("SELECT * FROM datasets WHERE conversion_end is NULL order by id ASC LIMIT 1")
		row=data.fetchone()
		if row is None: 
			return None
		row={k:row[k] for k in row.keys()}
		row["conversion_start"]=str(datetime.now())
		data = self.conn.execute("UPDATE datasets SET conversion_start==? where id=?",(row["conversion_start"],row["id"], ))
		self.conn.commit()
		return row

	# setConvertDone
	def setConvertDone(self, row):
		row["conversion_end"]=str(datetime.now())
		data = self.conn.execute("UPDATE datasets SET conversion_end==? where id=?",(row["conversion_end"],row["id"], ))
		self.conn.commit()

	# getAll
	def getAll(self):
		for row in self.conn.execute("SELECT * FROM datasets ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# getConverted
	def getConverted(self):
		for row in self.conn.execute("SELECT * FROM datasets WHERE conversion_end is not NULL ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# generateModVisusConfig
	def generateModVisusConfig(self, filename):
		logger.info(f"generateModVisusConfig begin filename={filename}")

		v=[]
		converted=self.getConverted()

		N=0
		for row in converted:
			v.append(f"""<dataset name='{row["group"]}/{row["name"]}' url='{row["dst"]}' group='{row["group"]}' convert_id='{row["id"]}' />""")
			N+=1
		body="\n".join([f"<!-- file automatically generated {str(datetime.now())} -->"] + v + [""])

		# save the file
		with open(filename,"w") as f:
			f.write(body)
		logger.info(f"Saved file {filename}")
		logger.info(f"generateModVisusConfig end #datasets={N} filename={filename}")
		return body

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
	db=ov.CreateIdx(url=idx_filename, dims=[W,H,D], fields=[field], compression="raw", arco=arco, axis=idx_axis, physic_box=idx_physic_box)

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




# ////////////////////////////////////////////////////////////
class CreateNexusStreamable:

	# TODO: what is the criteria to remove fields?
	MAX_NXFIELD_BYTES=1024*1024

	# constructor
	def __init__(self,src_filename, idx_filename_template, streamable_filename):
		self.src_filename=src_filename
		self.streamable_filename=streamable_filename
		self.idx_filename_template=idx_filename_template

	# run
	def run(self):
		logger.info(f"NexusCreateStreamable::run filename={self.src_filename} full-size={os.path.getsize(self.src_filename):,}")
		if os.path.isfile(self.streamable_filename): os.remove(self.streamable_filename)
		src=nxload(self.src_filename)
		dst=copy.deepcopy(src)
		dst.attrs["streamable"]=True
		self._convertNexusFieldsToOpenVisus(src, dst)
		nxsave(self.streamable_filename, dst , mode='w')
		logger.info(f"NexusCreateStreamable::run streamable_filename={self.streamable_filename} reduced-size={os.path.getsize(self.streamable_filename):,}")
		return dst
	
	# _convertNexusFieldsToOpenVisus
	def _convertNexusFieldsToOpenVisus(self, src, dst):

		if isinstance(src,NXfield):

			if src.nbytes<=self.MAX_NXFIELD_BYTES:

				# deepcopy does not seem to copy nxdata (maybe for the lazy evalation?)
				dst.nxdata=copy.copy(src.nxdata)

			else:

				logger.info("Removing Nxfield",src.nxname)

				# replace any 'big' field with something virtually empty
				# TODO: read nexus by slabs
				t1=time.time()
				logger.info(f"Reading Nexus field {src.nxname}...")
				data = src.nxdata
				logger.info(f"Read Nexus field  in {time.time()-t1} seconds")

				# this is the version without any data
				new_field=NXfield(value=None, shape=src.shape, dtype=data.dtype)

				idx_filename=self.idx_filename_template.replace("{NxField::nxname}",src.nxname)

				t1=time.time()
				logger.info(f"Creating IDX file {idx_filename}...")
				field=ov.Field.fromString(f"""DATA {str(data.dtype)} format(row_major) min({np.min(data)}) max({np.max(data)})""")

				parent=src.nxgroup
				assert(isinstance(parent,NXdata))
				axis=[parent[it] for it in parent.attrs["axes"]]

				idx_axis=[]
				idx_physic_box=[]
				for it in axis:
					idx_physic_box=[str(it.nxdata[0]),str(it.nxdata[-1])] + idx_physic_box
					idx_axis=[it.nxname] +idx_axis
				idx_axis=" ".join(idx_axis)
				idx_physic_box=" ".join(idx_physic_box)
		
				db=ov.CreateIdx(
					url=idx_filename, 
					dims=list(reversed(data.shape)), 
					fields=[field], 
					compression="raw",
					physic_box=ov.BoxNd.fromString(idx_physic_box),
					axis=idx_axis
				)
				db.write(data)
				logger.info(f"Created IDX file {idx_filename} in {time.time()-t1} seconds")

				# add as attribute (list of openvisus files)
				new_field.attrs["openvisus"]=repr([idx_filename])

				# need to modify the parent
				dst.nxgroup[src.nxname]=new_field
		
		# recurse
		if hasattr(src,"items"):
			for name in src.entries:
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
def LocalFileToMetadata(metadata, filename):
	try:
		ext=os.path.splitext(filename)[1]
		with open(filename,mode='rb') as f:
			body=f.read()

		if ext==".json":
			item={'type':'json-object','filename': filename, 'object': json.loads(body)}
		else:
			encoded=base64.b64encode(body).decode('ascii') # this should work with streamable nexus data too! or any binary file not too big (i.e. without big 3d data )
			item={'type':'b64encode','filename' : filename,'encoded': encoded}
		logger.info(f"Read metadata type={type} filename={filename} ext={ext} body_c_size={len(body)}")
		metadata.append(item)

	except Exception as ex:
		logger.info(f"Reading of metadata {filename} failed {ex}. Skipping it")


# ///////////////////////////////////////////////////////////////////
def Touch(filename):
	from pathlib import Path
	Path(filename).touch(exist_ok=True)


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	
	log_filename=os.environ["NSDF_CONVERT_LOG_FILENAME"]
	convert_queue_name=os.environ["NSDF_CONVERT_QUEUE"]
	pubsub_url=os.environ["NSDF_CONVERT_PUBSUB_URL"]	
	sqlite3_filename=os.environ["NSDF_CONVERT_SQLITE3_FILENAME"]
	modvisus_group_filename=os.environ["NSDF_CONVERT_MODVISUS_CONFIG"]
	converted_url_template=os.environ["NSDF_CONVERTED_URL_TEMPLATE"]
	group_config_filename=os.environ["NSDF_CONVERT_GROUP_CONFIG"]
	modvisus_root_filename=os.environ["MODVISUS_CONFIG"]

	SetupLogger(log_filename)
	
	if sys.argv[1]=="init-db":
		db=Datasets(sqlite3_filename)
		db.dropTable()
		db.createTable()
		for row in db.getAll():
			logger.info(row)
		logger.info(f"init-db done filename={sqlite3_filename}")	
		sys.exit(0)


	if sys.argv[1]=="generate-modvisus-config":
		db=Datasets(sqlite3_filename)
		db.generateModVisusConfig(modvisus_group_filename)
		Touch(modvisus_root_filename)
		sys.exit(0)

	if sys.argv[1]=="run-convert-loop":

		def GetPubSubChannel(queue_name):
			params = pika.URLParameters(pubsub_url)
			connection = pika.BlockingConnection(params)
			ret = connection.channel()
			ret.queue_declare(queue=queue_name)
			return connection, ret

		connection_in, channel_in  = GetPubSubChannel(convert_queue_name)

		db=Datasets(sqlite3_filename)
		db.generateModVisusConfig(modvisus_group_filename)
		Touch(modvisus_root_filename)

		logger.info(f"RunConvertLoop start")

		# track changes in github repo and automatically commit
		def RunGitLoop():
			while True:
				time.sleep(3)
				for I,cmd in enumerate(['git pull', 'git add *.json','git commit -a -m "new version"','git push']):
					output=subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.STDOUT, shell=True,check=False,cwd=os.path.dirname(group_config_filename)).stdout.decode("utf-8").strip()
					if I==0: continue 
					if any([
							not output,
						 "up-to-date" in output,
						 "nothing to commit" in output,
						 "did not match any files" in output,
					]): 
						continue
					logger.info(f"RunGitLoop cmd={cmd} output={output.strip()}")

		import threading
		t=threading.Thread(target=RunGitLoop)
		t.start()

		last_message_time=time.time()
		exitNow=False
		while not exitNow:

			# add all the messages to the database
			# https://pika.readthedocs.io/en/stable/examples/blocking_consumer_generator.html
			for method_frame, properties, body in channel_in.consume(convert_queue_name, auto_ack=False,inactivity_timeout=0.1):
				if (time.time()-last_message_time) > 180:
					logger.info(f"Listening to the queue={convert_queue_name}")
					last_message_time=time.time()

				if method_frame is None:  break  # timeout
				body=body.decode("utf-8").strip()
				msg=json.loads(body)
				logger.info(f"PubSub received message from queue={convert_queue_name} body=\n{json.dumps(msg,indent=2)} ")
				logger.info(f"Adding item top local db")
				db.pushPendingConvert(**msg)

				# important to do only here, I don't want to loose any message
				channel_in.basic_ack(delivery_tag=method_frame.delivery_tag) 

			# When you escape out of the loop, be sure to call consumer.cancel() to return any unprocessed messages.
			channel_in.cancel()

			# take one dataset from the database
			row=db.popPendingConvert()

			# no database to convert? just wait
			if not row:
				time.sleep(0.1)
				continue

			logger.info(f"Starting conversion spec={json.dumps(row,indent=2)}")

			src,dst=row["src"],row["dst"]

			# extract group_name (name should be in the form `group/whatever`)
			group_name, dataset_name=row['group'],row['name']
			logger.info(f"group={group_name} name={dataset_name}")

			# read group config (if not exists create a new one)
			group_config={"datasets": []}
			if os.path.isfile(group_config_filename) and os.path.getsize(group_config_filename):
				with open(group_config_filename,"r") as f:
					try:
						group_config=json.load(f)
						logger.info(f"Loaded JSON file {group_config_filename}")
					except Exception as ex:
						logger.info(f"Loading of JSON file {group_config_filename} failed {ex} ")

			# read metatada (can be a binary file too?)
			metadata=[]
			for it in json.loads(row["metadata"]):
				type=it['type']
				assert(type=="file") # TODO other cases
				filename=it['path']
				LocalFileToMetadata(metadata,filename)

			if True:
					# NOTE: this is dangerous but I have to do it: I need to remove all openvisus files in case I crashed in a middle of compression
				# e.g assuyming /mnt/data1/nsdf/tmp/near-field-scrgiorgio-20230912-01/visus.idx I need to clean up the parent directory
				# SO MAKE SURE you are using unique directories!			
				logger.info(f" DANGEROUS but needed: removing any file from {os.path.dirname(dst)}")
				shutil.rmtree(os.path.dirname(dst), ignore_errors=True)

			src_ext=os.path.splitext(src)[1]

			# image stack 
			if src_ext==".tif":
				ConvertImageStack(src, dst, compression=row["compression"], arco=row["arco"])

			# nexus file
			elif src_ext ==".nxs":
				# TODO: not supporting multiple fields inside a nexus file
				left,ext=os.path.splitext(dst);assert(ext==".idx")
				streamable_nexus=left + ".nxs"
				CreateNexusStreamable(src, dst, streamable_nexus).run()
				LocalFileToMetadata(metadata,streamable_nexus)
			
			else:
				raise Exception("to handle... ")

			row["conversion_end"]=str(datetime.now())

			# save group config file (TODO commit to github)
			group_config["datasets"].append({
				"name" : f"{group_name}/{dataset_name}", # for displaying
				"url" : converted_url_template.format(group=group_name, name=dataset_name),
				"color-mapper-type":"log",
				"metadata" : metadata + [{'type':'json-object', 'filename': 'generated-nsdf-convert.json',  'object' : {k:str(v) for k,v in row.items() if k!="metadata"}}]
			})		

			with open(group_config_filename,"w") as f:
				json.dump(group_config,f, indent=2)
				logger.info(f"Saved group config to filename={group_config_filename}")

			# this sets the conversion_done with is needed for visus config generation
			db.setConvertDone(row)

			db.generateModVisusConfig(modvisus_group_filename)
			Touch(modvisus_root_filename) # force modvisus reload

			logger.info(f"*** Re-entering loop ***")

		t.stop()
		logger.info(f"RunConvertLoop end")
		channel_in.close();connection_in.close()
		sys.exit(0)



