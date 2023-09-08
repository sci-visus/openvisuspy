import os ,sys, time, logging,shutil,glob,json, string, random, argparse, shutil
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
				insert_time timestamp NOT NULL, 
				conversion_start timestep ,
				conversion_end   timestamp 
		)
		""")
		self.conn.commit()
	
	def pushPendingConvert(self, name, src, dst, compression, arco):
		# TODO: if multiple converters?
		self.conn.executemany("INSERT INTO datasets (name, src, dst, compression, arco, insert_time) values(?,?,?,?,?,?)",[
			(name, src, dst, compression, arco, datetime.now())
		])
		self.conn.commit()

	def popPendingConvert(self):
		# TODO: if multiple converters?
		data = self.conn.execute("SELECT * FROM datasets WHERE conversion_end is NULL order by id ASC LIMIT 1")
		row=data.fetchone()
		if row is None: 
			return None
		row={k:row[k] for k in row.keys()}
		data = self.conn.execute("UPDATE datasets SET conversion_start==? where id=?",(datetime.now(),row["id"], ))
		self.conn.commit()
		return row

	def setConvertDone(self, row):
		row["conversion_end"]=datetime.now()
		data = self.conn.execute("UPDATE datasets SET conversion_end==? where id=?",(row["conversion_end"],row["id"], ))
		self.conn.commit()
		return row

	def getAll(self):
		for row in self.conn.execute("SELECT * FROM datasets ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	def getConverted(self):
		for row in self.conn.execute("SELECT * FROM datasets WHERE conversion_end is not NULL ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

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

	logger.info(f"ConvertImageStack src={src} dst={dst} compression={compression} arco={arco} START")

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
	data=np.clip(data,0,70)
	data=data.astype(np.float32)

	m,M=np.min(data),np.max(data)
	D,H,W=data.shape
	logger.info(f"Image stack loaded in {time.time() - t1} seconds shape={data.shape} dtype={data.dtype} c_size={W*H*D*4:,} m={m} M={M}")
	D,H,W=data.shape

	# write uncompressed
	idx_filename=dst
	db=ov.CreateIdx(url=idx_filename, dims=[W,H,D], fields=[ov.Field("data",str(data.dtype),"row_major")], compression="raw", arco=arco)
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
	
	"""


	"""

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
				logger.info(f"Received body={body} ")
				msg=json.loads(body)
				logger.info(f"Pushing pending {msg}")
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
			else:
				logger.info(f"Popped pending {row}")
				ConvertImageStack(row["src"], row["dst"], compression=row["compression"], arco=row["arco"])
				row=db.setConvertDone(row)

			# i allow this to fail
			try:
				db.generateConfig(VISUS_CONVERT_CONFIG)
			except:
				pass	

			# nofify about the dataset ready (i.e. someone may want to run a dashboard)
			msg=json.dumps({k:str(v) for k,v in row.items()})
			channel_out.basic_publish(exchange='', routing_key=CONVERT_QUEUE_OUT ,body=msg)
			print(f"Published body={msg} queue={CONVERT_QUEUE_OUT}")

		logger.info(f"RunConvertLoop end")
		channel_in.close();connection_in.close()
		channel_out.close();connection_out.close()
		sys.exit(0)



