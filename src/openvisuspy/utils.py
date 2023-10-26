
import numpy as np
import os,sys,logging,asyncio,time,json,xmltodict

logger = logging.getLogger(__name__)

# ///////////////////////////////////////////////
def IsPyodide():
	return "pyodide" in sys.modules

# ///////////////////////////////////////////////
def IsJupyter():
	return hasattr(__builtins__,'__IPYTHON__') or 'ipykernel' in sys.modules

# ///////////////////////////////////////////////
def IsPanelServe():
	return "panel.command.serve" in sys.modules 

# ///////////////////////////////////////////////
def GetBackend():
	ret=os.environ.get("VISUS_BACKEND", "py" if IsPyodide() else "cpp")
	assert(ret=="cpp" or ret=="py")
	return ret

# ///////////////////////////////////////////////////////////////////
def Touch(filename):
	from pathlib import Path
	Path(filename).touch(exist_ok=True)

# ///////////////////////////////////////////////////////////////////
def LoadJSON(filename):
	with open(filename,"rt") as f:
		body=f.read()
	return json.loads(body) if body else {}	

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
			except Exception as ex:
				logger.info(f"ERROR {fn} : {ex}")
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
	stream=None, 
	log_filename:str=None, 
	logging_level=logging.INFO,
	fmt="[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)d:%(funcName)s] %(message)s",
	datefmt="%H%M%S"
	):

	if logger is None:
		logger=logging.getLogger("openvisuspy")

	logger.handlers.clear()
	logger.propagate=False

	logger.setLevel(logging_level)

	if stream != False:
		if stream is None or stream == True:
			handler=JupyterLoggingHandler() if IsJupyter() else logging.StreamHandler(stream=sys.stderr)
		else:
			handler=logging.StreamHandler(stream=stream)
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


import os,sys,logging, urllib
import urllib.request
from pprint import pprint

import bokeh
import bokeh.io 
import bokeh.io.notebook 
import bokeh.models.widgets  
import bokeh.core.validation
import bokeh.plotting
import bokeh.core.validation.warnings
import bokeh.layouts

from .utils import cbool

bokeh.core.validation.silence(bokeh.core.validation.warnings.EMPTY_LAYOUT, True)
bokeh.core.validation.silence(bokeh.core.validation.warnings.FIXED_SIZING_MODE,True)

logger = logging.getLogger(__name__)

# //////////////////////////////////////////////////////////////////////////////////////
def ShowBokehApp(app):
	
	# in JypyterLab/JupyterHub we need to tell what is the proxy url
	# see https://docs.bokeh.org/en/3.0.3/docs/user_guide/output/jupyter.html
	# example: 
	VISUS_USE_PUBLIC_IP=cbool(os.environ.get("VISUS_USE_PUBLIC_IP",False))

	# change this if you need ssh-tunneling
	# see https://github.com/sci-visus/OpenVisus/blob/master/docs/ssh-tunnels.md
	VISUS_SSH_TUNNELS=str(os.environ.get("VISUS_SSH_TUNNELS",""))
	
	logger.info(f"ShowBokehApp VISUS_USE_PUBLIC_IP={VISUS_USE_PUBLIC_IP} VISUS_SSH_TUNNELS={VISUS_SSH_TUNNELS}")
	
	if VISUS_SSH_TUNNELS:
		# change this if you need ssh-tunneling
		# see https://github.com/sci-visus/OpenVisus/blob/master/docs/ssh-tunnels.md    
		notebook_port,bokeh_port=VISUS_SSH_TUNNELS
		print(f"ShowBokehApp, enabling ssh tunnels notebook_port={notebook_port} bokeh_port={bokeh_port}")
		bokeh.io.notebook.show_app(app, bokeh.io.notebook.curstate(), f"http://127.0.0.1:{notebook_port}", port = bokeh_port) 
		
	elif VISUS_USE_PUBLIC_IP:
		# in JypyterLab/JupyterHub we may tell what is the proxy url
		# see https://docs.bokeh.org/en/3.0.3/docs/user_guide/output/jupyter.html         
		
		# retrieve public IP (this is needed for front-end browser to reach bokeh server)
		public_ip = urllib.request.urlopen('https://ident.me').read().decode('utf8')
		print(f"public_ip={public_ip}")    
		
		if "JUPYTERHUB_SERVICE_PREFIX" in os.environ:

			def GetJupyterHubNotebookUrl(port):
				if port is None:
					ret=public_ip
					print(f"GetJupyterHubNotebookUrl port={port} returning {ret}")
					return ret
				else:
					ret=f"https://{public_ip}{os.environ['JUPYTERHUB_SERVICE_PREFIX']}proxy/{port}"
					print(f"GetJupyterHubNotebookUrl port={port} returning {ret}")
					return ret     

			bokeh.io.show(app, notebook_url=GetJupyterHubNotebookUrl)
			
		else:
			# need the port (TODO: test), I assume I will get a non-ambiguos/unique port
			import notebook.notebookapp
			ports=list(set([it['port'] for it in notebook.notebookapp.list_running_servers()]))
			assert(len(ports)==1)
			port=ports[0]
			notebook_url=f"{public_ip}:{port}" 
			print(f"bokeh.io.show(app, notebook_url='{notebook_url}')")
			bokeh.io.show(app, notebook_url=notebook_url)
	else:
		bokeh.io.show(app) 
	  
# //////////////////////////////////////////////////////////////////////////////////////
def TestBokehApp(doc):
	button = bokeh.models.widgets.Button(label="Bokeh is working? Push...", sizing_mode='stretch_width')
	def OnClick(evt=None): button.label="YES!"
	button.on_click(OnClick)     
	doc.add_root(bokeh.layouts.column(button,sizing_mode='stretch_width') )  

# //////////////////////////////////////////////////////////////////////////////////////
def GetPanelApp(main_layout):
	import panel as pn
	from panel.template import DarkTheme
	ret  = pn.template.MaterialTemplate(
		title='Openvisus-Panel',
		site_url ="https://nationalsciencedatafabric.org/", 
		header_background="#303050", 
		theme=DarkTheme,
		logo ="https://www.sci.utah.edu/~pascucci/public/NSDF-smaller.PNG") 
	ret.main.append(main_layout) 
	return ret