

import os,sys,logging,copy
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
	def __init__(self, id):
		self.id=id
		self.layout=bokeh.models.Row(sizing_mode="stretch_both")	
		self.on_double_tab = None
		self.on_resize=None
		self.__fig=None
		self.createFigure() 
		self.source_image = bokeh.models.ColumnDataSource(data={"image": [np.random.random((300,300))*255], "x":[0], "y":[0], "dw":[256], "dh":[256]})  
		self.last_renderer=self.__fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh")

	# createFigure
	def createFigure(self):
		old=self.__fig
		self.__fig=bokeh.plotting.figure(active_scroll = "wheel_zoom") 
		self.__fig.x_range = bokeh.models.Range1d(0,512) if old is None else old.x_range
		self.__fig.y_range = bokeh.models.Range1d(0,512) if old is None else old.y_range
		self.__fig.toolbar_location=None                 if old is None else old.toolbar_location
		self.__fig.sizing_mode = 'stretch_both'          if old is None else old.sizing_mode
		self.__fig.xaxis.axis_label  = "X"               if old is None else old.xaxis.axis_label
		self.__fig.yaxis.axis_label  = "Y"               if old is None else old.yaxis.axis_label

		if self.on_double_tab is not None:
			self.__fig.on_event(bokeh.events.DoubleTap, self.on_double_tab)		

		# TODO: keep the renderers but not the
		if old is not None:
			v=old.renderers
			old.renderers=[]
			for it in v:
				if it!=self.last_renderer:
					self.__fig.renderers.append(it)

		self.layout.children=[self.__fig]
		self.last_fig_width =0
		self.last_fig_height=0
		self.last_dtype   = None
		self.last_cb      = None
		self.last_renderer= None


	# getFigure
	def getFigure(self):
		return self.__fig

	# setAxisLabels
	def setAxisLabels(self,x,y):
		self.__fig.xaxis.axis_label  = x
		self.__fig.yaxis.axis_label  = y		

	# checkFigureResize
	def checkFigureResize(self):

		# huge problems with inner_ thingy ... HTML does not reflect real values
		# problems here, not getting real-time resizes
		# https://github.com/bokeh/bokeh/issues/9136
		# https://github.com/bokeh/bokeh/pull/9308
		# self.fig.on_change('inner_width' , self.onResize)
		# self.fig.on_change('inner_height', self.onResize)

		try:
			w=self.__fig.inner_width
			h=self.__fig.inner_height
		except Exception as ex:
			return
		
		if not w or not h: 
			return
		
		if w==self.last_fig_width and h==self.last_fig_height: 
			return

		# getting spurious events with marginal changes (in particular with jupyter notebook)
		# is change too marginal?
		if True:
			from .utils import IsJupyter
			max_x=self.last_fig_width *0.05 # 5% variation
			max_y=self.last_fig_height*0.05
			if all([
				# IsJupyter(),
				self.last_fig_width>0,
				self.last_fig_height>0,
				abs(w-self.last_fig_width )<=max_x,
				abs(h-self.last_fig_height)<=max_y
			]):
				return

		# logger.info("!!! RESIZE",self.last_width,self.last_fig_height,w,h)
		self.last_fig_width =w
		self.last_fig_height=h
		self.onResize()

	# onResize
	def onResize(self):
		if self.on_resize is not None:
			self.on_resize()

	# getWidth (this is number of pixels along X for the canvas)
	def getWidth(self):
		return self.last_fig_width

	# getHeight (this is number of pixels along Y  for the canvas)
	def getHeight(self):
		return self.last_fig_height

	# enableDoubleTap
	def enableDoubleTap(self,fn):
		self.on_double_tab=lambda evt: fn(evt.x,evt.y)
		self.__fig.on_event(bokeh.events.DoubleTap, self.on_double_tab)

	  # getViewport [[x1,x2],[y1,y2])
	def getViewport(self):
		return [
			[self.__fig.x_range.start, self.__fig.x_range.end],
			[self.__fig.y_range.start, self.__fig.y_range.end]
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

		logger.info(f"setViewport x1={x1} x2={x2} y1={y1} y2={y2} W={W} H={H}")
		self.__fig.x_range.start,self.__fig.x_range.end=x1,x2
		self.__fig.y_range.start,self.__fig.y_range.end=y1,y2

	# renderPoints
	#def renderPoints(self, points, size=20, color="red", marker="cross"):
	#	if self.points is not None: 
	#		self.__fig.renderers.remove(self.points)
	#	self.points = self.__fig.scatter(x=[p[0] for p in points], y=[p[1] for p in points], size=size, color=color, marker=marker)   
	#	assert self.points in self.__fig.renderers

	# getMainLayout
	def getMainLayout(self):
		return self.layout

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
				self.last_renderer=self.__fig.image_rgba("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh") 
			else:
				self.last_renderer=self.__fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh", color_mapper=color_bar.color_mapper) 

			self.__fig.add_layout(color_bar, 'right')
			self.last_dtype=img.dtype
			self.last_cb=color_bar
