
import os,sys,io,types,threading,time,logging
import numpy as np

from bokeh.models import Select,Column,Row
from bokeh.layouts import grid as Grid

from . widgets import Widgets
from . slice   import Slice
from . utils   import IsPyodide, AddAsyncLoop

logger = logging.getLogger(__name__)

# //////////////////////////////////////////////////////////////////////////////////////
class Slices(Widgets):

	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None, cls=Slice):
		super().__init__(doc=doc, is_panel=is_panel, parent=parent)
		self.cls=cls
		self.show_options=["view_mode","palette","timestep","field","viewdep","quality"]
		self.slice_show_options=["direction","offset","viewdep"]
		self.central_layout=Column(sizing_mode='stretch_both')

	# getShowOptions
	def getShowOptions(self):
		return [self.show_options,self.slice_show_options]

	# setShowOptions
	def setShowOptions(self, value):
		if isinstance(value,tuple) or isinstance(value,list):
			self.show_options,self.slice_show_options=value
		else:
			self.show_otions,self.slice_show_options=value,None
		self.first_row_layout.children=[getattr(self.widgets,it.replace("-","_")) for it in self.show_options ] 

	# getMainLayout 
	# NOTE: doc is needed in case of jupyter notebooks, where curdoc() gives the wrong value
	def getMainLayout(self):

		self.first_row_layout.children=[getattr(self.widgets,it.replace("-","_")) for it in self.show_options ] 

		ret=Column(
			self.first_row_layout,
			Row(
				self.central_layout,
				self.widgets.metadata, 
				sizing_mode='stretch_both'
			),
			sizing_mode='stretch_both')

		if IsPyodide():
			self.idle_callbackAddAsyncLoop(f"{self}::onIdle (bokeh)",self.onIdle,1000//30)

		elif self.is_panel:
			import panel as pn
			self.idle_callback=pn.state.add_periodic_callback(self.onIdle, period=1000//30)
			if self.parent is None:
				self.panel_layout=pn.pane.Bokeh(ret,sizing_mode='stretch_both')
				ret=self.panel_layout

		else:
			self.idle_callback=self.doc.add_periodic_callback(self.onIdle, 1000//30)

		self.start()

		# this will fill out the central_layout
		view_mode=self.getViewMode()
		self.setViewMode(view_mode)

		return ret

	# setNumberOfViews (backward compatible)
	def setNumberOfViews(self, value):
		self.setViewMode(str(value))

	# setViewMode
	def setViewMode(self,value):

		config=self.getConfig()

		super().stop()
		super().setViewMode(value)

		# remove old children
		v=self.children
		logger.info(f"[{self.id}] deleting old children {[it.id for it in v]}")
		for it in v: del it
		
		def CreateChild():
			ret=self.cls(doc=self.doc, is_panel=self.is_panel, parent=self) 
			if self.slice_show_options is not None:
				ret.setShowOptions(self.slice_show_options)	
			return ret

		if value=="1":
			self.children=[CreateChild()]
			self.central_layout.children=[
				Row(self.children[0].getMainLayout(), sizing_mode='stretch_both')
			]

		elif value=="2":
			self.children=[CreateChild(),CreateChild()]
			self.central_layout.children=[
				Row(self.children[0].getMainLayout(),self.children[1].getMainLayout(), sizing_mode='stretch_both')
			]

		elif value=="4":
			self.children=[CreateChild(),CreateChild(),CreateChild(),CreateChild()]
			self.central_layout.children=[
				Grid(
					children=[self.children[I].getMainLayout() for I in range(4)],
					nrows=2, 
					ncols=2, 
					sizing_mode="stretch_both")	
				]
			
		else:
			raise Exception("internal error")
		
		self.setConfig(config)
		super().start()



