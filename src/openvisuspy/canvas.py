

import os,sys,logging,copy
import numpy as np

from .utils import *
from .widgets import *

logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////////////////////////////////
class Canvas:
  
	# constructor
	def __init__(self, id):
		self.id=id
		self.fig=None
		self.main_layout=Row(sizing_mode="stretch_both")	
		self.createFigure() 
		self.source_image = ColumnDataSource(data={"image": [np.random.random((300,300))*255], "x":[0], "y":[0], "dw":[256], "dh":[256]})  
		self.last_renderer=self.fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh")
		self.on_resize=None

		# since I cannot track consistently inner_width,inner_height (particularly on Jupyter) I am using a timer
		self.last_resize_width=0
		self.last_resize_height=0

		def CheckResize():
			W,H=self.getWidth(),self.getHeight()
			if W==0 or H==0: return
			if [W,H]==[self.last_resize_width,self.last_resize_height]: return
			self.last_resize_width,self.last_resize_height=[W,H]
			self.on_resize()
		AddPeriodicCallback(CheckResize,1000//30)
		

	# onDoubleTap
	def onDoubleTap(self,evt):
		pass

	# createFigure
	def createFigure(self):
		old=self.fig
		self.fig=Figure(active_scroll = "wheel_zoom") 
		self.fig.x_range = Range1d(0,512) if old is None else old.x_range
		self.fig.y_range = Range1d(0,512) if old is None else old.y_range
		self.fig.toolbar_location=None                 if old is None else old.toolbar_location
		self.fig.sizing_mode = 'stretch_both'          if old is None else old.sizing_mode
		self.fig.xaxis.axis_label  = "X"               if old is None else old.xaxis.axis_label
		self.fig.yaxis.axis_label  = "Y"               if old is None else old.yaxis.axis_label

		# if old: old_remove_on_event(DoubleTap, self.onDoubleTap) cannot find old_remove_on_event

		self.fig.on_event(DoubleTap, self.onDoubleTap)

		# TODO: keep the renderers but not the
		if old is not None:
			v=old.renderers
			old.renderers=[]
			for it in v:
				if it!=self.last_renderer:
					self.fig.renderers.append(it)

		self.main_layout[:]=[]
		self.main_layout.append(Bokeh(self.fig))
		
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
		W,H=self.getWidth(),self.getHeight()
		logger.debug(f"setViewport x1={x1} x2={x2} y1={y1} y2={y2} W={W} H={H} ")
		self.fig.x_range.start,self.fig.x_range.end=x1,x2
		self.fig.y_range.start,self.fig.y_range.end=y1,y2

	# setImage
	def setImage(self, data, x1, y1, x2, y2, color_bar):
		img=ConvertDataForRendering(data)
		dtype=img.dtype
		if self.last_dtype==dtype and self.last_cb==color_bar:
			# current dtype is 'compatible' with the new image dtype, just change the source _data
			self.source_image.data={"image":[img], "x":[x1], "y":[y1], "dw":[x2-x1], "dh":[y2-y1]}
		else:
			self.createFigure()
			self.source_image = ColumnDataSource(data={"image":[img], "x":[x1], "y":[y1], "dw":[x2-x1], "dh":[y2-y1]})
			if img.dtype==np.uint32:	
				self.last_renderer=self.fig.image_rgba("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh") 
			else:
				self.last_renderer=self.fig.image("image", source=self.source_image, x="x", y="y", dw="dw", dh="dh", color_mapper=color_bar.color_mapper) 
			self.fig.add_layout(color_bar, 'right')
			self.last_dtype=img.dtype
			self.last_cb=color_bar
