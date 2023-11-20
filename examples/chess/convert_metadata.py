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

	uri=chessdata_uri=os.environ["NSDF_CONVERT_CHESSDATA_URI"]
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
def LoadMetadata(value):

	ret=[]

	if not value:
		return ret

	# can be a JSON string
	if isinstance(value,str):
		value=json.loads(value) if len(value) else {}

	assert(isinstance(value,list))
	
	for it in value:
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