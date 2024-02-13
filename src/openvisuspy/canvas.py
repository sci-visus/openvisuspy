import os,sys,logging,copy,traceback,colorcet

import numpy as np
import types

logger = logging.getLogger(__name__)

import bokeh
import bokeh.models
import bokeh.events
import bokeh.plotting
import bokeh.models.callbacks

import panel as pn
from panel import Column,Row
from panel.pane import Bokeh

from .utils import *

class ViewportUpdate: 
	pass

# ////////////////////////////////////////////////////////////////////////////////////
class Canvas:
  
	# constructor
	def __init__(self, id):
		self.id=id
		self.fig=None
		self.fix_aspect_ratio=True

		# events
		self.events={
			bokeh.events.Tap: [],
			bokeh.events.DoubleTap: [],
			bokeh.events.SelectionGeometry: [],
			ViewportUpdate: []
		}

		self.fig_layout=Row(sizing_mode="stretch_both")	
		self.createFigure() 

		# since I cannot track consistently inner_width,inner_height (particularly on Jupyter) I am using a timer
		self.last_W=0
		self.last_H=0
		self.last_viewport=None
		self.setViewport([0,0,256,256])
		
		AddPeriodicCallback(self.onIdle,300)

	# onIdle
	def onIdle(self):
		
		# I need to wait until I get a decent size
		W,H=self.getWidth(),self.getHeight()
		if W==0 or H==0:  
			return

		# some zoom in/out or panning happened (handled by bokeh) 
		# note: no need to fix the aspect ratio in this case
		x=self.fig.x_range.start
		y=self.fig.y_range.start
		w=self.fig.x_range.end-x
		h=self.fig.y_range.end-y

		# nothing todo
		if [x,y,w,h]==self.last_viewport and [self.last_W,self.last_H]==[W,H]:
			return

		# I need to fix the aspect ratio 
		if self.fix_aspect_ratio and [self.last_W,self.last_H]!=[W,H]:
			x+=0.5*w
			y+=0.5*h
			if (w/W) > (h/H): 
				h=w*(H/W) 
			else: 
				w=h*(W/H)
			x-=0.5*w
			y-=0.5*h

		#if [(x1,x2),(y1,y2)]!=[(self.fig.x_range.start, self.fig.x_range.end),(self.fig.y_range.start, self.fig.y_range.end)]:
		self.fig.x_range.start, self.fig.x_range.end = x,x+w
		self.fig.y_range.start, self.fig.y_range.end = y,y+h
		self.last_W=W
		self.last_H=H
		self.last_viewport=[x,y,w,h]
		[fn(None) for fn in self.events[ViewportUpdate]]

	# on_event
	def on_event(self, evt, callback):
		self.events[evt].append(callback)

	# createFigure
	def createFigure(self):
		old=self.fig

		self.pan_tool               = bokeh.models.PanTool()
		self.wheel_zoom_tool        = bokeh.models.WheelZoomTool()
		self.box_select_tool        = bokeh.models.BoxSelectTool()
		self.box_select_tool_helper = bokeh.models.TextInput()

		self.fig=bokeh.plotting.figure(tools=[self.pan_tool,self.wheel_zoom_tool,self.box_select_tool]) 
		self.fig.toolbar_location="right" 
		self.fig.toolbar.active_scroll = self.wheel_zoom_tool
		self.fig.toolbar.active_drag    = self.pan_tool
		self.fig.toolbar.active_inspect = None
		self.fig.toolbar.active_tap     = None

		# try to preserve the old status
		self.fig.x_range = bokeh.models.Range1d(0,512) if old is None else old.x_range
		self.fig.y_range = bokeh.models.Range1d(0,512) if old is None else old.y_range
		self.fig.sizing_mode = 'stretch_both'          if old is None else old.sizing_mode
		self.fig.xaxis.axis_label  = "X"               if old is None else old.xaxis.axis_label
		self.fig.yaxis.axis_label  = "Y"               if old is None else old.yaxis.axis_label

		self.fig.on_event(bokeh.events.Tap      , lambda evt: [fn(evt) for fn in self.events[bokeh.events.Tap      ]])
		self.fig.on_event(bokeh.events.DoubleTap, lambda evt: [fn(evt) for fn in self.events[bokeh.events.DoubleTap]])

		# replace the figure from the fig_layout (so that later on I can replace it)
		self.fig_layout[:]=[]
		self.fig_layout.append(Bokeh(self.fig))
		
		self.enableSelection()

		self.last_renderer={}

	# enableSelection
	def enableSelection(self,use_python_events=False):
		if use_python_events:
			# python event DOES NOT work
			self.fig.on_event(bokeh.events.SelectionGeometry, lambda s: print("JHERE"))
		else:
			def handleSelectionGeometry(attr,old,new):
				j=json.loads(new)
				x,y=float(j["x0"]),float(j["y0"])
				w,h=float(j["x1"])-x,float(j["y1"])-y
				evt=types.SimpleNamespace()
				evt.new=[x,y,w,h]
				[fn(evt) for fn in self.events[bokeh.events.SelectionGeometry]]
				logger.info(f"HandleSeletionGeometry {evt}")

			self.box_select_tool_helper.on_change('value', handleSelectionGeometry)

			self.fig.js_on_event(bokeh.events.SelectionGeometry, bokeh.models.callbacks.CustomJS(
				args=dict(widget=self.box_select_tool_helper), 
				code="""
					console.log("Setting widget value for selection...");
					widget.value=JSON.stringify(cb_obj.geometry, undefined, 2);
					console.log("Setting widget value for selection DONE");
					"""
			))	

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

	# getViewport [(x1,x2),(y1,y2)]
	def getViewport(self):
		x=self.fig.x_range.start
		y=self.fig.y_range.start
		w=self.fig.x_range.end-x
		h=self.fig.y_range.end-y
		return [x,y,w,h]

	  # setViewport
	def setViewport(self,value):
		x,y,w,h=value
		self.last_W,self.last_H=0,0 # force a fix viewport
		self.fig.x_range.start, self.fig.x_range.end = x, x+w
		self.fig.y_range.start, self.fig.y_range.end = y, y+h
		# NOTE: the event will be fired inside onIdle


	# setImage
	def showData(self, data, viewport,color_bar=None):

		# 1D signal
		if len(data.shape)==1:
			self.fix_aspect_ratio=False
			self.fig.renderers.clear()
			xs=np.arange(x0,x1,(x1-x0)/signal.shape[0])
			ys=signal
			self.fig.line(xs,ys)
			
		# 2d image (eventually multichannel)
		else:	
			assert(len(data.shape) in [2,3])
			self.fix_aspect_ratio=True
			img=ConvertDataForRendering(data)
			dtype=img.dtype
			x,y,w,h=viewport
			
			# compatible with last rendered image?
			if all([
				self.last_renderer.get("source",None) is not None,
				self.last_renderer.get("dtype",None)==dtype,
				self.last_renderer.get("color_bar",None)==color_bar
			]):
				self.last_renderer["source"].data={"image":[img], "x":[x], "y":[y], "dw":[w], "dh":[h]}
			else:
				self.createFigure()
				source = bokeh.models.ColumnDataSource(data={"image":[img], "x":[x], "y":[y], "dw":[w], "dh":[h]})
				if img.dtype==np.uint32:	
					self.fig.image_rgba("image", source=source, x="x", y="y", dw="dw", dh="dh") 
				else:
					self.fig.image("image", source=source, x="x", y="y", dw="dw", dh="dh", color_mapper=color_bar.color_mapper) 
				self.fig.add_layout(color_bar, 'right')
				self.last_renderer={
					"source": source,
					"dtype":img.dtype,
					"color_bar":color_bar
				}







