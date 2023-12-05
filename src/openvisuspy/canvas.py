

import os,sys,logging,copy
import numpy as np

from . utils import *

import bokeh

import panel as pn

logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////////////////////////////////
class Canvas:
  
	# constructor
	def __init__(self, id):
		self.id=id

		self.fig=None
		self.main_layout=pn.Row(sizing_mode="stretch_both")	
		self.createFigure() 
		self.source_image = bokeh.models.ColumnDataSource(data={"image": [np.random.random((300,300))*255], "x":[0], "y":[0], "dw":[256], "dh":[256]})  
		self.last_renderer=self.fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh")
		
	# onResize
	def onResize(self, attr, old, new):
		pass

	# onDoubleTap
	def onDoubleTap(self,evt):
		pass

	# createFigure
	def createFigure(self):
		old=self.fig
		self.fig=bokeh.plotting.figure(active_scroll = "wheel_zoom") 
		self.fig.x_range = bokeh.models.Range1d(0,512) if old is None else old.x_range
		self.fig.y_range = bokeh.models.Range1d(0,512) if old is None else old.y_range
		self.fig.toolbar_location=None                 if old is None else old.toolbar_location
		self.fig.sizing_mode = 'stretch_both'          if old is None else old.sizing_mode
		self.fig.xaxis.axis_label  = "X"               if old is None else old.xaxis.axis_label
		self.fig.yaxis.axis_label  = "Y"               if old is None else old.yaxis.axis_label


		from bokeh.events import DoubleTap

		if old: old.remove_on_change('inner_width'  , self.onResize)
		if old: old.remove_on_change('inner_height' , self.onResize)
		# if old: old_remove_on_event(bokeh.events.DoubleTap, self.onDoubleTap) cannot find old_remove_on_event

		self.fig.on_change('inner_width' , self.onResize)
		self.fig.on_change('inner_height', self.onResize) 
		self.fig.on_event(bokeh.events.DoubleTap, self.onDoubleTap)

		# TODO: keep the renderers but not the
		if old is not None:
			v=old.renderers
			old.renderers=[]
			for it in v:
				if it!=self.last_renderer:
					self.fig.renderers.append(it)

		self.main_layout[:]=[]
		self.main_layout.append(pn.pane.Bokeh(self.fig))
		
		self.last_dtype   = None
		self.last_cb      = None
		self.last_renderer= None

	# setAxisLabels
	def setAxisLabels(self,x,y):
		self.fig.xaxis.axis_label  = x
		self.fig.yaxis.axis_label  = y		


	# getWidth (this is number of pixels along X for the canvas)
	def getWidth(self):
		try:
			return self.fig.inner_width
		except:
			return 0

	# getHeight (this is number of pixels along Y  for the canvas)
	def getHeight(self):
		try:
			return self.fig.inner_height
		except:
			return 0

	  # getViewport [[x1,x2],[y1,y2])
	def getViewport(self):
		return [
			[self.fig.x_range.start, self.fig.x_range.end],
			[self.fig.y_range.start, self.fig.y_range.end]
		]

	  # setViewport
	def setViewport(self,value):
		(x1,x2),(y1,y2)=value
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

		logger.debug(f"setViewport x1={x1} x2={x2} y1={y1} y2={y2} W={W} H={H}")
		self.fig.x_range.start,self.fig.x_range.end=x1,x2
		self.fig.y_range.start,self.fig.y_range.end=y1,y2

	# renderPoints
	#def renderPoints(self, points, size=20, color="red", marker="cross"):
	#	if self.points is not None: 
	#		self.fig.renderers.remove(self.points)
	#	self.points = self.fig.scatter(x=[p[0] for p in points], y=[p[1] for p in points], size=size, color=color, marker=marker)   
	#	assert self.points in self.fig.renderers

	# setImage
	def setImage(self, data, x1, y1, x2, y2, color_bar):

		img=ConvertDataForRendering(data)
		dtype=img.dtype

		if self.last_dtype==dtype and self.last_cb==color_bar:
			# current dtype is 'compatible' with the new image dtype, just change the source _data
			self.source_image.data={"image":[img], "x":[x1], "y":[y1], "dw":[x2-x1], "dh":[y2-y1]}


			
		else:
			self.createFigure()
			self.source_image = bokeh.models.ColumnDataSource(data={"image":[img], "x":[x1], "y":[y1], "dw":[x2-x1], "dh":[y2-y1]})

			if img.dtype==np.uint32:	
				self.last_renderer=self.fig.image_rgba("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh") 
			else:
				self.last_renderer=self.fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh", color_mapper=color_bar.color_mapper) 

			self.fig.add_layout(color_bar, 'right')
			self.last_dtype=img.dtype
			self.last_cb=color_bar
