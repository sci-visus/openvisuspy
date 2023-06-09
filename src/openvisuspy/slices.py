
import os,sys,io,types,threading,time,logging
import numpy as np

from bokeh.models import Select,Column,Row
from bokeh.layouts import grid as Grid

from . widgets import Widgets
from . slice   import Slice

logger = logging.getLogger(__name__)

# //////////////////////////////////////////////////////////////////////////////////////
class Slices(Widgets):

	# constructor
	def __init__(self, 
			show_options=["num_views","palette","timestep","field","viewdep","quality"],
			slice_show_options=["direction","offset","viewdep","status_bar"],
			num_views=2):
		super().__init__()
		self.slice_show_options=slice_show_options
		self.central_layout=Column(sizing_mode='stretch_both')
		self.gui=self.createGui(central_layout=self.central_layout, options=show_options)
		self.setNumberOfViews(num_views)
	
	# setNumberOfViews
	def setNumberOfViews(self,value):
		super().setNumberOfViews(value)

		super().stop()
		self.children=[]
		for I in range(value):
			slice=Slice(show_options=self.slice_show_options) 
			self.children.append(slice)
  
		layouts=[it.gui for it in self.children]
		if value<=2:
			self.central_layout.children=[Row(*layouts, sizing_mode='stretch_both')]
		elif value==3:
			self.central_layout.children=[Row(layouts[2], Column(children=layouts[0:2],sizing_mode='stretch_both'),sizing_mode='stretch_both')]
		elif value==4:
			self.central_layout.children=[Grid(children=layouts,nrows=2, ncols=2, sizing_mode="stretch_both")]
		else:
			raise Exception("internal error")



