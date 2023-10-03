
import os,sys,io,types,threading,time,logging
import numpy as np

from bokeh.models import Select,Column,Row
from bokeh.layouts import grid as Grid

from . widgets import Widgets
from . slice   import Slice
from . utils   import IsPyodide, AddAsyncLoop

from bokeh.models import TabPanel,Tabs, Button,Column, Div

logger = logging.getLogger(__name__)

# //////////////////////////////////////////////////////////////////////////////////////
class Slices(Widgets):

	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None, cls=Slice):
		super().__init__(doc=doc, is_panel=is_panel, parent=parent)
		self.cls=cls
		self.show_options=["palette","timestep","field","viewdep","quality"]
		self.slice_show_options=["direction","offset","viewdep"]

		# view_mode
		self.widgets.view_mode=Tabs(tabs=[
			TabPanel(child=Column(sizing_mode="stretch_both"),title="1"),
			TabPanel(child=Column(sizing_mode="stretch_both"),title="2"),
			TabPanel(child=Column(sizing_mode="stretch_both"),title="probe"),
			TabPanel(child=Column(sizing_mode="stretch_both"),title="4"),
			],
			sizing_mode="stretch_both")
		self.widgets.view_mode.on_change("active", lambda attr, old, new: self.setViewMode(self.widgets.view_mode.tabs[new].title)) 


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
	def getMainLayout(self):

		options=[it.replace("-","_") for it in self.show_options]
		self.first_row_layout.children=[getattr(self.widgets,it) for it in options]

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

		# this will fill out the layout
		self.setViewMode(self.getViewMode())

		return self.widgets.view_mode

	# getViewMode
	def getViewMode(self):
		tab=self.widgets.view_mode.tabs[self.widgets.view_mode.active]
		return tab.title

	# createChild
	def createChild(self, extra_options=[]):
		ret=self.cls(doc=self.doc, is_panel=self.is_panel, parent=self) 
		if self.slice_show_options is not None:
			ret.setShowOptions(self.slice_show_options + extra_options)	
		return ret

	# setViewMode
	def setViewMode(self, value):
		logger.info(f"[{self.id}] value={value}")		

		tabs=self.widgets.view_mode.tabs
		inner=None
		for I,tab in enumerate(tabs):
			if tab.title==value:
				self.widgets.view_mode.active=I
				inner=tab.child
				break

		if not inner:
			return
		
		config=self.getConfig()
		super().stop()

		# remove old children
		v=self.children
		logger.info(f"[{self.id}] deleting old children {[it.id for it in v]}")
		for it in v: del it

		# empty all tabs
		for tab in self.widgets.view_mode.tabs:
			tab.child.children=[]


		if value=="1":
			self.children=[self.createChild()]
			central=Row(self.children[0].getMainLayout(), sizing_mode="stretch_both")

		elif value=="2":
			self.children=[self.createChild(extra_options=["link"]),self.createChild()]
			central=Row(self.children[0].getMainLayout(),self.children[1].getMainLayout(), sizing_mode="stretch_both")

		elif "probe" in value:
			child=self.createChild()
			child.setProbeVisible(True)
			self.children=[child]
			central=Row(self.children[0].getMainLayout(), sizing_mode="stretch_both")			

		elif value=="4":
			self.children=[self.createChild(),self.createChild(),self.createChild(),self.createChild()]
			central=Grid(children=[self.children[I].getMainLayout() for I in range(4)],nrows=2, ncols=2, sizing_mode="stretch_both")
			
		else:
			raise Exception("internal error")
		
		inner.children=[
			Row(
					Column(
						self.first_row_layout,
						central,
						sizing_mode='stretch_both'
					),
					self.widgets.metadata, 
					sizing_mode='stretch_both'
			)
		]

		self.setConfig(config)
		super().start()


	# setNumberOfViews (backward compatible)
	def setNumberOfViews(self, value):
		self.setViewMode(str(value))

