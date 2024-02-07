import os,sys
import logging
import traceback
import colorcet

logger = logging.getLogger(__name__)

import bokeh
import bokeh.models
import bokeh.events

from bokeh.models import LinearColorMapper,LogColorMapper,ColorBar,ColumnDataSource,Range1d
from bokeh.events import DoubleTap
from bokeh.plotting import figure as Figure
from bokeh.models.scales import LinearScale,LogScale

bokeh.core.validation.silence(bokeh.core.validation.warnings.EMPTY_LAYOUT, True)
bokeh.core.validation.silence(bokeh.core.validation.warnings.FIXED_SIZING_MODE,True)


# //////////////////////////////////////////////////////////////////////////////////////
# DEPRECATED
"""
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
	  
"""

import panel as pn
from panel import Column,Row,GridBox,Card
from panel.layout import FloatPanel
from panel.pane import HTML,JSON,Bokeh

from .utils import IsPyodide

# ///////////////////////////////////////////////////
def GetPalettes():
	ret = {}
	for name in bokeh.palettes.__palettes__:
		value=getattr(bokeh.palettes,name,None)
		if value and len(value)>=256:
			ret[name]=value

	for name in sorted(colorcet.palette):
		value=getattr(colorcet.palette,name,None)
		if value and len(value)>=256:
			# stupid criteria but otherwise I am getting too much palettes
			if len(name)>12: continue
			ret[name]=value

	return ret

# ////////////////////////////////////////////////////////
def ShowInfoNotification(msg):
	pn.state.notifications.info('Copy url done')

# ////////////////////////////////////////////////////////
def GetCurrentUrl():
	return pn.state.location.href

# //////////////////////////////////////////////////////////////////////////////////////
def GetQueryParams():
	return {k: v for k,v in pn.state.location.query_params.items()}


# ////////////////////////////////////////////////////////
def AddPeriodicCallback(fn, period, name="AddPeriodicCallback"):
	#if IsPyodide():
	#	return AddAsyncLoop(name, fn,period )  
	#else:
	return pn.state.add_periodic_callback(fn, period=period)

# ////////////////////////////////////////////////////////
class DisableCallbacks:
	
	def __init__(self, instance):
		self.instance=instance
	
	def __enter__(self):
		setattr(self.instance,"__disable_callbacks",True)

	def __exit__(self, type, value, traceback):
		setattr(self.instance,"__disable_callbacks",False)

# ////////////////////////////////////////////////////////
def CallIfNotDisabled(evt, instance, callback):
	if evt.old == evt.new or not callback or getattr(instance,"__disable_callbacks"): 
		return

	try:
		callback(evt.new)
	except:
		logger.info(traceback.format_exc())
		raise

# ////////////////////////////////////////////////////////
def AddCallback(ret, callback, parameter_name):
	setattr(ret,"__disable_callbacks",False)
	assert(getattr(ret,"__disable_callbacks")==False)
	ret.disable_callbacks=lambda ret=ret: DisableCallbacks(ret)
	ret.param.watch(lambda evt,ret=ret, callback=callback: CallIfNotDisabled(evt, ret, callback),parameter_name)
	return ret

# ////////////////////////////////////////////////////////
class Widgets:

	@staticmethod
	def CheckBox(callback=None,**kwargs):
		ret=pn.widgets.Checkbox(**kwargs)
		return AddCallback(ret, callback, "value")

	@staticmethod
	def RadioButtonGroup(callback=None,**kwargs):
		ret=pn.widgets.RadioButtonGroup(**kwargs)
		return AddCallback(ret, callback, "value")

	@staticmethod
	def Button(callback=None,**kwargs):
		ret = pn.widgets.Button(**kwargs)
		def onClick(evt):
			if not callback: return
			try:
				callback()
			except:
				logger.info(traceback.format_exc())
				raise
		ret.on_click(onClick)
		return ret

	@staticmethod
	def Input(callback=None, type="text", **kwargs):
		ret = {
			"text": pn.widgets.TextInput,
			"int": pn.widgets.IntInput,
			"float": pn.widgets.FloatInput
		}[type](**kwargs)
		return AddCallback(ret, callback, "value")


	@staticmethod
	def TextAreaInput(callback=None, type="text", **kwargs):
		ret = pn.widgets.TextAreaInput(**kwargs)
		return AddCallback(ret, callback, "value")

	@staticmethod
	def Select(callback=None, **kwargs):
		ret = pn.widgets.Select(**kwargs) 
		ret = AddCallback(ret, callback, "value")
		return ret

	@staticmethod
	def ColorMap(callback=None, **kwargs):
		ret = pn.widgets.ColorMap(**kwargs) 
		return AddCallback(ret, callback, "value_name")

	@staticmethod
	def FileInput(callback=None, **kwargs):
		ret = pn.widgets.FileInput(**kwargs)
		return AddCallback(ret, callback, "value")

	@staticmethod
	def FileDownload(*args, **kwargs):
		return pn.widgets.FileDownload(*args, **kwargs)

	@staticmethod
	def Slider(callback=None, type="int", parameter_name="value", editable=False, format="0.001",**kwargs):

		if type=="float":
			from bokeh.models.formatters import NumeralTickFormatter
			kwargs["format"]=NumeralTickFormatter(format=format)

		#if "sizing_mode" not in kwargs:
		#	kwargs["sizing_mode"]="stretch_width"

		ret = {
			"int":   pn.widgets.EditableIntSlider   if editable else pn.widgets.IntSlider,
			"float": pn.widgets.EditableFloatSlider if editable else pn.widgets.FloatSlider,
			"discrete": pn.widgets.DiscreteSlider
		}[type](**kwargs) 

		return AddCallback(ret, callback, parameter_name)
	
	@staticmethod
	def RangeSlider(editable=False, type="float", format="0.001", callback=None, parameter_name="value", **kwargs):
		from bokeh.models.formatters import NumeralTickFormatter
		kwargs["format"]=NumeralTickFormatter(format=format)
		ret = {
			"float": pn.widgets.EditableRangeSlider if editable else pn.widgets.RangeSlider,
			"int":   pn.widgets.EditableIntSlider   if editable else pn.widgets.IntRangeSlider
		}[type](**kwargs)

		return AddCallback(ret, callback, parameter_name)


	@staticmethod
	def MenuButton(callback=None, jsargs={}, jscallback=None, **kwargs):
		menu_value_js = pn.widgets.TextInput(visible=False)
		jsargs['menu']=menu_value_js

		def onMenuClick(evt):
				try:
					menu_value_js.value=evt.new
					fn=callback.get(evt.new,None) if callback else None
					if fn:
						logger.info(f"Executing {fn}")
						fn()
				except:
					logger.info(traceback.format_exc())
					raise
		ret = pn.widgets.MenuButton(**kwargs)
		ret.on_click(onMenuClick)

		if jscallback:
			ret.js_on_click(args=jsargs, code=jscallback)
		
		return pn.Row(ret, menu_value_js)
