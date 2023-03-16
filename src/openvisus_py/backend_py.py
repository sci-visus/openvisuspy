
import os,sys,requests, zlib,xmltodict,logging,urllib
import numpy as np
import types

from .backend import BaseDataset

logger = logging.getLogger(__name__)

# ///////////////////////////////////////////////////////////////////
class Aborted:
	
	# constructor
	def __init__(self):
		self.value=False
		self.response=None

	# setTrue
	def setTrue(self):
		self.value=True

		# https://stackoverflow.com/questions/16390243/closing-python-requests-connection-from-another-thread/16400574?noredirect=1#comment23529567_16400574
		if self.response is not None:
			try:
				self.response.connectionclose()
			except:
				pass


# ///////////////////////////////////////////////////////////////////
def ReadStats(reset=False):

	# TODO
	return {
		"io": {
			"r": 0,
			"w": 0,
			"n": 0,
		},
		"net":{
			"r": 0, 
			"w": 0,
			"n": 0,
		}
	}
	

# ///////////////////////////////////////////////////////////////////
class Dataset(BaseDataset):
	
	# constructor
	def __init__(self):
		pass
	
	# getUrl
	def getUrl(self):
		return self.url
	
	# getPointDim
	def getPointDim(self):
		return self.pdim

	# getLogicBox
	def getLogicBox(self):
		return self.logic_box

	# getMaxResolution
	def getMaxResolution(self):
		return self.max_resolution

	# getBitmask
	def getBitmask(self):
		return self.bitmask

	# getLogicSize
	def getLogicSize(self):
		return self.logic_size
	
	# getTimesteps
	def getTimesteps(self):
		return self.timesteps

	# getTimestep
	def getTimestep(self):
		return self.timesteps[0]

	# getFields
	def getFields(self):
		return [it['name'] for it in self.fields]

	# createAccess
	def createAccess(self):
		return None # I don't have the access

	# getField
	def getField(self,field=None):
		if field is None:
			return self.fields[0]['name']
		else:
			raise Exception("internal error")

	# getDatasetBody
	def getDatasetBody(self):
		return self.body
		
	# /////////////////////////////////////////////////////////////////////////////////

	# executeBoxQuery
	def executeBoxQuery(self,access, query, verbose=False):

		"""
		Links:

		- https://blog.jonlu.ca/posts/async-python-http
		- https://requests.readthedocs.io/en/latest/user/advanced/
		- https://lwebapp.com/en/post/pyodide-fetch
		- https://stackoverflow.com/questions/31998421/abort-a-get-request-in-python-when-the-server-is-not-responding
		- https://developer.mozilla.org/en-US/docs/Web/API/fetch#options
		- https://pyodide.org/en/stable/usage/packages-in-pyodide.html
		"""

		if not self.isQueryRunning(query):
			return

		H=query.end_resolutions[query.cursor]

		url=self.getUrl()
		timestep=query.timestep
		field=query.field
		logic_box=query.logic_box
		toh=H
		compression="zip"

		parsed=urllib.parse.urlparse(url)
		
		scheme=parsed.scheme
		path=parsed.path;assert(path=="/mod_visus")
		params=urllib.parse.parse_qs(parsed.query)
		
		for k,v in params.items():
			if isinstance(v,list):
				params[k]=v[0]
		
		# remove array in values
		params={k:(v[0] if isinstance(v,list)  else v) for k,v in params.items()}

		def SetParam(key,value):
			nonlocal params
			if not key in params:
				params[key]=value
		
		SetParam('action',"boxquery")
		SetParam('box'," ".join([f"{a} {b}" for a,b in zip(*logic_box)]).strip())
		SetParam('compression',compression)
		SetParam('field',field)
		SetParam('time',timestep)
		SetParam('toh',toh)
	
		if verbose:
			logger.info("Sending params={params.items()}")
			
		url=f"{scheme}://{parsed.netloc}{path}"

		# response=requests.get(url, stream=True, params=params)
		aborted=query.aborted
		if aborted.value: return None
		s=requests.Session()
		s.auth = ('user', 'pass')
		s.headers.update({'x-test': 'true'})
		response=s.get(url, params=params, verify=False, stream=True)
		aborted.response=response
			
		if aborted.value:
			print("!!!!!!!!!!!!! ABORTED AFTER",response.status_code)
			return None

		if response.status_code!=200:
			logger.info(f"!!!!!Got unvalid response {response.status_code}")
			return None

		try:
			body=response.raw.data
			# body=response.raw.getbuffer().tobytes() TODO
		except:
			logger.info(f"!!!!!Got unvalid response {aborted.value}")
			return None			

		if verbose:
			logger.info(f"Got body len={len(body)}")
			logger.info(f"response headers {response.headers.items()}")

		dtype= response.headers["visus-dtype"].strip()

		compression=response.headers["visus-compression"].strip()

		if compression=="raw" or compression=="":
			pass
		elif compression=="zip":
			body=zlib.decompress(body)
			if verbose:
				logger.info(f"data after decompression {type(body)} {len(body)}")
		else:
			raise Exception("internal error")
		
		nsamples=[int(it) for it in response.headers["visus-nsamples"].strip().split()]

		# example uint8[3]
		shape=list(reversed(nsamples))
		if "[" in dtype:
			assert dtype[-1]==']'
			dtype,N=dtype[0:-1].split("[")
			shape.append(int(N))

		if verbose:
			logger.info(f"numpy array dtype={dtype} shape={shape}")

		data=np.frombuffer(body,dtype=np.dtype(dtype)).reshape(shape)   

		# full-dimension
		return super().executeBoxQuery(access, query, data)



