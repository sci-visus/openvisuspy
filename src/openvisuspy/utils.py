
import numpy as np
import os,sys,logging,asyncio,time,json,xmltodict,urllib
import urllib.request
import boto3
import urllib.parse 
import sys, contextlib, urllib
from urllib.parse import urlencode          
from urllib.request import urlopen
	

import requests
from requests.auth import HTTPBasicAuth

import urllib3
urllib3.disable_warnings()

from pprint import pprint

logger = logging.getLogger(__name__)

COLORS = ["red", "lime", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"]

DEFAULT_PALETTE= "Turbo256"

import colorcet

import bokeh
import bokeh.core
import bokeh.core.validation

bokeh.core.validation.silence(bokeh.core.validation.warnings.EMPTY_LAYOUT, True)
bokeh.core.validation.silence(bokeh.core.validation.warnings.FIXED_SIZING_MODE,True)

import panel as pn

# ////////////////////////////////////////////////////////
def SafeCallback(fn):
	def ReturnValue(evt):
		try:
			fn(evt)
		except:
			logger.error(traceback.format_exc())
			raise
	return ReturnValue


# ///////////////////////////////////////////////
def IsPyodide():
	return "pyodide" in sys.modules

# ///////////////////////////////////////////////
def IsJupyter():
	return hasattr(__builtins__,'__IPYTHON__') or 'ipykernel' in sys.modules

# ///////////////////////////////////////////////
def IsPanelServe():
	return "panel.command.serve" in sys.modules 



# ///////////////////////////////////////////////////////////////////
def Touch(filename):
	from pathlib import Path
	Path(filename).touch(exist_ok=True)

# ///////////////////////////////////////////////////////////////////
def LoadJSON(value):

	# already a good json
	if isinstance(value,dict):
		return value

	# remote file (maybe I need to setup credentials)
	if value.startswith("http"):
		url=value
		username = os.environ.get("MODVISUS_USERNAME", "")
		password = os.environ.get("MODVISUS_PASSWORD", "")
		auth = None
		if username and password: 
			auth = HTTPBasicAuth(username, password) if username else None
		response = requests.get(url, auth=auth)
		try:
			body = response.body.decode('utf-8') 
		except:
			body = response.content.decode('utf-8') 
		return json.loads(body)
	
	if os.path.isfile(value):
		url=value
		with open(url, "r") as f:  body=f.read()
		return json.loads(body)
		
	elif isinstance(value,str):
		body=value
		return json.loads(body)

	raise Exception(f"{value} not supported")

# ///////////////////////////////////////////////////////////////////
def DownloadObject(src,dst, aws_access_key_id='any',aws_secret_access_key='any', endpoint_url='https://maritime.sealstorage.io/api/v0/s3'):
    if os.path.isfile(dst): return
    print(f"DownloadObject {src} -> {dst}")
    assert(src.startswith("s3://"))
    session = boto3.session.Session()
    s3_client = session.client(
        service_name='s3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        endpoint_url=endpoint_url, 
        verify=False
    )
    __bucket,__name=src[len("s3://"):].split("/",maxsplit=1)
    os.makedirs(os.path.dirname(dst),exist_ok=True)
    s3_client.download_file(__bucket,__name,dst) 

# ///////////////////////////////////////////////////////////////////
def DownloadFile(url, cache_dir=os.environ.get("VISUS_CACHE",os.path.expanduser("~/visus/cache")),verify=False):

	os.makedirs(cache_dir,exist_ok=True)
	logger.info(f"downloading url={url} verify={verify}")

	if not url.startswith("http"):
		return url # already local
		
	# need to download trhe file
	parsed=urllib.parse.urlparse(url)
	q=urllib.parse.parse_qs(parsed.query)
	endpoint_url=os.environ.get("AWS_ENDPOINT_URL",q.get("endpoint_url",[""])[0])

	default_ports={"http":80,"https":443}
	local_filename=os.path.join(cache_dir,f"{parsed.scheme}/{parsed.hostname}/{parsed.port if parsed.port else default_ports[parsed.scheme]}{parsed.path}")

	if os.path.isfile(local_filename):
		logger.info(f"Using cached file for url={url} local_filename={local_filename}")
		return local_filename

	if endpoint_url:
		profile=os.environ.get("AWS_PROFILE",q.get("profile",[None])[0])
		bucket_name,key=url[len(endpoint_url)+1:].split("?")[0].split("/",maxsplit=1)
		assert("access_key" not in q) # TODO, for now use the profile
		assert("secret_key" not in q)

		session=boto3.session.Session(profile_name=profile)
		resource=session.resource('s3', endpoint_url=endpoint_url,verify=verify)
		bucket = resource.Bucket(bucket_name)
		os.makedirs(os.path.dirname(local_filename),exist_ok=True)
		bucket.download_file(key,local_filename)
	else:
		from urllib.request import urlretrieve
		urlretrieve(url, local_filename)

	return local_filename
# ///////////////////////////////////////////////////////////////////
import OpenVisus as ov

def PointToPyList(value):
	return [value[I] for I in range(value.getPointDim())]

def BoxToPyList(value):
	return [PointToPyList(value.p1),PointToPyList(value.p2)]

# ///////////////////////////////////////////////////////////////////
def SaveJSON(filename,d):
	with open(filename,"wt") as fp:
		json.dump(d, fp, indent=2)	

# ///////////////////////////////////////////////////////////////////
def LoadXML(filename):
	with open(filename, 'rt') as file: 
		body = file.read() 
	return xmltodict.parse(body, process_namespaces=True) 	

# ///////////////////////////////////////////////////////////////////
def SaveFile(filename,body):
	with open(filename,"wt") as f:
		f.write(body)


# ///////////////////////////////////////////////////////////////////
def SaveXML(filename,d):
	body=xmltodict.unparse(d, pretty=True)
	SaveFile(filename,body)

# ///////////////////////////////////////////////
async def SleepMsec(msec):
	await asyncio.sleep(msec/1000.0)

# ///////////////////////////////////////////////
def AddAsyncLoop(name, fn, msec):

	# do I need this?
	if False and not IsPyodide():
		loop = asyncio.get_event_loop()
		if loop is None:
			logger.info(f"Setting new event loop")
			loop=asyncio.new_event_loop() 
			asyncio.set_event_loop(loop)

	async def MyLoop():
		t1=time.time()
		while True:

			# it's difficult to know what it running or not in the browser
			if IsPyodide():
				if (time.time()-t1)>5.0:
					logger.info(f"{name} is alive...")
					t1=time.time()
			try:
				await fn()
			except:
				logger.error(f"\n\n# ****************** ERROR {fn} : {traceback.format_exc()}")
			await SleepMsec(msec)

	return asyncio.create_task(MyLoop())


# ////////////////////////////////////////////////////////////////////////////////////////////////////////////
def RunAsync(coroutine_object):
	try:
		return asyncio.run(coroutine_object)
	except RuntimeError:
		pass

	import nest_asyncio
	nest_asyncio.apply()
	return asyncio.run(coroutine_object)

# //////////////////////////////////////////////////////////////////////////////////////
def cdouble(value):
	try:
		return float(value)
	except:
		return 0.0



# ///////////////////////////////////////////////////////////////////
def cbool(value):
	if isinstance(value,bool):
		return value

	if isinstance(value,int) or isinstance(value,float):
		return bool(value)

	if isinstance(value, str):
		return value.lower().strip() in ['true', '1']
	 
	raise Exception("not supported")


# ///////////////////////////////////////////////////////////////////
def IsIterable(value):
	try:
		iter(value)
		return True
	except:
		return False

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////
def Clamp(value,a,b):
	assert a<=b
	if value<a: value=a
	if value>b: value=b
	return value

# ///////////////////////////////////////////////////////////////////
def HumanSize(size):
	KiB,MiB,GiB,TiB=1024,1024*1024,1024*1024*1024,1024*1024*1024*1024
	if size>TiB: return "{:.2f}TiB".format(size/TiB) 
	if size>GiB: return "{:.2f}GiB".format(size/GiB) 
	if size>MiB: return "{:.2f}MiB".format(size/MiB) 
	if size>KiB: return "{:.2f}KiB".format(size/KiB) 
	return str(size)

# ////////////////////////////////////////////////////////////////
class JupyterLoggingHandler(logging.Handler):

	def __init__(self, stream=None):
		logging.Handler.__init__(self)
		self.stream = sys.__stdout__

	def flush(self):
		self.acquire()
		try:
			if self.stream and hasattr(self.stream, "flush"):
					self.stream.flush()
		finally:
			self.release()

	def emit(self, record):
		try:
			msg = self.format(record)
			msg = msg.replace('"',"'")
			stream = self.stream
			stream.write(msg + "\n")

			# it's producing some output to jupyter lab ... to solve
			if False:
				from IPython import get_ipython
				msg=msg.replace("\n"," ") # weird, otherwise javascript fails
				get_ipython().run_cell(f""" %%javascript\nconsole.log("{msg}");""")
				self.flush()
		except :
			# self.handleError(record)
			pass # just ignore

	def setStream(self, stream):
			raise Exception("internal error")
		

# ////////////////////////////////////////////////////////////////
def SetupLogger(
	logger=None, 
	log_filename:str=None, 
	logging_level=logging.INFO,
	fmt="%(asctime)s %(levelname)s %(filename)s:%(lineno)d:%(funcName)s %(message)s",
	datefmt="%Y-%M-%d- %H:%M:%S"
	):

	if logger is None:
		logger=logging.getLogger("openvisuspy")

	logger.handlers.clear()
	logger.propagate=False

	logger.setLevel(logging_level)
	handler=logging.StreamHandler(stream=sys.stderr)
	handler.setLevel(logging_level)
	handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
	logger.addHandler(handler)	
	
	# file
	if log_filename:
		os.makedirs(os.path.dirname(log_filename),exist_ok=True)
		handler=logging.FileHandler(log_filename)
		handler.setLevel(logging_level)
		handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
		logger.addHandler(handler)

	return logger



# ////////////////////////////////////////////////////////////////
def SetupJupyterLogger(
	logger=None, 
	logging_level=logging.INFO,
	fmt="%(asctime)s %(levelname)s %(filename)s:%(lineno)d:%(funcName)s %(message)s",
	datefmt="%Y-%M-%d- %H:%M:%S"
	):

	if logger is None:
		logger=logging.getLogger("openvisuspy")

	logger.handlers.clear()
	logger.propagate=False

	logger.setLevel(logging_level)
	handler=JupyterLoggingHandler()
	handler.setLevel(logging_level)
	handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
	logger.addHandler(handler)	
	
	return logger


# ///////////////////////////////////////////////////
def SplitChannels(array):
	return [array[...,C] for C in range(array.shape[-1])]

# ///////////////////////////////////////////////////
def InterleaveChannels(v):
	N=len(v)
	if N==0:
		raise Exception("empty image")
	if N==1: 
		return v[0]
	else:
		ret=np.zeros(v[0].shape + (N,), dtype=v[0].dtype)
		for C in range(N): 
			ret[...,C]=v[C]
		return ret 


# ///////////////////////////////////////////////////
def ConvertDataForRendering(data, normalize_float=True):
	 
	height,width=data.shape[0],data.shape[1]

	# typycal case
	if data.dtype==np.uint8:

		# (height,width)::uint8... grayscale, I will apply the colormap
		if len(data.shape)==2:
			Gray=data
			return Gray 

		# (height,depth,channel)
		if len(data.shape)!=3:
			raise Exception(f"Wrong dtype={data.dtype} shape={data.shape}")

		channels=SplitChannels(data)

		if len(channels)==1:
			Gray=channels[0]
			return Gray

		if len(channels)==2:
			G,A=channels
			return  InterleaveChannels([G,G,G,A]).view(dtype=np.uint32).reshape([height,width]) 
	
		elif len(channels)==3:
			R,G,B=channels
			A=np.full(channels[0].shape, 255, np.uint8)
			return  InterleaveChannels([R,G,B,A]).view(dtype=np.uint32).reshape([height,width]) 

		elif len(channels)==4:
			R,G,B,A=channels
			return InterleaveChannels([R,G,B,A]).view(dtype=np.uint32).reshape([height,width]) 
		
	else:

		# (height,depth) ... I will apply matplotlib colormap 
		if len(data.shape)==2:
			G=data.astype(np.float32)
			return G
		
		# (height,depth,channel)
		if len(data.shape)!=3:
			raise Exception(f"Wrong dtype={data.dtype} shape={data.shape}")  
	
		# convert all channels in float32
		channels=SplitChannels(data)
		channels=[channel.astype(np.float32) for channel in channels]

		if normalize_float:
			for C,channel in enumerate(channels):
				m,M=np.min(channel),np.max(channel)
				channels[C]=(channel-m)/(M-m)

		if len(channels)==1:
			G=channels[0]
			return G

		if len(channels)==2:
			G,A=channels
			return InterleaveChannels([G,G,G,A])
	
		elif len(channels)==3:
			R,G,B=channels
			A=np.full(channels[0].shape, 1.0, np.float32)
			return InterleaveChannels([R,G,B,A])

		elif len(channels)==4:
			R,G,B,A=channels
			return InterleaveChannels([R,G,B,A])
	
	raise Exception(f"Wrong dtype={data.dtype} shape={data.shape}") 




# ///////////////////////////////////////////////////
def GetPalettes():
	ret = {}
	for name in bokeh.palettes.__palettes__:
		colors=getattr(bokeh.palettes,name,None)
		if colors and len(colors)>=256:
			ret[name]=colors

	if True:
		for name in sorted(colorcet.palette):
			if name.startswith("CET_") or len(name)>20: continue # stupid criteria but otherwise I am getting too much palettes
			colors=getattr(colorcet.palette,name,None)
			if colors and len(colors)>=256:
				ret[name]=colors
	return ret

# ////////////////////////////////////////////////////////
def ShowInfoNotification(msg):  
    pn.state.notifications.clear() # DO I need this?
    pn.state.notifications.info(msg)

# ////////////////////////////////////////////////////////
def GetCurrentUrl():
	return pn.state.location.href


# ////////////////////////////////////////////////////////
import traceback

def CallPeriodicFunction(fn):
	try:
		fn()
	except:
		logger.error(traceback.format_exc())

def AddPeriodicCallback(fn, period, name="AddPeriodicCallback"):
	#if IsPyodide():
	#	return AddAsyncLoop(name, fn,period )  
	#else:

	return pn.state.add_periodic_callback(lambda fn=fn: CallPeriodicFunction(fn), period=period)


# //////////////////////////////////////////////////////
def GetShortUrl(url):
	request_url = 'http://tinyurl.com/api-create.php?' + urllib.parse.urlencode({'url':url})   
	with contextlib.closing(urllib.request.urlopen(request_url)) as response:   
		return response.read().decode('utf-8 ') 
