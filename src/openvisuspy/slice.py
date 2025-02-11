import os,sys,logging,copy,traceback,colorcet

import bokeh.models
import base64
import types
import logging
import copy
import traceback
import io 
import threading
import time
from urllib.parse import urlparse, urlencode

import numpy as np

import bokeh
import bokeh.models
from bokeh.models import Button, CustomJS
import bokeh.events
import bokeh.plotting
import bokeh.models.callbacks
from bokeh.models import LinearColorMapper, ColorBar
from bokeh.plotting import figure
import param 

import panel as pn
from panel.layout import FloatPanel
from panel import Column,Row,GridBox,Card
from panel.pane import HTML,JSON,Bokeh

from .utils   import *
from .backend import Aborted,LoadDataset,ExecuteBoxQuery

from .show_details import ShowDetails

logger = logging.getLogger(__name__)


# ////////////////////////////////////////////////////////////////////////////////////
class Canvas:
  
	# constructor
	def __init__(self, id, ViewChoice=None):
		self.id=id # A unique identifier
		self.view_choice = ViewChoice # View Selection
		self.fig=None # A Bokeh figure for plotting.
		self.pdim=2 # point dimension
		self.events={} # Event handling supporting various kinds of interactions

		self.box_select_tool_helper = bokeh.models.TextInput(visible=False)
		self.fig_layout=Row(sizing_mode="stretch_both")	

		self.createFigure() # Creates the main figure using Bokeh and adds

		# since I cannot track consistently inner_width,inner_height (particularly on Jupyter) I am using a timer
		self.setViewport([0,0,256,256])

		

	

	# onFigureSizeChange
	def onFigureSizeChange(self, __attr, __old, __new):
		self.setViewport(self.getViewport())

	# __fixAspectRatioIfNeeded
	def __fixAspectRatioIfNeeded(self, value):

		W=self.getWidth()
		H=self.getHeight()
		

		# does not apply to 1d signal
		if self.pdim==2 and W>0 and H>0:
			x,y,w,h=value
			cx=x+0.5*w 
			cy=y+0.5*h
			ratio=W/H
			w,h=(w,w/ratio) if (w/W) > (h/H) else (h*ratio,h)
			x1=cx-0.5*w
			y1=cy-0.5*h
			value=(x1,y1,w,h)
		
		
		return value

	# onIdle
	def onIdle(self):
		pass

	# on_event
	def on_event(self, evt, callback):
		if not evt in self.events:
			self.events[evt]=[]
		self.events[evt].append(callback)

	# createFigure
	def createFigure(self):
		old=self.fig

		self.pan_tool               = bokeh.models.PanTool()
		self.wheel_zoom_tool        = bokeh.models.WheelZoomTool()
		self.box_select_tool        = bokeh.models.BoxSelectTool()
		self.reset_fig              = bokeh.models.ResetTool()
		self.box_zoom_tool          = bokeh.models.BoxZoomTool()


		if self.view_choice  == "SYNC_VIEW": # sync_view bokeh options
			self.fig=bokeh.plotting.figure(tools=[self.pan_tool,self.reset_fig,self.wheel_zoom_tool,self.box_zoom_tool])

		else:
			self.fig=bokeh.plotting.figure(tools=[self.pan_tool,self.reset_fig,self.wheel_zoom_tool,self.box_select_tool,self.box_zoom_tool])

		self.fig.toolbar_location="right" 
		self.fig.toolbar.active_scroll  = self.wheel_zoom_tool
		self.fig.toolbar.active_drag    = self.pan_tool
		# self.fig.toolbar.active_inspect = self.over_tool #will bring this back
		self.fig.toolbar.active_tap     = None
		# self.fig.toolbar.

		# try to preserve the old status
		self.fig.x_range = bokeh.models.Range1d(0,512) if old is None else old.x_range
		self.fig.y_range = bokeh.models.Range1d(0,512) if old is None else old.y_range



		self.fig.sizing_mode = 'stretch_both'          if old is None else old.sizing_mode
		self.fig.yaxis.axis_label  = "Y"               if old is None else old.xaxis.axis_label
		self.fig.xaxis.axis_label  = "X"               if old is None else old.yaxis.axis_label

		self.fig.on_event(bokeh.events.Tap      ,      lambda evt: [fn(evt) for fn in self.events.get(bokeh.events.Tap,[]) ])
		self.fig.on_event(bokeh.events.DoubleTap,      lambda evt: [fn(evt) for fn in self.events.get(bokeh.events.DoubleTap,[])])
		self.fig.on_event(bokeh.events.RangesUpdate,   lambda evt: [fn(evt) for fn in self.events.get(bokeh.events.RangesUpdate,[])])

		# tracl changes in the size
		# see https://github.com/bokeh/bokeh/issues/9136

		self.fig.on_change('inner_width',  self.onFigureSizeChange)
		self.fig.on_change('inner_height', self.onFigureSizeChange)

		# replace the figure from the fig_layout (so that later on I can replace it)
		self.fig_layout[:]=[
			Bokeh(self.fig),
			self.box_select_tool_helper,
		]
		self.enableSelection()
		self.last_renderer={}

	# enableSelection
	def enableSelection(self,use_python_events=False):

		"""
		Implementing in javascript since this DOES NOT WORK
		self.fig.on_event(bokeh.events.SelectionGeometry, lambda s: print("JHERE"))
		"""

		def handleSelectionGeometry(attr,old,new):
			j=json.loads(new)
			x,y=float(j["x0"])  ,float(j["y0"])
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
		self.fig.xaxis.axis_label  ='X'
		self.fig.yaxis.axis_label  = 'Y'		


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
		x=self.fig.x_range.start # The x coordinate of the viewport's bottom-left corner.
		y=self.fig.y_range.start # The y coordinate of the viewport's bottom-left corner.
		w=self.fig.x_range.end-x # The width of the viewport along the x axis.
		h=self.fig.y_range.end-y # The height of the viewport along the y axis.
		return [x,y,w,h]

	  # setViewport
	def setViewport(self,value):
		x,y,w,h=self.__fixAspectRatioIfNeeded(value)
		self.fig.x_range.start, self.fig.x_range.end = x, x+w
		self.fig.y_range.start, self.fig.y_range.end = y, y+h

	# showData
	def showData(self, pdim, data, viewport, color_bar=None):

		x,y,w,h=viewport
		self.pdim=pdim
		assert(pdim==1 or pdim==2)
		self.fig.xaxis.formatter.use_scientific = (pdim!=1)
		self.fig.yaxis.formatter.use_scientific = (pdim!=1)

		# 1D signal (eventually with an extra channel for filters)
		if pdim==1:
			assert(len(data.shape) in [1,2])
			if len(data.shape)==2: data=data[:,0]
			self.fig.renderers.clear()

			xs=np.arange(x,x+w,w/data.shape[0])
			ys=data
			self.fig.line(xs,ys)

		# 2d image (eventually multichannel)
		else:	
			assert(len(data.shape) in [2,3])
			img=ConvertDataForRendering(data)
			dtype=img.dtype
			
			# compatible with last rendered image?
			if all([
				self.last_renderer.get("source",None) is not None,
				self.last_renderer.get("dtype",None)==dtype,
				self.last_renderer.get("color_bar",None)==color_bar
			]):
				self.last_renderer["source"].data={"image":[img], "X":[x], "Y":[y], "dw":[w], "dh":[h]}
			else:
				self.createFigure()
				source = bokeh.models.ColumnDataSource(data={"image":[img], "X":[x], "Y":[y], "dw":[w], "dh":[h]})
				if img.dtype==np.uint32:	
					self.fig.image_rgba("image", source=source, x="X", y="Y", dw="dw", dh="dh") 
				else:
					self.fig.image("image", source=source, x="X", y="Y", dw="dw", dh="dh", color_mapper=color_bar.color_mapper) 
				
				if not self.view_choice:
					self.fig.add_layout(color_bar, 'right')   # to stop showing side color bar in sync_view
				self.last_renderer={
					"source": source,
					"dtype":img.dtype,
					"color_bar":color_bar
				}