# /////////////////////////////////////////////////////////////////////////////////
def LoadDataset(url):
	
	# https otherwise http will be blocked as "unsafe" in the browser???
	assert(not url.startswith("https"))    
	
	response=requests.get(url,params={'action':'readdataset','format':'xml'}) 
	assert(response.status_code==200)
	body=response.text
	logger.info(f"Got response {body}")
	  
	def RemoveAt(cursor):
		if isinstance(cursor,dict):
			return {(k[1:] if k.startswith("@") else k):RemoveAt(v) for k,v in cursor.items()}
		elif isinstance(cursor,list):
			return [RemoveAt(it) for it in cursor]
		else:
			return cursor

	d=RemoveAt(xmltodict.parse(body)["dataset"]["idxfile"])
	# pprint(d)

	ret=Dataset()
	ret.url=url
	ret.body=body
	ret.bitmask=d["bitmask"]["value"]
	ret.pdim=3 if '2' in ret.bitmask else 2
	ret.max_resolution=len(ret.bitmask)-1

	# logic_box (X1 X2 Y1 Y2 Z1 Z2)
	v=[int(it) for it in d["box"]["value"].strip().split()]
	p1=[v[I] for I in range(0,len(v),2)]
	p2=[v[I] for I in range(1,len(v),2)]
	ret.logic_box=[p1,p2]
	
	# logic_size
	ret.logic_size=[(b-a) for a,b in zip(p1,p2)]

	# timesteps
	ret.timesteps=[]
	v=d["timestep"]
	if not isinstance(v,list): v=[v]
	for T,timestep in enumerate(v):
		if "when" in timestep:
			ret.timesteps.append(int(timestep["when"]))
		else:
			assert("from" in timestep)
			for T in range(int(timestep["from"]),int(timestep["to"]),int(timestep["step"])):
				ret.timesteps.append(T)

	# fields
	v=d["field"]
	if not isinstance(v,list):
		v=[v]
	ret.fields=[{"name":field["name"],"dtype": field["dtype"]} for field in v]
	
	logger.info(str({
			"url":ret.url,
			"bitmask":ret.bitmask,
			"pdim":ret.pdim,
			"max_resolution":ret.max_resolution,
			"timesteps": ret.timesteps,
			"fields":ret.fields,
			"logic_box":ret.logic_box,
			"logic_size":ret.logic_size,
		}))
	

	return ret



