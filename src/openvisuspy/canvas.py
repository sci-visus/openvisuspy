

import os,sys,logging
import numpy as np

from . utils import *

import bokeh
import bokeh.plotting
import bokeh.models 
import bokeh.events 

logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////////////////////////////////
class Canvas:
  
	# constructor
	def __init__(self, color_bar, color_mapper,sizing_mode='stretch_both', toolbar_location=None):
		self.sizing_mode=sizing_mode
		self.color_bar=color_bar
		self.color_mapper=color_mapper
		self.fig=bokeh.plotting.figure(active_scroll = "wheel_zoom") 
		self.fig.x_range = bokeh.models.Range1d(0,0)   
		self.fig.y_range = bokeh.models.Range1d(512,512) 
		self.fig.toolbar_location=toolbar_location
		self.fig.sizing_mode = self.sizing_mode
		# self.fig.add_tools(bokeh.models.HoverTool(tooltips=[ ("(x, y)", "($x, $y)"),("RGB", "(@R, @G, @B)")])) # is it working?

		# https://github.com/bokeh/bokeh/issues/9136
		# https://github.com/bokeh/bokeh/pull/9308
		self.on_resize=None
		self.last_width=0
		self.last_height=0
		self.fig.on_change('inner_width' , self.onResize)
		self.fig.on_change('inner_height', self.onResize)
  
		self.source_image = bokeh.models.ColumnDataSource(data={"image": [np.random.random((300,300))*255], "x":[0], "y":[0], "dw":[256], "dh":[256]})  
		self.fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh", color_mapper=self.color_mapper)  
		self.fig.add_layout(self.color_bar, 'right')
 
		self.points     = None
		self.dtype      = None

	# onResize
	def onResize(self,attr, old, new):
		w,h=self.getWidth(),self.getHeight()

		if w<=0 or h<=0:
			return 

		# getting spurious events with marginal changes (in particular with jupyter notebook)
		if self.last_width>0 and self.last_height>0:
			# is change too marginal?
			if abs(w-self.last_width)<=5 or abs(h-self.last_height)<5:
				return

		self.last_width =w
		self.last_height=h
		
		logger.info(f"Calling on_resize callback w={w} h={h}")
		if self.on_resize is not None:
			self.on_resize()

	# getWidth (this is number of pixels along X for the canvas)
	def getWidth(self):
		# https://docs.bokeh.org/en/2.4.3/docs/reference/models/plots.html
		#  This is the exact width of the plotting canvas, i.e. the width of
		# 	the actual plot, without toolbars etc. Note this is computed in a
		# 	web browser, so this property will work only in backends capable of			
		return self.fig.inner_width

	# getHeight (this is number of pixels along Y  for the canvas)
	def getHeight(self):
		return self.fig.inner_height

	# enableDoubleTap
	def enableDoubleTap(self,fn):
		self.fig.on_event(bokeh.events.DoubleTap, lambda evt: fn(evt.x,evt.y))

	  # getViewport
	def getViewport(self):
		return [
			self.fig.x_range.start,
			self.fig.y_range.start,
			self.fig.x_range.end,
			self.fig.y_range.end
		]

	  # getViewport
	def setViewport(self,x1,y1,x2,y2):
		if (x2<x1): x1,x2=x2,x1
		if (y2<y1): y1,y2=y2,y1

		W,H=self.getWidth(),self.getHeight()

		# fix aspect ratio
		if W>0 and H>0:
			assert(W>0 and H>0)
			w,cx =(x2-x1),x1+0.5*(x2-x1)
			h,cy =(y2-y1),y1+0.5*(y2-y1)
			if (w/W) > (h/H): 
				h=(w/W)*H 
			else: 
				w=(h/H)*W
			x1,y1=cx-w/2,cy-h/2
			x2,y2=cx+w/2,cy+h/2

		self.fig.x_range.start=x1
		self.fig.y_range.start=y1
		self.fig.x_range.end  =x2
		self.fig.y_range.end  =y2


	# renderPoints
	def renderPoints(self,points, size=20, color="red", marker="cross"):
		if self.points is not None: 
			self.fig.renderers.remove(self.points)
		self.points = self.fig.scatter(x=[p[0] for p in points], y=[p[1] for p in points], size=size, color=color, marker=marker)   
		assert self.points in self.fig.renderers


	# setImage
	def setImage(self, data, x1, y1, x2, y2):

		img=ConvertDataForRendering(data)
		dtype=img.dtype
 
		if self.dtype==dtype :
			# current dtype is 'compatible' with the new image dtype, just change the source _data
			self.source_image.data={"image":[img], "x":[x1], "y":[y1], "dw":[x2-x1], "dh":[y2-y1]}
		else:
			# need to create a new one from scratch
			self.fig.renderers=[]
			self.source_image = bokeh.models.ColumnDataSource(data={"image":[img], "x":[x1], "y":[y1], "dw":[x2-x1], "dh":[y2-y1]})
			if img.dtype==np.uint32:	
				self.image_rgba=self.fig.image_rgba("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh") 
			else:
				self.img=self.fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh", color_mapper=self.color_mapper) 
			self.dtype=img.dtype