# ////////////////////////////////////////////////////////////////////////////////////
class Slice(param.Parameterized):

	ID=0

	EPSILON = 0.001

	show_options={
		"top": [
			[ "menu_button","scene", "timestep", "timestep_delta", "play_sec","play_button","palette",  "color_mapper_type","view_dependent", "resolution", "num_refinements", "show_probe"],
			["field","direction", "offset", "range_mode", "range_min",  "range_max"]

		],
		"bottom": [
			["request","response","image_type"]
		]
	}

	# constructor
	def __init__(self, ViewChoice=None): 
		super().__init__()  
		
		self.id=Slice.ID+1
		Slice.ID += 1
		self.job_id=0

		self.view_choice = ViewChoice # passing ViewChoice for sync view

		self.vmin=None
		self.vmax=None
		self.db = None
		self.access = None

		# translate and scale for each dimension
		self.logic_to_physic        = [(0.0, 1.0)] * 3
		self.metadata_range         = [0.0, 255.0]
		self.scenes                 = {}

		self.aborted       = Aborted()
		self.new_job       = False
		self.current_img   = None
		self.last_job_pushed =time.time()

		
    
		self.createGui()

	# createMenuButton
	def createMenuButton(self):

		action_helper          = pn.widgets.TextInput(visible=False)
		save_button_helper     = pn.widgets.TextInput(visible=False)
		copy_url_button_helper = pn.widgets.TextInput(visible=False)
	
		main_button = pn.widgets.MenuButton(
			name="File", items=[('Open', 'open'), ('Save', 'save'), ('Show Metadata', 'metadata'),('Copy Url','copy-url'), None, ("Refresh All","refresh-all"), None, ('Logout', 'logout')], 
			button_type='primary')


		# onClicked
		def onClicked(action):
			action_helper.value=action # this is needed for the javascript part

			if action=="metadata":
				self.showMetadata()
				return

			if action=="open":
				self.showOpen()

			if action=="save":
				body=self.save()
				save_button_helper.value=body # this is needed for the javascript part
				return

			if action=="copy-url":
				copy_url_button_helper.value=self.getShareableUrl() # this is needed for the javascript part
				ShowInfoNotification(f'Copy Url done {copy_url_button_helper.value}')
				return

			if action=="refresh-all":
				self.refreshAll()
				return

		main_button.on_click(SafeCallback(lambda evt: onClicked(evt.new)))
		main_button.js_on_click(args={
			"action_helper":action_helper,
			"save_button_helper":save_button_helper,
			"copy_url_button_helper": copy_url_button_helper
			}, code="""

					function jsCallFunction() {
						
						console.log("jsCallFunction value="+action_helper.value);

						if (action_helper.value=="save") {
							console.log("save_button_helper.value=" + save_button_helper.value);
							const link = document.createElement("a");
							const file = new Blob([save_button_helper.value], { type: 'text/plain' });
							link.href = URL.createObjectURL(file);
							link.download = "save_scene.json";
							link.click();
							URL.revokeObjectURL(link.href);
							return
						}

						if (action_helper.value=="copy-url") {
							console.log("copy_url_button_helper.value=" + copy_url_button_helper.value);
							navigator.clipboard.writeText(copy_url_button_helper.value);
							return;
						}				

						if (action_helper.value=="logout") {
							console.log("window.location.href="+window.location.href);
							window.location=window.location.href + "/logout";
						}

					}

					setTimeout(jsCallFunction,300);
					""")

		return pn.Row(
			main_button,
			action_helper, 
			save_button_helper, 
			copy_url_button_helper,
			max_width=120,
			align=('start', 'end'))

	# refreshAll
	def refreshAll(self):
		viewport=self.canvas.getViewport()
		self.canvas.setViewport(viewport)
		self.refresh("refreshAll")
		self.probe_tool.recomputeAllProbes()

	# createColorBar
	def createColorBar(self):
		color_mapper_type=self.color_mapper_type.value
		assert(color_mapper_type in ["linear","log"])
		is_log=color_mapper_type=="log"
		low =cdouble(self.range_min.value)
		high=cdouble(self.range_max.value)
		mapper_low =max(Slice.EPSILON, low ) if is_log else low
		mapper_high=max(Slice.EPSILON, high) if is_log else high
		self.color_bar = bokeh.models.ColorBar(color_mapper = 
			bokeh.models.LogColorMapper   (palette=self.palette.value, low=mapper_low, high=mapper_high) if is_log else 
			bokeh.models.LinearColorMapper(palette=self.palette.value, low=mapper_low, high=mapper_high)
		)


	# open
	def showOpen(self):

		body=json.dumps(self.getBody(),indent=2)
		self.scene_body.value=body

		def onFileInputChange(evt):
			self.scene_body.value=file_input.value.decode('ascii')
			ShowInfoNotification('Load done. Press `Eval`')
		file_input = pn.widgets.FileInput(description="Load", accept=".json")
		file_input.param.watch(SafeCallback(onFileInputChange),"value", onlychanged=True,queued=True)

		def onEvalClick(evt):
			self.setBody(json.loads(self.scene_body.value))
			ShowInfoNotification('Eval done')
		eval_button = pn.widgets.Button(name="Eval", align='end')
		eval_button.on_click(SafeCallback(onEvalClick))

		self.showDialog(
			Column(
				self.scene_body,
				Row(file_input, eval_button, align='end'),
				sizing_mode="stretch_both",align="end"
			), 
			width=600, height=700, name="Open")
	

	# save
	def save(self):
		body=json.dumps(self.getBody(),indent=2)
		ShowInfoNotification('Save done')
		print(body)
		return body

	# createGui
	def createGui(self):

		self.play = types.SimpleNamespace()
		self.play.is_playing = False

		self.idle_callback = None
		self.color_bar     = None

		self.menu_button=self.createMenuButton()

		self.dialogs=Column()
		self.dialogs.visible=False

		self.central_layout  = Column(sizing_mode="stretch_both")

		self.main_layout=Row(
			self.central_layout,
			sizing_mode="stretch_both")

		# just so that we can get new instances in each session
		self.render_id = pn.widgets.IntSlider(name="RenderId", value=0)

		# current scene as json
		self.scene_body = pn.widgets.CodeEditor(name='Current', sizing_mode="stretch_width", height=520,language="json")
		self.scene_body.stylesheets=[""".bk-input {background-color: rgb(48, 48, 64);color: white;font-size: small;}"""]
		
		# core query
		self.scene = pn.widgets.Select(name="Scene", options=[], width=120)
		def onSceneChange(evt): 
			logger.info(f"onSceneChange {evt}")
			body=self.scenes[evt.new]
			self.setBody(body)
		self.scene.param.watch(SafeCallback(onSceneChange),"value", onlychanged=True,queued=True)

		self.timestep = pn.widgets.IntSlider(name="Time", value=0, start=0, end=1, step=1, sizing_mode="stretch_width")
		def onTimestepChange(evt):
			self.refresh(reason="onTimestepChange")
		self.timestep.param.watch(SafeCallback(onTimestepChange), "value", onlychanged=True,queued=True)

		self.timestep_delta = pn.widgets.Select(name="Speed", options=[1, 2, 4, 8, 16, 32, 64, 128], value=1, width=50)
		def onTimestepDeltaChange(evt):
			if bool(getattr(self,"setting_timestep_delta",False)): return
			setattr(self,"setting_timestep_delta",True)
			value=int(evt.new)
			A = self.timestep.start
			B = self.timestep.end
			T = self.timestep.value
			T = A + value * int((T - A) / value)
			T = min(B, max(A, T))
			self.timestep.step = value
			self.timestep.value=T
			setattr(self,"setting_timestep_delta",False)
		self.timestep_delta.param.watch(SafeCallback(onTimestepDeltaChange),"value", onlychanged=True,queued=True)

		self.field = pn.widgets.Select(name='Field', options=[], value='data', width=80)
		def onFieldChange(evt):
			self.refresh("onFieldChange")
		self.field.param.watch(SafeCallback(onFieldChange),"value", onlychanged=True,queued=True)

		self.resolution = pn.widgets.IntSlider(name='Resolution', value=28, start=20, end=99, sizing_mode="stretch_width")
		self.resolution.param.watch(SafeCallback(lambda evt: self.refresh("resolution.param.watch")),"value", onlychanged=True,queued=True)

		self.view_dependent = pn.widgets.Select(name="ViewDep", options={"Yes": True, "No": False}, value=True, width=80)
		self.view_dependent.param.watch(SafeCallback(lambda evt: self.refresh("view_dependent.param.watch")),"value", onlychanged=True,queued=True)

		self.num_refinements = pn.widgets.IntSlider(name='#Ref', value=0, start=0, end=4, width=80)
		self.num_refinements.param.watch(SafeCallback(lambda evt: self.refresh("num_refinements.param.watch")),"value", onlychanged=True,queued=True)
		self.direction = pn.widgets.Select(name='Direction', options={'X': 0, 'Y': 1, 'Z': 2}, value=2, width=80)
		def onDirectionChange(evt):
			value=evt.new
			logger.debug(f"id={self.id} value={value}")
			pdim = self.getPointDim()
			if pdim in (1,2): value = 2 # direction value does not make sense in 1D and 2D
			dims = [int(it) for it in self.db.getLogicSize()]

			# default behaviour is to guess the offset
			offset_value,offset_range=self.guessOffset(value)
			self.offset.start=offset_range[0]
			self.offset.end  =offset_range[1]
			self.offset.step=1e-16 if self.offset.editable and offset_range[2]==0.0 else offset_range[2] #  problem with editable slider and step==0
			self.offset.value=offset_value
			self.setQueryLogicBox(([0]*pdim,dims))
			self.refresh("onDirectionChange")
		self.direction.param.watch(SafeCallback(onDirectionChange),"value", onlychanged=True,queued=True)

		self.offset = pn.widgets.EditableFloatSlider(name="Depth", start=0.0, end=1024.0, step=1.0, value=0.0, sizing_mode="stretch_width", format=bokeh.models.formatters.NumeralTickFormatter(format="0.01"))
		self.offset.param.watch(SafeCallback(lambda evt: self.refresh("offset.param.watch")),"value", onlychanged=True,queued=True)
		
		# palette 
		self.range_mode = pn.widgets.Select(name="Range", options=["metadata", "user", "dynamic", "dynamic-acc"], value="dynamic", width=120)
		def onRangeModeChange(evt):
			mode=evt.new
			if mode == "metadata":   
				self.range_min.value = self.metadata_range[0]
				self.range_max.value = self.metadata_range[1]
			if mode == "dynamic-acc":
				self.range_min.value = 0.0
				self.range_max.value = 0.0
			self.range_min.disabled = False if mode == "user" else True
			self.range_max.disabled = False if mode == "user" else True
			self.refresh("onRangeModeChange")
		self.range_mode.param.watch(SafeCallback(onRangeModeChange),"value", onlychanged=True,queued=True)

		self.range_min = pn.widgets.FloatInput(name="Min", width=80,value=0.0)
		self.range_max = pn.widgets.FloatInput(name="Max", width=80,value=0.0) # NOTE: in dynamic mode I need an empty range
		def onUserRangeChange(evt):
			mode=self.range_mode.value
			if mode!="user": return
			self.refresh("onUserRangeChange")
		self.range_min.param.watch(SafeCallback(onUserRangeChange),"value", onlychanged=True,queued=True)
		self.range_max.param.watch(SafeCallback(onUserRangeChange),"value", onlychanged=True,queued=True)

		self.palette = pn.widgets.ColorMap(name="Palette", options=GetPalettes(), value_name="Greys256", ncols=3, width=180)

		def onPaletteChange(evt):
			self.createColorBar()
			self.refresh("onPaletteChange")

		self.palette.param.watch(SafeCallback(onPaletteChange),"value_name", onlychanged=True,queued=True)

		self.color_mapper_type = pn.widgets.Select(name="Mapper", options=["linear", "log"], width=60)
		def onColorMapperTypeChange(evt):
			self.createColorBar()
			self.refresh("onColorMapperTypeChange")
		self.color_mapper_type.param.watch(SafeCallback(onColorMapperTypeChange),"value", onlychanged=True,queued=True)

		self.play_button = pn.widgets.Button(name="Play", width=10)
		self.play_button.on_click(SafeCallback(lambda evt: self.togglePlay()))

		self.play_sec = pn.widgets.Select(name="Delay", options=[0.00, 0.01, 0.1, 0.2, 0.1, 1, 2], value=0.01, width=90)
		self.request = pn.widgets.TextInput(name="", sizing_mode='stretch_width', disabled=False)
		self.response = pn.widgets.TextInput(name="", sizing_mode='stretch_width', disabled=False)

		self.file_name_input = pn.widgets.TextInput(name="Numpy_File", value='test', placeholder='Numpy File Name to save')

		self.canvas = Canvas(self.id, self.view_choice)
		self.canvas.on_event(bokeh.events.RangesUpdate     , SafeCallback(self.onCanvasViewportChange))
		self.canvas.on_event(bokeh.events.Tap              , SafeCallback(self.onCanvasSingleTap))
		self.canvas.on_event(bokeh.events.DoubleTap        , SafeCallback(self.onCanvasDoubleTap))
		self.canvas.on_event(bokeh.events.SelectionGeometry, SafeCallback(self.onCanvasSelectionGeometry))

		if self.canvas.view_choice == "SYNC_VIEW":
			self.image_type = pn.widgets.TextInput(name="", sizing_mode='stretch_width', disabled=False) # Sync-View Image Title
		else:
			self.image_type = None

		# probe_tool
		from .probe import ProbeTool
		self.probe_tool=ProbeTool(self)
		
		self.show_probe=pn.widgets.Toggle(name='Probe',value=False, width=60, align=('start', 'end'), button_style='outline', button_type='primary')
		self.show_probe.param.watch(SafeCallback(lambda evt: self.setShowProbe(evt.new)),"value")

		self.setShowOptions(Slice.show_options)
		self.start()

	# setShowProbe
	def setShowProbe(self, value):
		self.show_probe.value=value
		if value:
			self.main_layout[:]=[self.central_layout,self.probe_tool.getMainLayout()]
			self.probe_tool.recomputeAllProbes()
		else:
			self.main_layout[:]=[self.central_layout]

	# onCanvasViewportChange
	def onCanvasViewportChange(self, evt):
		x,y,w,h=self.canvas.getViewport()
		self.refresh("onCanvasViewportChange")

	# onCanvasSingleTap # a click on image
	def onCanvasSingleTap(self, evt):
		logger.info(f"Single tap {evt}")
		pass

	# onCanvasDoubleTap
	def onCanvasDoubleTap(self, evt):
		logger.info(f"Double tap {evt}")

	# getShowOptions
	def getShowOptions(self):
		return self.show_options

	# setShowOptions
	def setShowOptions(self, value):
		self.show_options=value

		# [0,1) means 1 timestep
		num_timesteps=max(1,len(self.db.getTimesteps())-1) if self.db else 1
	
		def CreateWidgets(row):
			ret=[]
			for it in row:
				widget=getattr(self, it.replace("-","_"),None)
				if widget:
					if num_timesteps==1 and widget in [self.timestep, self.timestep_delta, self.play_sec,self.play_button]:
						continue
					ret.append(widget)
					
			return ret

		top   =[Row(*CreateWidgets(row),sizing_mode="fixed") for row in value.get("top"   ,[[]])]
		bottom=[Row(*CreateWidgets(row),sizing_mode="stretch_width") for row in value.get("bottom",[[]])]

		self.central_layout[:]=[
					*top,
					self.canvas.fig_layout,
					*bottom,
					self.dialogs,
		]

	# getShareableUrl
	def getShareableUrl(self, short=True):
		body=self.getBody()
		load_s=base64.b64encode(json.dumps(body).encode('utf-8')).decode('ascii')
		current_url=GetCurrentUrl()
		o=urlparse(current_url)
		ret=o.scheme + "://" + o.netloc + o.path + '?' + urlencode({'load': load_s})		
		ret=GetShortUrl(ret) if short else ret
		return ret

	# stop
	def stop(self):
		self.aborted.setTrue()
		if self.db:
			self.db.stop()

	# start
	def start(self):
		if self.db:
			self.db.start()
		if not self.idle_callback:
			self.idle_callback = AddPeriodicCallback(self.onIdle, 1000 // 30)
		self.refresh("self.start")

	# getMainLayout
	def getMainLayout(self):
		return self.main_layout

	# getLogicToPhysic
	def getLogicToPhysic(self):
		return self.logic_to_physic

	# setLogicToPhysic
	def setLogicToPhysic(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.logic_to_physic = value
		self.refresh("self.setLogicToPhysic")

	# getPhysicBox
	def getPhysicBox(self):
		dims = self.db.getLogicSize()
		vt = [it[0] for it in self.logic_to_physic]
		vs = [it[1] for it in self.logic_to_physic]
		return [[
			0 * vs[I] + vt[I],
			dims[I] * vs[I] + vt[I]
		] for I in range(len(dims))]

	# setPhysicBox
	def setPhysicBox(self, value):
		dims = self.db.getLogicSize()
		def LinearMapping(a, b, A, B):
			vs = (B - A) / (b - a)
			vt = A - a * vs
			return vt, vs
		T = [LinearMapping(0, dims[I], *value[I]) for I in range(len(dims))]
		self.setLogicToPhysic(T)
		
	# getBody
	def getBody(self):
		ret={
			"scene" : {
				"name": self.scene.value, 
				
				# NOT needed.. they should come automatically from the dataset?
				#   "timesteps": self.db.getTimesteps(),
				#   "physic_box": self.getPhysicBox(),
				#   "fields": self.field.options,
				#   "directions" : self.direction.options,
				# "metadata-range": self.metadata_range,

				"timestep-delta": self.timestep_delta.value,
				"timestep": self.timestep.value,
				"direction": self.direction.value,
				"offset": self.offset.value, 
				"field": self.field.value,
				"view-dependent": self.view_dependent.value,
				"resolution": self.resolution.value,
				"num-refinements": self.num_refinements.value,
				"play-sec":self.play_sec.value,
				"palette": self.palette.value_name,
				"color-mapper-type": self.color_mapper_type.value,
				"range-mode": self.range_mode.value,
				"range-min": cdouble(self.range_min.value), # Object of type float32 is not JSON serializable
				"range-max": cdouble(self.range_max.value),
				"viewport": self.canvas.getViewport(),
				"show_probe": self.show_probe.value,
			}
		}

		if self.probe_tool.getActiveProbes():
			ret["scene"]["probe_tool"]=self.probe_tool.getBody()

		return ret

	# load
	def load(self, value):

		if isinstance(value,str):
			ext=os.path.splitext(value)[1].split("?")[0]
			if ext==".json":
				value=LoadJSON(value)
			else:
				value={"scenes": [{"name": os.path.basename(value), "url":value}]}

		# from dictionary
		elif isinstance(value,dict):
			pass
		else:
			raise Exception(f"{value} not supported")

		assert(isinstance(value,dict))
		assert(len(value)==1)
		root=list(value.keys())[0]

		self.scenes={}
		for it in value[root]:
			if "name" in it:
				self.scenes[it["name"]]={"scene": it}

		self.scene.options = list(self.scenes)

		if self.scenes:
			first_scene_name=list(self.scenes)[0]
			self.setBody(self.scenes[first_scene_name])
		else:
			self.refreshAll()

	# setBody
	def setBody(self, body):

		logger.info(f"# //////////////////////////////////////////#")
		logger.info(f"id={self.id} {body} START")

		# TODO!
		# self.stop()

		assert(isinstance(body,dict))
		assert(len(body)==1 and list(body.keys())==["scene"])

		# go one level inside
		body=body["scene"]

		# the url should come from first load (for security reasons)
		name=body["name"]

		assert(name in self.scenes)
		default_scene=self.scenes[name]["scene"]
		url =default_scene["url"]
		urls=default_scene.get("urls",{})

		# special case, I want to force the dataset to be local (case when I have a local dashboards and remove dashboards)
		if "urls" in body:

			if "--prefer" in sys.argv:
				prefer = sys.argv[sys.argv.index("--prefer") + 1]
				prefers = [it for it in urls if it['id']==prefer]
				if prefers:
					logger.info(f"id={self.id} Overriding url from {prefers[0]['url']} since selected from --select command line")
					url = prefers[0]['url']
					
			else:
				locals=[it for it in urls if it['id']=="local"]
				if locals and os.path.isfile(locals[0]["url"]):
					logger.info(f"id={self.id} Overriding url from {locals[0]['url']} since it exists and is a local path")
					url = locals[0]["url"]

		logger.info(f"id={self.id} LoadDataset url={url}...")
		db=LoadDataset(url=url) 
		self.data_url=url
		# update the GUI too
		self.db    =db
		self.access=db.createAccess()
		self.scene.value=name


		timesteps=self.db.getTimesteps()
		self.timestep.start = timesteps[ 0]
		self.timestep.end   = max(timesteps[-1],self.timestep.start+1) # bokeh fixes: start cannot be equals to end
		self.timestep.step  = 1

		self.field.options=list(self.db.getFields())

		pdim = self.getPointDim()

		if "logic-to-physic" in body:
			logic_to_physic=body["logic-to-physic"]
			self.setLogicToPhysic(logic_to_physic)
		else:
			physic_box=self.db.getPhysicBox()
			self.setPhysicBox(physic_box)

		if "directions" in body:
			directions=body["directions"]
		else:
			directions=self.db.getAxis()
		self.direction.options=directions

		self.timestep_delta.value=int(body.get("timestep-delta", 1))
		self.timestep.value=int(body.get("timestep", self.db.getTimesteps()[0]))
		self.view_dependent.value = bool(body.get('view-dependent', True))

		resolution=int(body.get("resolution", -6))
		if resolution<0: resolution=self.db.getMaxResolution()+resolution
		self.resolution.end = self.db.getMaxResolution()

		if self.canvas.view_choice == "SYNC_VIEW":
			self.resolution.value = self.resolution.end #kept max_resolution default for sync view
		else:
			self.resolution.value = resolution
		
		self.field.value=body.get("field", self.db.getField().name)

		self.num_refinements.value=int(body.get("num-refinements", 1 if pdim==1 else 2))

		self.direction.value = int(body.get("direction", 2))

		default_offset_value,offset_range=self.guessOffset(self.direction.value)
		self.offset.start=offset_range[0]
		self.offset.end  =offset_range[1]
		self.offset.step=1e-16 if self.offset.editable and offset_range[2]==0.0 else offset_range[2] #  problem with editable slider and step==0
		self.offset.value=float(body.get("offset",default_offset_value))
		self.setQueryLogicBox(([0]*self.getPointDim(),[int(it) for it in self.db.getLogicSize()]))

		self.play_sec.value=float(body.get("play-sec",0.01))
		self.palette.value_name=body.get("palette",DEFAULT_PALETTE)

		self.metadata_range = list(body.get("metadata-range",self.db.getFieldRange()))
		assert(len(self.metadata_range))==2
		self.range_mode.value=body.get("range-mode","dynamic")

		self.range_min.value = body.get("range-min",0.0)
		self.range_max.value = body.get("range-max",0.0)

		self.color_mapper_type.value = body.get("color-mapper-type","linear")	

		viewport=body.get("viewport",None)
		if viewport is not None:
			self.canvas.setViewport(viewport)

		# probe_tool
		self.show_probe.value=body.get("show_probe",False)
		self.probe_tool.setBody(body.get("probe_tool",{}))
			
		show_options=body.get("show-options",Slice.show_options)

		self.setShowOptions(show_options)
		self.start()

		logger.info(f"id={self.id} END\n")

		self.refreshAll()

	# onCanvasSelectionGeometry
	def onCanvasSelectionGeometry(self, evt):
		ShowInfoNotification('Reading data. Please wait...')
		ShowDetails(self,*evt.new)
		ShowInfoNotification('Data ready')

	# showMetadata
	def showMetadata(self):

		logger.debug(f"Show info")
		body=self.scenes[self.scene.value]
		metadata=body["scene"].get("metadata", [])
		if not metadata:
			self.showDialog(HTML(f"<div><pre><code>No metadata</code></pre></div>",sizing_mode="stretch_width",height=400))

		else:

			cards=[]
			for I, item in enumerate(metadata):

				type = item["type"]
				filename = item.get("filename",f"metadata_{I:02d}.bin")

				if type == "b64encode":
					# binary encoded in string
					body = base64.b64decode(item["encoded"]).decode("utf-8")
					body = io.StringIO(body)
					body.seek(0)
					internal_panel=HTML(f"<div><pre><code>{body}</code></pre></div>",sizing_mode="stretch_width",height=400)
				elif type=="json-object":
					obj=item["object"]
					file = io.StringIO(json.dumps(obj))
					file.seek(0)
					internal_panel=JSON(obj,name="Object",depth=3, sizing_mode="stretch_width",height=400) 
				else:
					continue

				cards.append(Card(
						internal_panel,
						pn.widgets.FileDownload(file, embed=True, filename=filename,align="end"),
						title=filename,
						collapsed=(I>0),
						sizing_mode="stretch_width"
					)
				)

			self.showDialog(*cards)

	# showDialog
	def showDialog(self, *args,**kwargs):
		d={"position":"center", "width":1024, "height":600, "contained":False}
		d.update(**kwargs)
		float_panel=FloatPanel(*args, **d)
		self.dialogs.append(float_panel)

	# getMaxResolution
	def getMaxResolution(self):
		return self.db.getMaxResolution()

	# setViewDependent
	def setViewDependent(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.view_dependent.value = value
		self.refresh("self.setViewDependent")

	# getLogicAxis (depending on the projection XY is the slice plane Z is the orthogoal direction)
	def getLogicAxis(self):
		dir  = self.direction.value
		directions = self.direction.options
		# this is the projected slice
		XY = list(directions.values())
		if len(XY) == 3:
			del XY[dir]
		else:
			assert (len(XY) == 2)
		X, Y = XY
		# this is the cross dimension
		Z = dir if len(directions) == 3 else 2
		titles = list(directions.keys())
		return (X, Y, Z), (titles[X], titles[Y], titles[Z] if len(titles) == 3 else 'Z')

	# guessOffset
	def guessOffset(self, dir):

		pdim = self.getPointDim()

		# offset does not make sense in 1D and 2D
		if pdim<=2:
			return 0, [0, 0, 1] # (offset,range) 
		else:
			# 3d
			vt = [self.logic_to_physic[I][0] for I in range(pdim)]
			vs = [self.logic_to_physic[I][1] for I in range(pdim)]

			if all([it == 0 for it in vt]) and all([it == 1.0 for it in vs]):
				dims = [int(it) for it in self.db.getLogicSize()]
				value = dims[dir] // 2
				return value,[0, int(dims[dir]) - 1, 1]
			else:
				A, B = self.getPhysicBox()[dir]
				value = (A + B) / 2.0
				return value,[A, B, 0]

	# toPhysic (i.e. logic box -> canvas viewport in physic coordinates)
	def toPhysic(self, value):
		dir = self.direction.value
		pdim = self.getPointDim()

		vt = [self.logic_to_physic[I][0] for I in range(pdim)]
		vs = [self.logic_to_physic[I][1] for I in range(pdim)]
		p1,p2=value

		p1 = [vs[I] * p1[I] + vt[I] for I in range(pdim)]
		p2 = [vs[I] * p2[I] + vt[I] for I in range(pdim)]

		if pdim==1:
			# todo: what is the y range? probably I shold do what I am doing with the colormap
			assert(len(p1)==1 and len(p2)==1)
			p1.append(0.0)
			p2.append(1.0)

		elif pdim==2:
			assert(len(p1)==2 and len(p2)==2)

		else:
			assert(pdim==3 and len(p1)==3 and len(p2)==3)
			del p1[dir]
			del p2[dir]

		x1,y1=p1
		x2,y2=p2
		return [x1,y1, x2-x1, y2-y1]

	# toLogic
	def toLogic(self, value):
		pdim = self.getPointDim()
		dir = self.direction.value
		vt = [self.logic_to_physic[I][0] for I in range(pdim)]
		vs = [self.logic_to_physic[I][1] for I in range(pdim)]		

		x,y,w,h=value
		p1=[x  ,y  ]
		p2=[x+w,y+h]

		if pdim==1:
			del p1[1]
			del p2[1]
		elif pdim==2:
			pass # alredy in 2D
		else:
			assert(pdim==3) 
			p1.insert(dir, 0) # need to add the missing direction
			p2.insert(dir, 0)

		assert(len(p1)==pdim and len(p2)==pdim)



		p1 = [(p1[I] - vt[I]) / vs[I] for I in range(pdim)]
		p2 = [(p2[I] - vt[I]) / vs[I] for I in range(pdim)]

		# in 3d the offset is what I should return in logic coordinates (making the box full dim)
		if pdim == 3:
			p1[dir] = int((self.offset.value  - vt[dir]) / vs[dir])
			p2[dir] = p1[dir]+1 
			
		return [p1, p2]

	# togglePlay
	def togglePlay(self):
		if self.play.is_playing:
			self.stopPlay()
		else:
			self.startPlay()

	# startPlay
	def startPlay(self):
		logger.info(f"id={self.id}::startPlay")
		self.play.is_playing = True
		self.play_button.name = "Stop"
		self.play.t1 = time.time()
		self.play.wait_render_id = None
		self.play.num_refinements = self.num_refinements.value
		self.num_refinements.value = 1
		self.setWidgetsDisabled(True)
		self.play_button.disabled = False
		

	# stopPlay
	def stopPlay(self):
		logger.info(f"id={self.id}::stopPlay")
		self.play.is_playing = False
		self.play.wait_render_id = None
		self.num_refinements.value = self.play.num_refinements
		self.setWidgetsDisabled(False)
		self.play_button.disabled = False
		self.play_button.name = "Play"

	# playNextIfNeeded
	def playNextIfNeeded(self):

		if not self.play.is_playing:
			return

		# avoid playing too fast by waiting a minimum amount of time
		t2 = time.time()
		if (t2 - self.play.t1) < float(self.play_sec.value):
			return

		# wait
		if self.play.wait_render_id is not None and self.render_id.value<self.play.wait_render_id:
			return

		# advance
		T = int(self.timestep.value) + self.timestep_delta.value

		# reached the end -> go to the beginning?
		if T >= self.timestep.end:
			T = self.timesteps.timestep.start

		logger.info(f"id={self.id}::playing timestep={T}")

		# I will wait for the resolution to be displayed
		self.play.wait_render_id = self.render_id.value+1
		self.play.t1 = time.time()
		self.timestep.value= T

	# onShowMetadataClick
	def onShowMetadataClick(self):
		self.metadata.visible = not self.metadata.visible

	# setWidgetsDisabled
	def setWidgetsDisabled(self, value):
		self.scene.disabled = value
		self.palette.disabled = value
		self.timestep.disabled = value
		self.timestep_delta.disabled = value
		self.field.disabled = value
		self.direction.disabled = value
		self.offset.disabled = value
		self.num_refinements.disabled = value
		self.resolution.disabled = value
		self.view_dependent.disabled = value
		self.request.disabled = value
		self.response.disabled = value
		self.play_button.disabled = value
		self.play_sec.disabled = value



	# getPointDim
	def getPointDim(self):
		return self.db.getPointDim() if self.db else 2

	# refresh
	def refresh(self,reason=None):
		logger.info(f"reason={reason}")
		self.aborted.setTrue()
		self.new_job=True

	# getQueryLogicBox
	def getQueryLogicBox(self):
		viewport=self.canvas.getViewport()
		return self.toLogic(viewport)

	# setQueryLogicBox
	def setQueryLogicBox(self,value):
		viewport=self.toPhysic(value)
		self.canvas.setViewport(viewport)
		self.refresh("setQueryLogicBox")
  
	# getLogicCenter
	def getLogicCenter(self):
		pdim=self.getPointDim()  
		p1,p2=self.getQueryLogicBox()
		assert(len(p1)==pdim and len(p2)==pdim)
		return [(p1[I]+p2[I])*0.5 for I in range(pdim)]

	# getLogicSize
	def getLogicSize(self):
		pdim=self.getPointDim()
		p1,p2=self.getQueryLogicBox()
		assert(len(p1)==pdim and len(p2)==pdim)
		return [(p2[I]-p1[I]) for I in range(pdim)]

  # gotoPoint
	def gotoPoint(self,point):
		return  # COMMENTED OUT
		"""
		self.offset.value=point[self.direction.value]
		
		(p1,p2),dims=self.getQueryLogicBox(),self.getLogicSize()
		p1,p2=list(p1),list(p2)
		for I in range(self.getPointDim()):
			p1[I],p2[I]=point[I]-dims[I]/2,point[I]+dims[I]/2
		self.setQueryLogicBox([p1,p2])
		self.canvas.renderPoints([self.toPhysic(point)]) 
		"""
  
	# gotNewData
	def gotNewData(self, result):

		data=result['data']
		try:
			data_range=np.min(data),np.max(data)
		except:
			data_range=0.0,0.0

		logic_box=result['logic_box'] 

		# depending on the palette range mode, I need to use different color mapper low/high
		mode=self.range_mode.value

		# show the user what is the current offset
		maxh=self.db.getMaxResolution()
		dir=self.direction.value

		pdim=self.getPointDim()
		vt,vs=self.logic_to_physic[dir] if pdim==3 else (0.0,1.0)
		endh=result['H']

		user_physic_offset=self.offset.value

		real_logic_offset=logic_box[0][dir] if pdim==3 else 0.0
		real_physic_offset=vs*real_logic_offset + vt 
		user_logic_offset=int((user_physic_offset-vt)/vs)

		# update slider info
		self.offset.name=" ".join([
			f"Offset: {user_physic_offset:.3f}±{abs(user_physic_offset-real_physic_offset):.3f}",
			f"Pixel: {user_logic_offset}±{abs(user_logic_offset-real_logic_offset)}",
			f"Max Res: {endh}/{maxh}"
		])

		pdim = self.getPointDim()

		# refresh the range
		# in dynamic mode, I need to use the data range
		if mode=="dynamic":
			self.range_min.value = data_range[0] 
			self.range_max.value = data_range[1]

		# in data accumulation mode I am accumulating the range
		if mode=="dynamic-acc":
			if self.range_min.value>=self.range_max.value:
				self.range_min.value=data_range[0]
				self.range_max.value=data_range[1]
			else:
				self.range_min.value = min(self.range_min.value, data_range[0])
				self.range_max.value = max(self.range_max.value, data_range[1])

		# update the color bar
		low =cdouble(self.range_min.value)
		high=cdouble(self.range_max.value)

		#
		if pdim==1:
			self.canvas.pan_tool.dimensions="width"
			self.canvas.wheel_zoom_tool.dimensions="width"
			if mode in ["dynamic","dynamic-acc"]:
				self.canvas.fig.y_range.start=int(self.range_min.value)
				self.canvas.fig.y_range.end  =int(self.range_max.value)			
			elif mode=="user":
				self.canvas.fig.y_range.start=int(self.range_min.value)
				self.canvas.fig.y_range.end  =int(self.range_max.value)			
			elif mode=="metadata":
				self.range_min.value = self.metadata_range[0]
				self.range_max.value = self.metadata_range[1]
		else:
			self.canvas.wheel_zoom_tool.dimensions="both"
			self.canvas.pan_tool.dimensions="both"

		color_mapper_type=self.color_mapper_type.value
		assert(color_mapper_type in ["linear","log"])
		is_log=color_mapper_type=="log"
		mapper_low =max(Slice.EPSILON, low ) if is_log else low
		mapper_high=max(Slice.EPSILON, high) if is_log else high

		self.color_bar.color_mapper.low = mapper_low
		self.color_bar.color_mapper.high = mapper_high
		
		logger.debug(f"id={self.id} job_id={self.job_id} rendering result data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box} mode={mode} np-array-range={data_range} widget-range={[low,high]}")

		# update the image
		self.canvas.showData(min(pdim,2), data, self.toPhysic(logic_box), color_bar= self.color_bar) # self.color_bar

		(X,Y,Z),(tX,tY,tZ)=self.getLogicAxis()
		self.canvas.setAxisLabels(tX,tY)

		# update the status bar
		if True:
			tot_pixels=np.prod(data.shape)
			canvas_pixels=self.canvas.getWidth()*self.canvas.getHeight()
			self.H=result['H']
			query_status="running" if result['running'] else "FINISHED"
			self.response.value=" ".join([
				f"#{result['I']+1}",
				f"{str(logic_box).replace(' ','')}",
				str(data.shape),
				f"Res={result['H']}/{maxh}",
				f"{result['msec']}msec",
				str(query_status)
			])

		# this way someone from the outside can watch for new results
		self.render_id.value=self.render_id.value+1 
  
	# pushJobIfNeeded
	def pushJobIfNeeded(self):

		if not self.new_job:
			return

		canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
		query_logic_box=self.getQueryLogicBox()
		pdim=self.getPointDim()

		# abort the last one
		self.aborted.setTrue()
		self.db.waitIdle()
		num_refinements = self.num_refinements.value
		if num_refinements==0:
			num_refinements={
				1: 1, 
				2: 3, 
				3: 4  
			}[pdim]
		self.aborted=Aborted()

		# do not push too many jobs
		if (time.time()-self.last_job_pushed)<0.2:
			return
		
		# I will use max_pixels to decide what resolution, I am using resolution just to add/remove a little the 'quality'
		if not self.view_dependent.value:
			# I am not using the information about the pixel on screen
			endh=self.resolution.value
			max_pixels=None
		else:

			endh=None 
			canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())

			# probably the UI is not ready yet
			if not canvas_w or not canvas_h:
				return

			if pdim==1:
				max_pixels=canvas_w
			else:
				delta=self.resolution.value-self.getMaxResolution()
				a,b=self.resolution.value,self.getMaxResolution()
				if a==b:
					coeff=1.0
				if a<b:
					coeff=1.0/pow(1.3,abs(delta)) # decrease 
				else:
					coeff=1.0*pow(1.3,abs(delta)) # increase 
				max_pixels=int(canvas_w*canvas_h*coeff)
			
		# new scene body
		self.scene_body.value=json.dumps(self.getBody(),indent=2)
		
		logger.debug("# ///////////////////////////////")
		self.job_id+=1
		logger.debug(f"id={self.id} job_id={self.job_id} pushing new job query_logic_box={query_logic_box} max_pixels={max_pixels} endh={endh}..")

		timestep=int(self.timestep.value)
		field=self.field.value
		box_i=[[int(it) for it in jt] for jt in query_logic_box]
		self.request.value=f"t={timestep} b={str(box_i).replace(' ','')} {canvas_w}x{canvas_h}"
		self.response.value="Running..."

		self.db.pushJob(
			self.db, 
			access=self.access,
			timestep=timestep, 
			field=field, 
			logic_box=query_logic_box, 
			max_pixels=max_pixels, 
			num_refinements=num_refinements, 
			endh=endh, 
			aborted=self.aborted
		)
		
		self.last_job_pushed=time.time()
		self.new_job=False
		# logger.debug(f"id={self.id} pushed new job query_logic_box={query_logic_box}")

	# onIdle
	def onIdle(self):

		if not self.db:
			return

		self.canvas.onIdle()

		if self.canvas and  self.canvas.getWidth()>0 and self.canvas.getHeight()>0:
			self.playNextIfNeeded()

		if self.db:
			result=self.db.popResult(last_only=True) 
			if result is not None: 
				self.gotNewData(result)
			self.pushJobIfNeeded()



# backward compatible
Slices=Slice



