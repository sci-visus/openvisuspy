import os,base64,logging, json

logger = logging.getLogger("nsdf-convert")

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
def LoadMetadataFromChess(query=None):
	"""
	python -m pip install chessdata-pyclient
	# modified /mnt/data1/nsdf/miniforge3/envs/my-env/lib/python3.9/site-packages/chessdata/__init__.py added at line 49 `verify=False`
	# otherwise I need a certificate `export REQUESTS_CA_BUNDLE=`
	"""

	uri=chessdata_uri=os.environ.get("NSDF_CONVERT_CHESSDATA_URI",None)
	import chessdata 
	records = chessdata.query(query,url=uri) 
	logger.info(f"Read CHESS metadata from uri={uri} CHESS query={query}] #records={len(records)}")

	return {
		'type':'json-object',
		'filename': '/dev/null', 
		'query'   : query,
		'records' : records,
	}

# //////////////////////////////////////////////////////////
def LoadMetadata(d):
	ret=[]
	for it in d:
		type=it['type']
		if type=="file":
			filename=it['path']
			try:
				ret.append(LoadMetadataFromFile(filename))
			except Exception as ex:
				logger.info(f"LoadMetadataFromFile filename={filename} failed {ex}. Skipping it")
		elif type=="chess-metadata":
			query=json.dumps(it['query'])
			try:
				ret.append(LoadMetadataFromChess(query))
			except Exception as ex:
				logger.info(f"LoadMetadataFromChess query={query} failed {ex}. Skipping it")
		else:
			raise Exception("todo")
		
	return ret