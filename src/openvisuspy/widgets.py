import os,sys
import logging
import traceback

import panel as pn

logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////
class Widgets:

	@staticmethod
	def CheckBox(callback=None,**kwargs):
		ret=pn.widgets.Checkbox(**kwargs)
		def onChange(evt):
			if evt.old == evt.new or not callback: 
				return
			try:
				callback(evt.new)
			except:
				logger.info(traceback.format_exc())
				raise
		ret.param.watch(onChange,"value")
		return ret

	@staticmethod
	def RadioButtonGroup(callback=None,**kwargs):
		ret=pn.widgets.RadioButtonGroup(**kwargs)
		def onChange(evt):
			if evt.old == evt.new or not callback: 
				return
			try:
				callback(evt.new)
			except:
				logger.info(traceback.format_exc())
				raise
		ret.param.watch(onChange,"value")
		return ret

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
		def onChange(evt):
			if evt.old == evt.new or not callback: return
			try:
				callback(evt.new)
			except:
				logger.info(traceback.format_exc())
				raise
		return ret


	@staticmethod
	def Select(callback=None, **kwargs):
		ret = pn.widgets.Select(**kwargs) 
		def onChange(evt):
			if evt.old == evt.new or not callback: return
			try:
				callback(evt.new)
			except:
				logger.info(traceback.format_exc())
				raise
		ret.param.watch(onChange,"value")
		return ret

	@staticmethod
	def Slider(callback=None, type="int", parameter_name="value", editable=False, format="0.001",**kwargs):

		if type=="float":
			from bokeh.models.formatters import NumeralTickFormatter
			kwargs["format"]=NumeralTickFormatter(format=format)

		if "sizing_mode" not in kwargs:
			kwargs["sizing_mode"]="stretch_width"

		ret = {
			"int":   pn.widgets.EditableIntSlider   if editable else pn.widgets.IntSlider,
			"float": pn.widgets.EditableFloatSlider if editable else pn.widgets.FloatSlider,
			"discrte": pn.widgets.DiscreteSlider
		}[type](**kwargs) 
		def onChange(evt):
			if evt.old == evt.new or not callback: return
			try:
				callback(evt.new)
			except:
				logger.info(traceback.format_exc())
				raise
		ret.param.watch(onChange,parameter_name)
		return ret
	
	@staticmethod
	def RangeSlider(editable=False, type="float", format="0.001", callback=None, parameter_name="value", **kwargs):
		from bokeh.models.formatters import NumeralTickFormatter
		kwargs["format"]=NumeralTickFormatter(format=format)
		ret = {
			"float": pn.widgets.EditableRangeSlider if editable else pn.widgets.RangeSlider,
			"int":   pn.widgets.EditableIntSlider   if editable else pn.widgets.IntRangeSlider
		}[type](**kwargs)
		def onChange(evt):
			if evt.old == evt.new or not callback: return
			try:
				callback(evt.new)
			except:
				logger.info(traceback.format_exc())
				raise
		ret.param.watch(onChange,parameter_name)
		return ret
