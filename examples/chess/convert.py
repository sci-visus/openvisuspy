import os ,sys, time, logging,shutil,glob,json, string, random, argparse, shutil, base64
from datetime import datetime
import pika
import sqlite3 
import numpy as np
from skimage import io
import OpenVisus as ov

logger = logging.getLogger("nsdf-convert")

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
	def pushPendingConvert(self, name, src, dst, compression, arco, metadata):
		# TODO: if multiple converters?
		self.conn.executemany("INSERT INTO datasets (name, src, dst, compression, arco, metadata, insert_time) values(?,?,?,?,?,?,?)",[
			(name, src, dst, compression, arco, json.dumps(metadata), datetime.now())
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
		return row

	# getAll
	def getAll(self):
		for row in self.conn.execute("SELECT * FROM datasets ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# getConverted
	def getConverted(self):
		for row in self.conn.execute("SELECT * FROM datasets WHERE conversion_end is not NULL ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# generateConfig
	def generateConfig(self, filename):
		logger.info("generateConfig begin")

		v=[]
		converted=self.getConverted()

		N=0
		for row in converted:
			v.append(f"""<dataset name='{row["name"]}' url='{row["dst"]}' convert_id='{row["id"]}' />""")
			N+=1
		body="\n".join([
			f"<!-- file automatically generated {str(datetime.now())} -->",
			"<datasets>"] + v + [
				"</datasets>",
				""
				])

		# save the file
		shutil.move(filename,filename + ".bak")
		with open(filename,"w") as f:
			f.write(body)
		logger.info(f"Saved file {filename}")
		logger.info(f"generateConfig end #datasets={N}")
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
	idx_physic_box=ov.BoxNd.fromString(f"0 {W} 0 {H} 0 {D}"),
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
if __name__ == "__main__":
	
	CONVERT_LOG_FILENAME=os.environ["CONVERT_LOG_FILENAME"]
	CONVERT_QUEUE_IN=os.environ["CONVERT_QUEUE_IN"]
	CONVERT_QUEUE_OUT=os.environ["CONVERT_QUEUE_OUT"]
	PUBSUB_URL=os.environ["PUBSUB_URL"]	
	CONVERT_SQLITE3_FILENAME=os.environ["CONVERT_SQLITE3_FILENAME"]
	VISUS_CONVERT_CONFIG=os.environ["VISUS_CONVERT_CONFIG"]

	SetupLogger(CONVERT_LOG_FILENAME)
	
	if sys.argv[1]=="init-db":
		db=Datasets(CONVERT_SQLITE3_FILENAME)
		db.dropTable()
		db.createTable()
		for row in db.getAll():
			logger.info(row)
		logger.info("init-db done")	
		sys.exit(0)

	# single conversion
	if "--src" in sys.argv:
		parser = argparse.ArgumentParser(description="convert demo")
		parser.add_argument("--src", type=str, help="images", required=True)	
		parser.add_argument("--dst", type=str, help="idx filename", required=True)	
		parser.add_argument("--compression", type=str, help="compression", required=False, default="raw")
		parser.add_argument("--arco", type=str, help="arco", required=False, default="modvisus")
		args = parser.parse_args()
		ConvertImageStack(args.src, args.dst, compression=args.compression, arco=args.arco)
		sys.exit(0)	

	if sys.argv[1]=="dump-datasets":
		db=Datasets(CONVERT_SQLITE3_FILENAME)
		body=db.generateConfig(VISUS_CONVERT_CONFIG)
		print(body)
		sys.exit(0)

	if sys.argv[1]=="run-convert-loop":

		def GetPubSubChannel(name):
			params = pika.URLParameters(PUBSUB_URL)
			connection = pika.BlockingConnection(params)
			ret = connection.channel()
			ret.queue_declare(queue=name)
			return connection, ret

		connection_in, channel_in  = GetPubSubChannel(CONVERT_QUEUE_IN)
		connection_out,channel_out = GetPubSubChannel(CONVERT_QUEUE_OUT)

		db=Datasets(CONVERT_SQLITE3_FILENAME)
		db.generateConfig(VISUS_CONVERT_CONFIG)
		logger.info(f"RunConvertLoop start")

		exitNow=False
		while not exitNow:

			# add all the messages to the database
			# https://pika.readthedocs.io/en/stable/examples/blocking_consumer_generator.html
			for method_frame, properties, body in channel_in.consume(CONVERT_QUEUE_IN, auto_ack=False,inactivity_timeout=0.1):

				# timeout
				if method_frame is None: 
					break 
				body=body.decode("utf-8").strip()
				msg=json.loads(body)
				logger.info(f"PubSub received message from queue={CONVERT_QUEUE_IN} body=\n{json.dumps(msg,indent=2)} ")
				logger.info(f"Pushing PubSub message to local database msg={json.dumps(msg,indent=2)}")
				db.pushPendingConvert(**msg)

				# important to do only here, I don't want to loose any message
				channel_in.basic_ack(delivery_tag=method_frame.delivery_tag) 

			# When you escape out of the loop, be sure to call consumer.cancel() to return any unprocessed messages.
			channel_in.cancel()

			# take one dataset from the database
			row=db.popPendingConvert()

			if not row:
				time.sleep(0.1)
				continue

			logger.info(f"Starting conversion spec={json.dumps(row,indent=2)}")

			# read metatada (can be a binary file too?)
			metadata=[]

			for it in json.loads(row["metadata"]):

				type=it['type']
				assert(type=="file") # TODO other cases

				filename=it['path']
				ext=os.path.splitext(filename)[1]

				try:
					with open(filename,mode='rb') as f:
						body=f.read()
						if ext==".json":
							metadata.append({'type':'json-object','filename': filename, 'object': json.loads(body)})
						else:
							encoded=base64.b64encode(body).decode('ascii') # this should work with streamable nexus data too! or any binary file not too big (i.e. without big 3d data )
							metadata.append({'type':'b64encode','filename' : filename,'encoded': encoded})
						
						logger.info(f"Read metadata type={type} filename={filename} ext={ext} body_c_size={len(body)}")
				except Exception as ex:
					logger.info(f"Reading of metadata file {filename} failed {ex}. Skipping it")

			# NOTE: this is dangerous but I have to do it: I need to remove all openvisus files in case I crashed in a middle of compression
			# e.g assuyming /mnt/data1/nsdf/tmp/near-field-scrgiorgio-20230912-01/visus.idx I need to clean up the parent directory
			# SO MAKE SURE you are using unique directories!
			src=row["src"]
			dst=row["dst"]

			if True:
				logger.info(f" DANGEROUS but needed: removing any file from {os.path.dirname(dst)}")
				shutil.rmtree(os.path.dirname(dst), ignore_errors=True)

			ConvertImageStack(row["src"], row["dst"], compression=row["compression"], arco=row["arco"])

			# i allow this to fail
			try:
				db.generateConfig(VISUS_CONVERT_CONFIG)
			except:
				logger.info(f"db.generateConfig('{VISUS_CONVERT_CONFIG}') failed, but ignoring. it may be fixed later")	

			# only when all successfull I can say it's done
			row=db.setConvertDone(row)

			out_msg={}
			out_msg["metadata"]=[{
				'type':'json-object',
				'filename': 'generated-nsdf-convert.json', 
				'object' : {k:str(v) for k,v in row.items() if k!="metadata"}
			}]
			out_msg["metadata"].extend(metadata)

			# TODO: what if I fail here?
			channel_out.basic_publish(exchange='', routing_key=CONVERT_QUEUE_OUT ,body=json.dumps(out_msg))
			print(f"PubSub published message to queue={CONVERT_QUEUE_OUT} body=\n{json.dumps(out_msg,indent=2)} ")
			print(f"Continuing loop...")

		logger.info(f"RunConvertLoop end")
		channel_in.close();connection_in.close()
		channel_out.close();connection_out.close()
		sys.exit(0)



