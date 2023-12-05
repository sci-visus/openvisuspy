import os,sys
import logging
import traceback

import panel as pn

logger = logging.getLogger(__name__)

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
			"discrte": pn.widgets.DiscreteSlider
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
