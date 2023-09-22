
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
	def __init__(self, 
			show_options=["num_views","palette","timestep","field","viewdep","quality"],
			slice_show_options=["direction","offset","viewdep"],
			cls=Slice
		):
		super().__init__()
		self.cls=cls
		self.slice_show_options=slice_show_options
		self.show_options=show_options
		self.central_layout=Column(sizing_mode='stretch_both')

	
	# getBokehLayout 
	# NOTE: doc is needed in case of jupyter notebooks, where curdoc() gives the wrong value
	def getBokehLayout(self, doc=None, sizing_mode=None, height=None, is_panel=False):

		if is_panel:
			import panel as pn
		else:
			import bokeh.io
			self.doc=bokeh.io.curdoc() if doc is None else doc

		from .utils import IsJupyter
		if IsJupyter():
			sizing_mode='stretch_width'
			if height is None: height=600
		else:
			sizing_mode='stretch_both'

		options=[it.replace("-","_") for it in self.show_options]

		first_row=[getattr(self.widgets,it) for it in options ]

		ret=Column(
			Row(*first_row,sizing_mode="stretch_width"),
			Row(
				self.central_layout,
				self.widgets.metadata, 
				sizing_mode='stretch_both'
			),
			sizing_mode=sizing_mode if not is_panel else 'stretch_both',
			height=height if not is_panel else None)

		if IsPyodide():
			self.idle_callbackAddAsyncLoop(f"{self}::onIdle (bokeh)",self.onIdle,1000//30)

		elif is_panel:
			self.idle_callback=pn.state.add_periodic_callback(self.onIdle, period=1000//30)
			self.panel_layout=pn.pane.Bokeh(ret,sizing_mode=sizing_mode, height=height)
			ret=self.panel_layout

		else:
			self.idle_callback=self.doc.add_periodic_callback(self.onIdle, 1000//30)

		self.start()

		# this will fill out the central_layout
		self.setNumberOfViews(self.getNumberOfViews())

		return ret


	# setNumberOfViews
	def setNumberOfViews(self,value):

		config=self.getConfig()

		super().stop()
		super().setNumberOfViews(value)

		# remove old children
		v=self.children
		logger.info(f"[{self.id}] deleting old children {[it.id for it in v]}")
		for it in v: del it

		self.children=[]
		for I in range(value):
			child=self.cls(self.slice_show_options) 
			self.children.append(child)
  
		layouts=[it.getBokehLayout() for it in self.children]
		if value<=2:
			self.central_layout.children=[
				Row(*layouts, sizing_mode='stretch_both')
			]

		elif value==3:
			self.central_layout.children=[
				Row(
					layouts[2], 
					Column(
						children=layouts[0:2],
						sizing_mode='stretch_both'
					),
					sizing_mode='stretch_both')
				]
			
		elif value==4:
			self.central_layout.children=[
				Grid(
					children=layouts,
					nrows=2, 
					ncols=2, 
					sizing_mode="stretch_both")	
				]
			
		else:
			raise Exception("internal error")
		
		self.setConfig(config)
		super().start()



