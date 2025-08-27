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
from scipy.ndimage import gaussian_filter
import numpy as np
import networkx as nx
import bokeh
import bokeh.models
from bokeh.models import Button, CustomJS, ColumnDataSource, TextInput
from bokeh.models import FreehandDrawTool
import bokeh.events
import bokeh.plotting
import bokeh.models.callbacks
from bokeh.models import LinearColorMapper, ColorBar
from bokeh.plotting import figure
import param 
from datetime import datetime
import panel as pn
from panel.layout import FloatPanel
from panel import Column,Row,GridBox,Card
from panel.pane import HTML,JSON,Bokeh
from panel.widgets import IntInput, Button
import cv2
from utils import bbox_corners
from utils import *
from openvisuspy.backend import Aborted,LoadDataset,ExecuteBoxQuery
import time
from openvisuspy.show_details import ShowDetails
import math
from scipy.spatial import KDTree
import heapq
from collections import defaultdict
import sys
from pathlib import Path
from PIL import Image
from inference_pipeline import TissuePredictor
pn.extension(notifications=True)

BUTTON_CSS = """
:root {
  --btn-h: 34px;          /* visual height */
  --btn-pad-x: 14px;      /* left/right padding (a touch tighter) */
  --btn-pad-y: 6px;       /* top/bottom padding  */
  --toolbar-gap: 3px;     /* <<< tighter space between controls */
}

/* One-line toolbar that wraps and uses a fixed, tiny gap */
.right-toolbar {
  display: flex;
  flex-wrap: wrap;            /* wrap to next line if tight */
  gap: var(--toolbar-gap);    /* uniform spacing */
  align-items: center;
}

/* Pill look + perfect centering for Button/Toggle */
.bk-btn.pill,
.bk-btn-group .bk-btn.pill,
.bk-input-group .bk-btn.pill {
  height: var(--btn-h) !important;
  display: inline-flex !important;
  align-items: center !important;   /* vertical center */
  justify-content: center !important;/* horizontal center */
  padding: var(--btn-pad-y) var(--btn-pad-x) !important;
  border-radius: 9999px !important;
  font-weight: 600 !important;
  line-height: 1 !important;
  box-sizing: border-box;
  width: auto;                      /* size by label + padding */
}

/* Make selects match button height/centering visually */
.right-toolbar .bk-input {
  height: var(--btn-h);
  line-height: var(--btn-h);
  padding: 0 10px;
  box-sizing: border-box;
  font-size: 14px;
}

/* Keep native select arrow vertically centered (WebKit) */
.right-toolbar select.bk-input {
  -webkit-appearance: none;
  background-position: right 8px center;
}
"""
try:
    pn.config.raw_css.append(BUTTON_CSS)
except Exception:
    pn.extension(raw_css=[BUTTON_CSS])
import matplotlib.cm as cm
from bokeh.io import curdoc
import threading
#sys.path.append(r"/run/media/syedfahimahmed1/New Volume/Documents Fahim PC/GitHub/msc_py_build_old/bin")
import msc_py
print("Successful")
import scipy.ndimage as ndi
logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////////////////////////////////
class Canvas:
  
	# constructor
	def __init__(self, id, ViewChoice=None, drawsource = None):
		self.id=id # A unique identifier
		self.view_choice = ViewChoice # View Selection
		self.drawsource = drawsource
		self.fig=None # A Bokeh figure for plotting.
		self.pdim=2 # point dimension
		self.events={} # Event handling supporting various kinds of interactions

		self.box_select_tool_helper = TextInput(visible=False)
		self.fig_layout = Row(sizing_mode="stretch_both")

		# Initialize image bounds
		self.image_x_min = self.image_y_min = 0
		self.image_x_max = self.image_y_max = None

		# Initially, the bounding box is EMPTY - it will appear when BoxEditTool is activated
		self.bbox_source = ColumnDataSource(data=dict(x=[], y=[], width=[], height=[]))

		# Print Initial Bounding Box Values
		print("[Initial Bounding Box] - Empty Initially")
		print("No bounding box present initially.")

		# Callback to print updates when the bounding box is modified using BoxEditTool
		def bbox_callback(attr, old, new):
			if len(new["x"]) == 0:
				return                       # no box yet
			x0, y0, x1, y1 = bbox_corners(new)
			print(f"[BBox] LL=({x0},{y0})  UR=({x1},{y1}) "
				f"W={x1-x0} H={y1-y0}")
		
		self.bbox_source.on_change("data", bbox_callback)

		self.createFigure()  # Creates the main figure using Bokeh and adds

		# Ensure viewport starts correctly
		self.setViewport([0, 0, 256, 256])


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

	
	def set_image_bounds(self, xmax, ymax):
		"""
		Called once the IDX is open.  Re‑create the JS that keeps the
		rectangle inside the image.
		"""
		self.image_x_min, self.image_y_min = 0, 0
		self.image_x_max, self.image_y_max = xmax, ymax

		# wipe any previous JS callback
		self.bbox_source.js_property_callbacks.clear()

		# attach a new one with the correct numbers
		restrict_bbox_js = CustomJS(
			args=dict(source=self.bbox_source,
						xmin=0, xmax=xmax,
						ymin=0, ymax=ymax),
			code="""
				const d = source.data;
				if (d.x.length === 0) { return; }

				let cx = d.x[0],
					cy = d.y[0],
					w  = d.width[0],
					h  = d.height[0];

				cx = Math.max(xmin + w/2, Math.min(cx, xmax - w/2));
				cy = Math.max(ymin + h/2, Math.min(cy, ymax - h/2));

				w  = Math.min(w, xmax - xmin);
				h  = Math.min(h, ymax - ymin);

				d.x[0] = cx; d.y[0] = cy;
				d.width[0] = w; d.height[0] = h;
				source.change.emit();
			"""
		)
		self.bbox_source.js_on_change('data', restrict_bbox_js)



	def reset_axes_to_image(self, xmax, ymax):
		"""Show the full image extents on the left plot."""
		self.fig.x_range.start = 0
		self.fig.x_range.end   = xmax
		self.fig.y_range.start = 0
		self.fig.y_range.end   = ymax

	# createFigure
	def createFigure(self):
		old=self.fig

		self.pan_tool               = bokeh.models.PanTool()
		self.wheel_zoom_tool        = bokeh.models.WheelZoomTool()
		self.box_select_tool        = bokeh.models.BoxSelectTool()
		self.reset_fig              = bokeh.models.ResetTool()
		self.box_zoom_tool          = bokeh.models.BoxZoomTool()
		self.box_edit_tool          = bokeh.models.BoxEditTool(renderers=[])

		if self.view_choice  == "SYNC_VIEW": # sync_view bokeh options
			self.fig=bokeh.plotting.figure(tools=[self.pan_tool,self.reset_fig,self.wheel_zoom_tool,self.box_zoom_tool, self.box_edit_tool])

		else:
			self.fig=bokeh.plotting.figure(tools=[self.pan_tool,self.reset_fig,self.wheel_zoom_tool,self.box_select_tool,self.box_zoom_tool, self.box_edit_tool])

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
		self.fig.on_event(bokeh.events.MouseMove,      lambda evt: [fn(evt) for fn in self.events.get(bokeh.events.MouseMove,[])])
		
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
		print("Set Viewport Updated: x={}, y={}, w={}, h={}".format(x, y, w, h))


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
				source = bokeh.models.ColumnDataSource(data={"image": [img], "X": [x], "Y": [y], "dw": [w], "dh": [h]})
				
				#draw_source = bokeh.models.ColumnDataSource(data={"xs": [], "ys": []})  # Source for freehand drawings
				
				#print("draw_source", draw_source)
				if img.dtype == np.uint32:    
					self.fig.image_rgba("image", source=source, x="X", y="Y", dw="dw", dh="dh")

					
					# Add a multi_line glyph for freehand drawing
					self.fig.multi_line(xs="xs", ys="ys", line_color="green", line_width=2, source=self.drawsource)

					# Add a FreehandDrawTool
					freehand_tool = FreehandDrawTool(renderers=[self.fig.renderers[-1]], num_objects=100)  # Use the last renderer (multi_line)
					self.fig.add_tools(freehand_tool)
					#self.fig.toolbar.active_drag = freehand_tool  # Activate freehand drawing by default


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

	show_options = {
		"top": [
			["x0_input", "y0_input", "set_bbox_btn"],  # moved middle row here
			["menu_button", "scene", "timestep", "timestep_delta", "play_sec",
			"play_button", "palette", "color_mapper_type", "view_dependent",
			"resolution", "num_refinements", "show_probe", "box_edit_button"],
			["field", "direction", "offset", "range_mode", "range_min", "range_max"]
		],
		"middle": [],
		"bottom": []  # disable bottom row entirely
	}

	right_show_options = {
		"top": [["view_dependent", "annotate_btn", "predict_btn", "overlay_view_toggle", "save_tiff_btn"]],
	}

	# constructor
	def __init__(self, drawsource=None, ViewChoice=None): 
		super().__init__()  
		
		self.id=Slice.ID+1
		Slice.ID += 1
		self.job_id=0

		self.view_choice = ViewChoice # passing ViewChoice for sync view
		self.drawsource= drawsource

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

		self.black_path_source = ColumnDataSource(data=dict(xs=[], ys=[]))
		self.blue_path_source = ColumnDataSource(data=dict(xs=[], ys=[]))

		self.selected_node = None
		self.path_drawing_active = False
		self.last_click_time = 0
		self.saved_paths = []

		self.spt_parent = {}
		self.spt_distance = {}
		self.spt_edge_ids = {}
		self.spt_root_id = None

		# ROI box default size
		self.BOX_W = 1024
		self.BOX_H = 1024

		# Hover/placement state for left panel bbox
		self._bbox_hover_enabled = False   # following mouse?
		self._bbox_stuck = False           # frozen (double-click placed)?

		# Gate auto-loading inside load_right_panel_image():
		self._autoload_on_bbox_change = False

		MODEL_CKPT = "/app2/app_magicscan/best_model.pth"      # CHANGE
		self.tissue_model = TissuePredictor(
			model_path=MODEL_CKPT,
			tile_size=128,      # 128-pixel tiles
			overlap=64,         # 32-pixel blend
			unet_layers=4       # 4-layer U-Net; adapt if needed
		)
		self.createGui()

	def to_rgba(self, rgb):
		"""Convert RGB image to RGBA format compatible with Bokeh."""
		if len(rgb.shape) != 3 or rgb.shape[2] != 3:
			print("Invalid RGB shape, returning placeholder image.")
			ph = np.zeros((100, 100, 4), dtype=np.uint8)
			return ph.view(np.uint32).reshape(100, 100)   # <-- packed uint32
		
		X, Y, _ = rgb.shape
		rgba_image = np.dstack((rgb, 255 * np.ones((X, Y), dtype=np.uint8)))
		rgba_flat = np.zeros((X, Y), dtype=np.uint32)
		view = rgba_flat.view(dtype=np.uint8).reshape((X, Y, 4))
		view[:, :, :] = rgba_image
		return rgba_flat

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
	
	# ----------------------- image processing -----------------------

	def mean_curvature_blur_rgb(self, image: np.ndarray, iterations: int = 20, dt: float = 0.2) -> np.ndarray:
		"""Mean Curvature Flow per channel (small, stable step)."""
		blurred = image.astype(np.float32).copy()
		eps = 1e-5
		for _ in range(int(iterations)):
			for c in range(3):
				ch = blurred[:, :, c]
				gx  = np.gradient(ch, axis=1)
				gy  = np.gradient(ch, axis=0)
				gxx = np.gradient(gx, axis=1)
				gyy = np.gradient(gy, axis=0)
				gxy = np.gradient(gx, axis=0)
				denom = (gx*gx + gy*gy + eps)
				kflow = ((gx*gx)*gyy - 2*gx*gy*gxy + (gy*gy)*gxx) / denom
				blurred[:, :, c] = ch + dt * kflow
		return np.clip(blurred, 0, 255).astype(np.uint8)


	def sobel_like_gimp(self, rgb_img: np.ndarray, preblur_sigma: float = 0.0) -> np.ndarray:
		"""GIMP-like Sobel magnitude on RGB (expects RGB)."""
		gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)
		if preblur_sigma > 0:
			gray = cv2.GaussianBlur(gray, ksize=(0, 0), sigmaX=preblur_sigma)
		gx  = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
		gy  = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
		mag = cv2.magnitude(gx, gy)
		mag_norm = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
		return mag_norm.astype(np.uint8)


	def grayscale_image(self, image: np.ndarray) -> np.ndarray:
		"""RGB → grayscale (float32)."""
		g = np.dot(image[..., :3], [0.299, 0.587, 0.114])
		return g.astype(np.float32)


	def smooth_image(self, image: np.ndarray, sigma: float = 2.0) -> np.ndarray:
		return gaussian_filter(image, sigma=float(sigma)).astype(np.float32)


	def reverse_and_normalize(self, image: np.ndarray) -> np.ndarray:
		"""Invert and scale to [0,255] float32."""
		im = image.astype(np.float32)
		mn, mx = np.min(im), np.max(im)
		if mx <= mn + 1e-12:
			return np.zeros_like(im, dtype=np.float32)
		inv = mx - im
		out = (inv - np.min(inv)) / (np.max(inv) - np.min(inv))
		return (out * 255.0).astype(np.float32)

	# ----------------------- MSC & graph -----------------------

	def compute_msc_scalar_field(self, scalar_field: np.ndarray):
		"""Run MSC on scalar_field (float32)."""
		topo_id = msc_py.MakeMSCInstance()
		msc_py.ComputeMSC(topo_id, scalar_field.astype(np.float32), False, False)
		msc_py.SetMSCPersistence(topo_id, 3.2)
		msc_py.ComputePolylineGraph(topo_id, True)
		N, E = msc_py.GetGraph(topo_id)   # lists of nodes/edges (bindings-specific)
		return N, E


	def build_graph_from_msc(self, processed_img: np.ndarray, epsilon: float = 1e-4):
		"""Build undirected weighted graph; weight = intensity-weighted arc length + ε."""
		from collections import defaultdict

		self.coord_map = {node.id: np.array(node.geometry[0], dtype=float) for node in self.msc_nodes}
		self.edge_map = {}
		self.graph = defaultdict(list)
		self.edge_weight_map = {}

		self.min_edge_weight = float('inf')
		self.max_edge_weight = -float('inf')

		H, W = processed_img.shape

		def get_intensity(x: float, y: float) -> float:
			xi, yi = int(round(x)), int(round(y))
			if 0 <= xi < W and 0 <= yi < H:
				return float(processed_img[yi, xi])
			return 0.0

		for eidx, edge in enumerate(self.msc_edges):
			self.edge_map[eidx] = edge
			u, v = edge.from_, edge.to

			poly = edge.geometry
			if len(poly) < 2:
				w = float(epsilon)
				self.edge_weight_map[eidx] = w
				self.graph[u].append((v, w, eidx))
				self.graph[v].append((u, w, eidx))
				continue

			accum = 0.0
			for i in range(1, len(poly)):
				x1, y1 = map(float, poly[i-1])
				x2, y2 = map(float, poly[i])
				w1 = get_intensity(x1, y1)
				w2 = get_intensity(x2, y2)
				seg_len = float(np.hypot(x2 - x1, y2 - y1))
				accum += 0.5 * (w1 + w2) * seg_len

			accum += float(epsilon)
			self.edge_weight_map[eidx] = accum
			self.min_edge_weight = min(self.min_edge_weight, accum)
			self.max_edge_weight = max(self.max_edge_weight, accum)

			self.graph[u].append((v, accum, eidx))
			self.graph[v].append((u, accum, eidx))

		print(f"[EDGE WEIGHTS] min={self.min_edge_weight:.4f}, max={self.max_edge_weight:.4f}")


	# ---------- helpers: geometry <-> plot coords, KDTree ----------

	def _build_kdtree_plot(self):
		arr = getattr(self, "_last_rgb_roi", None)
		if arr is None or not isinstance(arr, np.ndarray) or arr.ndim < 2:
			self._node_tree = None
			self.node_xy_plot = []
			print("[KDTree] No/invalid _last_rgb_roi.")
			return

		H, W = arr.shape[:2]
		if not getattr(self, "msc_nodes", None):
			self._node_tree = None
			self.node_xy_plot = []
			print("[KDTree] No MSC nodes.")
			return

		node_xy_img = []
		for nd in self.msc_nodes:
			if hasattr(nd, "geometry"):
				x, y = nd.geometry[0]
			elif isinstance(nd, dict) and "x" in nd and "y" in nd:
				x, y = nd["x"], nd["y"]
			else:
				x, y = nd[0], nd[1]
			node_xy_img.append((float(x), float(y)))

		self.node_xy_plot = [(x, H - 1 - y) for (x, y) in node_xy_img]
		if not self.node_xy_plot:
			self._node_tree = None
			print("[KDTree] No node positions.")
			return

		from scipy.spatial import cKDTree as KDTree
		self._node_tree = KDTree(self.node_xy_plot)
		print(f"[KDTree] Built with {len(self.node_xy_plot)} nodes (H={H}, W={W}).")

	def _polyline_to_plot(self, edge):
		"""
		Convert an MSC edge polyline to plot coords with duplicate-point filtering.
		Returns (xs, ys) lists ready for multi_line.
		"""
		H, W = self._last_rgb_roi.shape[:2]
		xs, ys = [], []
		prev = None
		for x, y in edge.geometry:
			xi, yi = int(round(x)), int(round(H - 1 - y))  # flip y for plot
			if prev != (xi, yi):
				xs.append(xi)
				ys.append(yi)
				prev = (xi, yi)
		return xs, ys


	def compute_shortest_path_tree_from_root(self, root_node):
		"""Dijkstra SPT from root_node.id on self.graph."""
		if not hasattr(self, "graph") or not self.graph:
			raise RuntimeError("Graph not initialized. Run build_graph_from_msc() first.")

		import heapq
		t0 = time.time()

		dist, parent, edge_used = {}, {}, {}
		visited = set()
		root_id = root_node.id
		heap = [(0.0, root_id)]

		while heap:
			d, nid = heapq.heappop(heap)
			if nid in visited:
				continue
			visited.add(nid)
			dist[nid] = d
			for nb_id, w, e_id in self.graph[nid]:
				nd = d + w
				if nb_id not in dist or nd < dist[nb_id]:
					dist[nb_id] = nd
					parent[nb_id] = nid
					edge_used[nb_id] = e_id
					heapq.heappush(heap, (nd, nb_id))

		print(f"[TIME] SPT (Dijkstra) computation time: {time.time()-t0:.6f} s")
		self.spt_root_id = root_id
		self.spt_distance = dist
		self.spt_parent = parent
		self.spt_edge_ids = edge_used

	# ---------- event handlers (tap / hover / reset) ----------

	def select_msc_node(self, event):
		print(f"[TAP] got event: x={event.x}, y={event.y}")

		if not hasattr(self, "_node_tree") or self._node_tree is None:
			print("[TAP] KDTree not ready — click Annotate first.")
			return
		if event.x is None or event.y is None:
			print("[TAP] missing coords")
			return

		# guard: inside current plot ranges
		xr = self.right_panel_plot.x_range
		yr = self.right_panel_plot.y_range
		if not (xr.start <= event.x <= xr.end and yr.start <= event.y <= yr.end):
			print("[TAP] outside visible range")
			return

		dist, idx = self._node_tree.query([event.x, event.y])
		print(f"[TAP] nearest idx={idx}, dist={dist}")
		if np.isinf(dist) or idx is None:
			print("[TAP] no nearest node")
			return
		if dist > 60:  # generous tolerance
			print("[TAP] too far from any node")
			return

		clicked_node = self.msc_nodes[idx]

		# first click -> build SPT
		if self.selected_node is None:
			self.selected_node = clicked_node
			self.path_drawing_active = True
			self.compute_shortest_path_tree_from_root(clicked_node)
			cx, cy = self.node_xy_plot[idx]
			self._debug_draw_crosshair(int(cx), int(cy), length=12)
			print(f"[SELECT] root id={clicked_node.id}")
			return

		# same as root -> cancel
		if clicked_node.id == self.selected_node.id:
			print("[CANCEL] same node")
			self.selected_node = None
			self.path_drawing_active = False
			self.blue_path_source.data = dict(xs=[], ys=[])
			return

		# ensure reachable from root
		if clicked_node.id not in self.spt_parent:
			print("[PATH] clicked node not reachable from root")
			return

		# Build final path (polyline segments) to clicked node
		cur = clicked_node.id
		path_edges = []
		while cur in self.spt_parent:
			parent_id = self.spt_parent[cur]
			e_id = self.spt_edge_ids[cur]
			edge = self.edge_map[e_id]
			xs, ys = self._polyline_to_plot(edge)
			path_edges.append((xs, ys))
			cur = parent_id

		if not hasattr(self, "saved_paths"):
			self.saved_paths = []
		self.saved_paths.extend(reversed(path_edges))

		self.black_path_source.data = dict(
			xs=[xs for xs, _ in self.saved_paths],
			ys=[ys for _, ys in self.saved_paths],
		)
		self.blue_path_source.data = dict(xs=[], ys=[])

		print(f"[PATH] finalized to id={clicked_node.id}, segments={len(path_edges)}")
		self.selected_node = None
		self.path_drawing_active = False

	def hover_msc_edges(self, event):
		"""While in path mode, draw temporary preview from root to nearest node."""
		if not self.path_drawing_active or not getattr(self, "_node_tree", None):
			return
		if event.x is None or event.y is None:
			return

		# throttle a bit
		if hasattr(self, "last_hover_time") and (time.time() - self.last_hover_time < 0.08):
			return
		self.last_hover_time = time.time()

		dist, idx = self._node_tree.query([event.x, event.y])
		if np.isinf(dist) or idx is None:
			return

		cur = self.msc_nodes[idx].id
		if cur not in self.spt_parent:
			self.blue_path_source.data = dict(xs=[], ys=[])
			return

		preview = []
		while cur in self.spt_parent:
			p = self.spt_parent[cur]
			e_id = self.spt_edge_ids[cur]
			edge = self.edge_map[e_id]
			xs, ys = self._polyline_to_plot(edge)
			preview.append((xs, ys))
			cur = p

		self.blue_path_source.data = dict(
			xs=[xs for xs, _ in reversed(preview)],
			ys=[ys for _, ys in reversed(preview)],
		)

	def _debug_draw_crosshair(self, x: int = 10, y: int = 10, length: int = 50):
		xs = [[x - length, x + length], [x, x]]
		ys = [[y, y], [y - length, y + length]]
		self.blue_path_source.data = dict(xs=xs, ys=ys)

	def on_right_panel_reset(self, event=None):
		print("[RESET] Reset button pressed — clearing paths and selections.")
		self.saved_paths = []
		self.selected_node = None
		self.path_drawing_active = False
		self.black_path_source.data = dict(xs=[], ys=[])
		self.blue_path_source.data = dict(xs=[], ys=[])

	# ---------- idempotent layer creation + robust (re)wiring ----------

	def _ensure_right_panel_layers_and_events(self):
		"""Ensure multi_line layers exist and events are wired (idempotent)."""
		if not hasattr(self, "right_panel_plot"):
			print("[ENSURE] No right_panel_plot yet.")
			return

		have_black = any(getattr(r, "data_source", None) is self.black_path_source
						for r in self.right_panel_plot.renderers)
		have_blue  = any(getattr(r, "data_source", None) is self.blue_path_source
						for r in self.right_panel_plot.renderers)

		if not have_black:
			self.right_panel_plot.multi_line(xs='xs', ys='ys', source=self.black_path_source,
											line_color='black', line_width=2, alpha=0.8)
			print("[ENSURE] Added black multi_line.")
		if not have_blue:
			self.right_panel_plot.multi_line(xs='xs', ys='ys', source=self.blue_path_source,
											line_color='blue', line_width=2, alpha=0.8)
			print("[ENSURE] Added blue multi_line.")

		# keep pan/box tools from stealing taps
		self.right_panel_plot.toolbar.active_drag = None

		if not getattr(self, "_right_events_wired", False):
			print("[ENSURE] Wiring events on right_panel_plot.")
			self.right_panel_plot.on_event(bokeh.events.Tap,       self.select_msc_node)
			self.right_panel_plot.on_event(bokeh.events.MouseMove, self.hover_msc_edges)
			self.right_panel_plot.on_event(bokeh.events.Reset,     self.on_right_panel_reset)
			self._right_events_wired = True
		else:
			print("[ENSURE] Events already wired.")

	def _force_wire_events_now(self):
		"""
		Bind Tap/Move/Reset to the *current* right_panel_plot.
		Clears any JS callbacks copied across plot instances.
		"""
		if not hasattr(self, "right_panel_plot"):
			return

		# Try to clear previous low-level subscriptions if the figure was replaced
		try:
			self.right_panel_plot.js_event_callbacks.clear()
		except Exception:
			pass
		try:
			self.right_panel_plot.subscribed_events = set()
		except Exception:
			pass

		self.right_panel_plot.toolbar.active_drag = None
		self.right_panel_plot.on_event(bokeh.events.Tap,       self.select_msc_node)
		self.right_panel_plot.on_event(bokeh.events.MouseMove, self.hover_msc_edges)
		self.right_panel_plot.on_event(bokeh.events.Reset,     self.on_right_panel_reset)
		print("[ENSURE] (re)wired Tap/Move/Reset on right_panel_plot")

	# ---------- ROI load (RGB-only) ----------

	def load_right_panel_image(self, attr, old, new):
		# Prevent autoloading during hover (on_change provides a real 'attr')
		if attr is not None and not getattr(self, "_autoload_on_bbox_change", False):
			return
		
		start_time = time.time()
		bbox = self.canvas.bbox_source.data
		if len(bbox.get('x', [])) == 0:
			return

		# 1) logic box from current rectangle
		x0, y0, x1, y1 = bbox_corners(bbox)
		logic_box = ([x0, y0], [x1, y1])

		# 2) fetch RGB patch
		db = self.db
		access = db.createAccess()
		endh = db.getMaxResolution()
		result = list(ExecuteBoxQuery(db, access=access, logic_box=logic_box, endh=endh, num_refinements=1))[0]
		rgb_image = result['data']  # H×W×3 uint8

		# 3) cache
		self._last_rgb_roi = rgb_image.copy()
		self._last_bbox_ll = (x0, y0)

		# 4) pack to uint32 + overlay toggle
		rgba_image = self.to_rgba(rgb_image)  # H×W uint32
		H, W = rgba_image.shape
		self._rgb_uint32 = rgba_image
		self._rgba_overlay = None
		if hasattr(self, "overlay_view_toggle"):
			self.overlay_view_toggle.disabled = True
			self.overlay_view_toggle.value = False

		# 5) reset annotation state
		self.saved_paths = []
		self.black_path_source.data = dict(xs=[], ys=[])
		self.blue_path_source.data  = dict(xs=[], ys=[])
		self.selected_node = None
		self.path_drawing_active = False
		self.msc_nodes = []
		self.msc_edges = []
		self.graph = {}
		self.spt_parent = {}
		self.spt_distance = {}
		self.spt_edge_ids = {}
		self.spt_root_id = None
		self._node_tree = None
		self.node_xy_plot = []

		# 6) update existing figure only (no re-mount)
		img = rgba_image
		H, W = img.shape
		self._rp_img_src.data = dict(image=[img], x=[0], y=[0], dw=[W], dh=[H])
		self.right_panel_plot.x_range.start, self.right_panel_plot.x_range.end = 0, W
		self.right_panel_plot.y_range.start, self.right_panel_plot.y_range.end = 0, H
		self.right_panel_plot.toolbar.active_drag = None
		self.right_panel_plot.toolbar.active_scroll  = None
		self.right_panel_plot.toolbar.active_tap     = None

		# 7) info
		if hasattr(self, "right_info"):
			self.right_info.object = (
				f"**Cropped ROI:** Lower Left: ({x0},{y0}) Upper Right: ({x1},{y1}) "
				f"Size: {(x1-x0)}x{(y1-y0)} px"
			)

		print(f"[RGB-only] load_right_panel_image {time.time() - start_time:.4f}s")
		pn.state.notifications.info("Loaded RGB patch. Click 'Annotate' to enable graph tools.")

	# ---------- bbox UI helpers (unchanged logic; calls loader) ----------

	def _get_left_image_bounds(self):
		"""
		Return (xmin, ymin, xmax, ymax) in left image data units.
		Adjust if your left canvas shows only a subset; default uses full image.
		"""
		xmax = self.canvas.image_x_max if self.canvas.image_x_max is not None else None
		ymax = self.canvas.image_y_max if self.canvas.image_y_max is not None else None
		if xmax is None or ymax is None:
			# Fallback: don’t clamp if not known yet
			return (-1e12, -1e12, 1e12, 1e12)
		return (0.0, 0.0, float(xmax), float(ymax))

	def _ensure_rect_renderer(self):
		# Ensure the red rectangle exists and is tied to the bbox_source
		if not hasattr(self.canvas, "rect_renderer") or self.canvas.rect_renderer not in self.canvas.fig.renderers:
			self.canvas.rect_renderer = self.canvas.fig.rect(
				x="x", y="y", width="width", height="height",
				source=self.canvas.bbox_source,
				line_color="red", line_width=3, fill_alpha=0.3, level="overlay"
			)
			# You can keep the BoxEditTool renderer list if you still want drag-edit later:
			self.canvas.box_edit_tool.renderers = [self.canvas.rect_renderer]
	
	def _take_over_doubletap(self):
		"""
		During ROI placement we *temporarily* replace ALL Canvas DoubleTap handlers
		with ONLY our onCanvasDoubleTap, so ProbeTool (and others) cannot fire.
		"""
		# Save everything that was there
		self._saved_doubletap_handlers = list(self.canvas.events.get(bokeh.events.DoubleTap, []) or [])
		# Clear and re-register ONLY our handler
		self.canvas.events[bokeh.events.DoubleTap] = []
		# IMPORTANT: re-add OUR handler via the same API Canvas uses, so it’s wrapped consistently
		self.canvas.on_event(bokeh.events.DoubleTap, SafeCallback(self.onCanvasDoubleTap))
		# (No-op if our handler was already there; we now have only ours.)

	def _restore_doubletap(self):
		"""Restore whatever DoubleTap handlers were present before placement."""
		if hasattr(self, "_saved_doubletap_handlers"):
			self.canvas.events[bokeh.events.DoubleTap] = list(self._saved_doubletap_handlers)
			self._saved_doubletap_handlers = []


	def _enable_bbox_hover_mode(self):
		"""Enter hover mode: rect follows mouse on left panel."""
		self._ensure_rect_renderer()
		self._bbox_hover_enabled = True
		self._bbox_stuck = False

		data = self.canvas.bbox_source.data
		if len(data.get("width", [])) == 0:
			self.canvas.bbox_source.data = dict(
				x=[self.BOX_W/2], y=[self.BOX_H/2], width=[self.BOX_W], height=[self.BOX_H]
			)

		if hasattr(self.canvas, "pan_tool"):
			self.canvas.fig.toolbar.active_drag = self.canvas.pan_tool
		self.canvas.fig.toolbar.active_scroll = None
		self.canvas.fig.toolbar.active_tap    = None

		# <<< TAKE OVER DoubleTap so ProbeTool cannot fire >>>
		self._take_over_doubletap()

		print("[BBox] Hover mode: ON — move mouse; Double-click to stick & load; single-click to resume hover.")

	def _disable_bbox_hover_mode(self):
		"""Leave hover mode (box stays where it is)."""
		self._bbox_hover_enabled = False

		# <<< RESTORE whatever DoubleTap listeners were there (including ProbeTool) >>>
		self._restore_doubletap()

		print("[BBox] Hover mode: OFF")


	def toggle_box_edit(self, event):
		"""
		New behavior:
		- Click button -> enter hover-to-place mode (box follows mouse).
		- Double-click on left -> stick box & load ROI to right.
		- Single-click -> resume hover mode.
		"""
		if self._bbox_hover_enabled and not self._bbox_stuck:
			# Clicking the button again cancels hover
			self._disable_bbox_hover_mode()
			print("Bounding Box: hover canceled (Pan enabled).")
			return

		# Start (or restart) hover mode
		self._enable_bbox_hover_mode()

	def set_bbox(self, event):
		try:
			x0 = int(self.x0_input.value)
			y0 = int(self.y0_input.value)
		except ValueError:
			pn.state.notifications.error("x0 and y0 must be integers.")
			return

		data = self.canvas.bbox_source.data
		w = data["width"][0] if len(data.get("width", [])) else 1024
		h = data["height"][0] if len(data.get("height", [])) else 1024

		cx = x0 + w/2
		cy = y0 + h/2

		self.canvas.bbox_source.data = dict(x=[cx], y=[cy], width=[w], height=[h])

		if not hasattr(self.canvas, "rect_renderer") or \
		self.canvas.rect_renderer not in self.canvas.fig.renderers:
			self.canvas.rect_renderer = self.canvas.fig.rect(
				x="x", y="y", width="width", height="height",
				source=self.canvas.bbox_source,
				line_color="red", line_width=3,
				fill_alpha=0.3, level="overlay"
			)
			self.canvas.box_edit_tool.renderers = [self.canvas.rect_renderer]

		self.canvas.fig.toolbar.active_drag = self.canvas.box_edit_tool
		self.load_right_panel_image(None, None, None)

	# ---------- annotate orchestrator ----------

	def _on_annotate_click(self, _):
		if not hasattr(self, "_last_rgb_roi"):
			pn.state.notifications.error("Load an ROI first (draw box or use SET).")
			return

		# pipeline (your current code)
		rgb = self._last_rgb_roi
		blurred = self.mean_curvature_blur_rgb(rgb); self._last_mean_curve = blurred.copy()
		gb = blurred.copy(); gb[:, :, 0] = 0
		edges_gray = self.sobel_like_gimp(gb, preblur_sigma=0.6)
		sobel_gb = np.zeros_like(gb); sobel_gb[:, :, 1] = edges_gray; sobel_gb[:, :, 2] = edges_gray
		self._last_sobel_roi = sobel_gb.copy()

		gray = self.grayscale_image(sobel_gb)
		sm   = self.smooth_image(gray, sigma=2)
		proc = self.reverse_and_normalize(sm)

		t0 = time.time()
		self.msc_nodes, self.msc_edges = self.compute_msc_scalar_field(proc)
		self.build_graph_from_msc(proc)
		self._build_kdtree_plot()
		print(f"[Annotate] MSC+graph: {time.time()-t0:.3f}s")

		# ensure tools don’t steal taps; no remount
		self.right_panel_plot.toolbar.active_drag    = None
		self.right_panel_plot.toolbar.active_scroll  = None
		self.right_panel_plot.toolbar.active_tap     = None

		pn.state.notifications.success(
			"Annotation ready — click to choose a start node, then hover or click a target."
		)

	def _apply_black_lines(
		self,
		rgb: np.ndarray,        # H×W×3 uint8
		prob: np.ndarray,       # H×W float (0..1) or uint8 (0..255)
		p_thresh: float = 0.03, # if uint8 & left at 0.03 -> legacy 247; else scaled/absolute
		dilate: int = 0         # thickness (morphological dilation iters)
	) -> np.ndarray:
		"""
		1) Threshold prob → binary mask
		2) (Optional) dilate to thicken lines
		3) Paint black pixels onto a copy of rgb
		4) Pack to uint32 RGBA for Bokeh
		Returns: HxW uint32 (packed RGBA)
		"""
		# ---- validate ----
		if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
			raise ValueError(f"rgb must be HxWx3 uint8, got shape={rgb.shape}, dtype={rgb.dtype}")
		if prob.ndim != 2 or prob.shape != rgb.shape[:2]:
			raise ValueError(f"prob must be HxW aligned with rgb, got {prob.shape} vs {rgb.shape[:2]}")

		H, W, _ = rgb.shape

		# ---- 1) threshold → mask ----
		if prob.dtype == np.uint8:
			if p_thresh == 0.03:            # legacy default
				thr = 247
			else:
				thr = int(round(p_thresh*255)) if p_thresh < 1 else int(p_thresh)
			mask = prob > thr
		else:
			# floats/other numeric → treat as probabilities; ignore NaNs
			prob_f = np.asarray(prob, dtype=np.float32)
			mask = np.greater(prob_f, float(p_thresh), where=~np.isnan(prob_f))

		# ---- 2) dilate (optional) ----
		if dilate and int(dilate) > 0:
			mask = ndi.binary_dilation(mask, iterations=int(dilate))

		# ---- no lines? return packed RGB ----
		if not mask.any():
			return self.to_rgba(rgb)
		
		self._last_mask = mask.astype(np.uint8)       # store for saving
		# ---- 3) paint black on a copy ----
		painted = rgb.copy()
		painted[mask] = (0, 0, 0)

		# ---- 4) pack to uint32 RGBA ----
		rgba_flat = np.zeros((H, W), dtype=np.uint32)
		view = rgba_flat.view(np.uint8).reshape(H, W, 4)
		view[..., :3] = painted
		view[...,  3] = 255
		return rgba_flat
	
	def save_tiff(self, _):
		"""
		Save the current ROI in three TIFFs:
		<stem>.tiff        (RGB)
		<stem>_sobel.tiff  (Sobel/MSC preview, RGB or RGBA)
		<stem>_mask.tiff   (DL boundary mask, single-channel L, 0/255)

		<stem> := <case>_<type>_<x0>_<y0>_<timestamp>
		"""
		# ── guards ─────────────────────────────────────────────────
		if not hasattr(self, "_last_rgb_roi"):
			pn.state.notifications.error("No ROI loaded yet!")
			return
		if not hasattr(self, "_last_sobel_roi"):
			pn.state.notifications.error("Edge image not available yet!")
			return
		if not hasattr(self, "_last_mask"):
			pn.state.notifications.error("Run “Predict Boundary” first!")
			return
		if not (hasattr(self, "current_case") and hasattr(self, "current_type")):
			pn.state.notifications.error("Missing case/type context!")
			return

		# ── fetch & flip to match GUI orientation ──────────────────
		rgb   = np.flipud(self._last_rgb_roi)     # H×W×3
		sobel = np.flipud(self._last_sobel_roi)   # H×W×3 or ×4
		mask  = np.flipud(self._last_mask)        # H×W (bool or 0/1/0/255)

		# ── coerce dtypes ──────────────────────────────────────────
		if rgb.dtype   != np.uint8: rgb   = np.clip(rgb,   0, 255).astype(np.uint8)
		if sobel.dtype != np.uint8: sobel = np.clip(sobel, 0, 255).astype(np.uint8)

		# mask → uint8 (0/255)
		if mask.dtype == np.bool_:
			mask = mask.astype(np.uint8) * 255
		else:
			mask = (mask > 0).astype(np.uint8) * 255

		sobel_mode = "RGBA" if (sobel.ndim == 3 and sobel.shape[-1] == 4) else "RGB"

		# ── filenames ──────────────────────────────────────────────
		x0, y0 = self._last_bbox_ll
		ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
		stem = f"{self.current_case}_{self.current_type}_{x0}_{y0}_{ts}"

		rgb_fn  = Path.cwd() / f"{stem}.tiff"
		sob_fn  = Path.cwd() / f"{stem}_sobel.tiff"
		mask_fn = Path.cwd() / f"{stem}_mask.tiff"

		# ── write ──────────────────────────────────────────────────
		Image.fromarray(rgb,   mode="RGB").save(rgb_fn,  format="TIFF")
		Image.fromarray(sobel, mode=sobel_mode).save(sob_fn, format="TIFF")
		Image.fromarray(mask,  mode="L").save(mask_fn,  format="TIFF")

		# ── notify ─────────────────────────────────────────────────
		pn.state.notifications.success(
			f"Saved {rgb_fn.name}, {sob_fn.name} & {mask_fn.name}"
		)
		print(f"[TIFF saved] → {rgb_fn.resolve()}")
		print(f"[TIFF saved] → {sob_fn.resolve()}")
		print(f"[TIFF saved] → {mask_fn.resolve()}")
	
	def _on_predict_click(self, _):
		"""
		Button callback — synchronous (no background thread).

		1) Run UNet on current ROI
		2) Paint black boundary pixels onto a copy of the RGB
		3) Cache overlay and swap the right-panel image (respecting the toggle)
		"""
		# ---- 0) guards ---------------------------------------------------------
		if not hasattr(self, "_last_rgb_roi"):
			pn.state.notifications.error("Draw a ROI first")
			return
		if self.tissue_model is None:
			pn.state.notifications.error("Model not loaded")
			return

		# clear previous path state
		self.saved_paths = []
		self.black_path_source.data = dict(xs=[], ys=[])
		self.blue_path_source.data  = dict(xs=[], ys=[])
		self.selected_node = None
		self.path_drawing_active = False
		print("[RESET] Cleared red/blue paths due to bounding box update.")
		pn.state.notifications.info("Running boundary model…")

		# ---- 1) inference ------------------------------------------------------
		rgb = self._last_rgb_roi.copy()  # HxWx3 uint8
		prob = self.tissue_model.predict_array(rgb)  # HxW float32 (0..1)
		try:
			print("Prob stats:", float(np.nanmin(prob)), float(np.nanmax(prob)), float(np.nanmean(prob)))
		except Exception:
			pass

		# ---- 2) paint + pack (HxW uint32) -------------------------------------
		rgba = self._apply_black_lines(rgb, prob, p_thresh=0.03, dilate=1)

		# coerce to packed HxW uint32 (defensive if _apply_black_lines ever changes)
		if isinstance(rgba, (tuple, list)):
			rgba = rgba[0]
		rgba = np.asarray(rgba)
		if rgba.ndim == 3 and rgba.shape[2] == 4 and rgba.dtype == np.uint8:
			rgba = rgba.view(np.uint32).reshape(rgba.shape[0], rgba.shape[1])
		if not (rgba.dtype == np.uint32 and rgba.ndim == 2):
			pn.state.notifications.error("Overlay format unexpected; unable to display.")
			return

		# ---- 3) cache + toggle + draw -----------------------------------------
		self._rgba_overlay = rgba
		# ensure base RGB cache exists (for fallback)
		if getattr(self, "_rgb_uint32", None) is None and hasattr(self, "_last_rgb_roi"):
			self._rgb_uint32 = self.to_rgba(self._last_rgb_roi)

		# enable toggle; auto-switch to overlay
		self.overlay_view_toggle.disabled = False
		self.overlay_view_toggle.value = True

		H, W = rgba.shape

		# if renderer not created yet (should exist from ROI load), create it now
		if self._main_renderer is None:
			# if right_panel_plot not yet created, bail gracefully
			if not hasattr(self, "right_panel_plot"):
				pn.state.notifications.error("Right panel not initialized.")
				return
			src = bokeh.models.ColumnDataSource(
				data=dict(image=[rgba], x=[0], y=[0], dw=[W], dh=[H])
			)
			self._main_renderer = self.right_panel_plot.image_rgba(
				"image", source=src, x="x", y="y", dw="dw", dh="dh"
			)
		else:
			# honor toggle: overlay if True, else RGB
			img = rgba if self.overlay_view_toggle.value and (self._rgba_overlay is not None) else self._rgb_uint32
			h, w = img.shape
			self._main_renderer.data_source.data = dict(image=[img], x=[0], y=[0], dw=[w], dh=[h])

		pn.state.notifications.success("Boundary overlay updated")

	def _on_overlay_view_toggled(self, event):
		show_overlay = bool(event.new)

		# guards
		if self._main_renderer is None:
			return
		if getattr(self, "_rgb_uint32", None) is None:
			# try to build it from last ROI if missing
			if hasattr(self, "_last_rgb_roi"):
				self._rgb_uint32 = self.to_rgba(self._last_rgb_roi)
			else:
				return

		if show_overlay and getattr(self, "_rgba_overlay", None) is None:
			# no overlay yet; revert and notify
			self.overlay_view_toggle.value = False
			try:
				pn.state.notifications.info("No boundary overlay yet. Click 'Predict Boundary' first.")
			except Exception:
				pass
			return

		# if True -> show overlay (_rgba_overlay); if False -> show RGB (_rgb_uint32)
		img = (self._rgba_overlay if event.new else self._rgb_uint32)
		if img is None:
			return
		H, W = img.shape
		self._rp_img_src.data = dict(image=[img], x=[0], y=[0], dw=[W], dh=[H])

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
	
	# In your Slice class, add a helper method to set up right panel options:
	def setRightShowOptions(self, options):
		def resolve(names):
			out = []
			for n in names:
				w = getattr(self, n.replace("-", "_"), None)
				if w is not None:
					out.append(w)
			return out

		# flatten all "top" rows into one list and render as one toolbar row
		top_names = []
		for row in options.get("top", [[]]):
			top_names.extend(row)
		top_widgets = resolve(top_names)

		toolbar = pn.Row(
			*top_widgets,
			sizing_mode="stretch_width",
			css_classes=["right-toolbar"],   # uses the CSS above for gap/centering
			margin=(4, 0, 6, 0),
		)

		# Keep a single Column so we can add a "bottom" row later if needed
		return pn.Column(toolbar, sizing_mode="stretch_both")

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

		self.canvas = Canvas(self.id, self.view_choice, self.drawsource)
		self.canvas.on_event(bokeh.events.RangesUpdate     , SafeCallback(self.onCanvasViewportChange))
		self.canvas.on_event(bokeh.events.MouseMove        , SafeCallback(self.onCanvasMouseMove))
		self.canvas.on_event(bokeh.events.Tap              , SafeCallback(self.onCanvasSingleTap))
		self.canvas.on_event(bokeh.events.DoubleTap        , SafeCallback(self.onCanvasDoubleTap))
		self.canvas.on_event(bokeh.events.SelectionGeometry, SafeCallback(self.onCanvasSelectionGeometry))

        # --- Right panel: create ONCE, wire ONCE ---
		from bokeh.models import ColumnDataSource, TapTool, CrosshairTool, CustomJS

		H0, W0 = 1, 1  # placeholder; will be updated on first ROI

		# image datasource that we will update on every ROI
		self._rp_img_src = ColumnDataSource(data=dict(
			image=[np.zeros((H0, W0), np.uint32)], x=[0], y=[0], dw=[W0], dh=[H0]
		))

		# reuse your existing sources if already present
		self.black_path_source = getattr(self, "black_path_source", ColumnDataSource(data=dict(xs=[], ys=[])))
		self.blue_path_source  = getattr(self, "blue_path_source",  ColumnDataSource(data=dict(xs=[], ys=[])))

		# IMPORTANT: don't read inner_width/inner_height here (they aren't set yet).
		# Let it stretch and Panel will size it.
		self.right_panel_plot = bokeh.plotting.figure(
			x_range=(0, W0), y_range=(0, H0),
			tools="pan,wheel_zoom,reset",
			match_aspect=True,
			sizing_mode="stretch_both",
			output_backend="webgl",
		)

		# base image + path layers
		self._main_renderer = self.right_panel_plot.image_rgba(
			"image", source=self._rp_img_src, x="x", y="y", dw="dw", dh="dh"
		)
		self.right_panel_plot.multi_line(xs='xs', ys='ys', source=self.black_path_source,
										line_color='black', line_width=2, alpha=0.8)
		self.right_panel_plot.multi_line(xs='xs', ys='ys', source=self.blue_path_source,
										line_color='blue',  line_width=2, alpha=0.8)

		# tools / events (wire ONCE)
		if not any(isinstance(t, TapTool) for t in self.right_panel_plot.tools):
			self.right_panel_plot.add_tools(TapTool(), CrosshairTool())

		# Make sure drag doesn’t steal taps
		self.right_panel_plot.toolbar.active_drag    = None
		self.right_panel_plot.toolbar.active_scroll  = None
		self.right_panel_plot.toolbar.active_tap     = None
		self.right_panel_plot.toolbar.active_inspect = None

		# Python callbacks (server-side)
		self.right_panel_plot.on_event(bokeh.events.Tap,       self.select_msc_node)
		self.right_panel_plot.on_event(bokeh.events.MouseMove, self.hover_msc_edges)
		self.right_panel_plot.on_event(bokeh.events.Reset,     self.on_right_panel_reset)

		# Optional: JS probe to confirm taps
		self._tap_debug_src = ColumnDataSource(data=dict(x=[], y=[]))
		self.right_panel_plot.circle('x', 'y', source=self._tap_debug_src, size=7, alpha=0.9, color="lime")
		self.right_panel_plot.js_on_event('tap', CustomJS(args=dict(s=self._tap_debug_src), code="""
			if (cb_obj.x==null || cb_obj.y==null) return;
			s.data.x = [cb_obj.x];
			s.data.y = [cb_obj.y];
			s.change.emit();
			console.log('[JS TAP]', cb_obj.x, cb_obj.y);
		"""))

		self.box_edit_button = Button(name="Bounding Box", button_type="primary")
		self.box_edit_button.on_click(self.toggle_box_edit)
		if self.canvas.view_choice == "SYNC_VIEW":
			self.image_type = pn.widgets.TextInput(name="", sizing_mode='stretch_width', disabled=False) # Sync-View Image Title
		else:
			self.image_type = None

		# ---- LOWER‑LEFT CORNER INPUTS ---------------------------------------------
		self.x0_input = IntInput(name="x0 (Lower Left corner)", step=1, value=0, width=130)
		self.y0_input = IntInput(name="y0 (Lower Left corner)", step=1, value=0, width=130)

		self.set_bbox_btn = Button(name="SET", button_type="primary")
		self.set_bbox_btn.css_classes = ["pill"]
		self.set_bbox_btn.on_click(self.set_bbox)

		# Annotate (run Sobel→MSC & wire interactions on demand)
		self.annotate_btn = pn.widgets.Button(
			name="Annotate",
			button_type="primary",
		)
		self.annotate_btn.css_classes = ["pill"]
		self.annotate_btn.on_click(self._on_annotate_click)

		self.predict_btn = pn.widgets.Button(
			name="Predict Boundary",
			button_type="warning",
			disabled=(self.tissue_model is None),
		)
		self.predict_btn.css_classes = ["pill"]
		self.predict_btn.on_click(self._on_predict_click)

		# Right-panel view toggle (RGB <-> Overlay)
		self.overlay_view_toggle = pn.widgets.Toggle(
			name="Toggle",
			value=False,
			button_type="primary",
			disabled=True,
		)
		self.overlay_view_toggle.css_classes = ["pill"]
		self.overlay_view_toggle.param.watch(self._on_overlay_view_toggled, "value")

		# Save / Predict / Toggle (uniform look; size driven by label)
		self.save_tiff_btn = pn.widgets.Button(name="Save TIFF", button_type="success")
		self.save_tiff_btn.css_classes = ["pill"]
		self.save_tiff_btn.on_click(self.save_tiff)

		# (no manual width overrides)
		self._rgb_uint32    = None   # set in load_right_panel_image
		self._rgba_overlay  = None   # set after prediction

		# probe_tool
		from openvisuspy.probe import ProbeTool
		self.probe_tool=ProbeTool(self)
		
		self.show_probe=pn.widgets.Toggle(name='Probe',value=False, width=60, align=('start', 'end'), button_style='outline', button_type='primary')
		self.show_probe.param.watch(SafeCallback(lambda evt: self.setShowProbe(evt.new)),"value")

		self.setShowOptions(Slice.show_options)
		self.right_image = Bokeh(self.right_panel_plot)   # <-- use right_panel_plot (NOT canvas.fig)
		self.right_info = pn.pane.Markdown("**Cropped ROI:** None")
		self.right_options = self.setRightShowOptions(self.right_show_options)

		# In createGui (or similar initialization):
		self.canvas.bbox_source.on_change("data", self.load_right_panel_image)
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

	def onCanvasMouseMove(self, event):
		"""While hovering (and not stuck), keep LOWER-LEFT of the box under the cursor (clamped)."""
		if not self._bbox_hover_enabled or self._bbox_stuck:
			return
		if event.x is None or event.y is None:
			return
		xmin, ymin, xmax, ymax = self._get_left_image_bounds()
		w, h = float(self.BOX_W), float(self.BOX_H)

		x_ll = max(xmin, min(event.x, xmax - w))
		y_ll = max(ymin, min(event.y, ymax - h))
		cx = x_ll + w/2.0
		cy = y_ll + h/2.0

		# Update center-based rect (NO autoload during hover)
		self.canvas.bbox_source.data = dict(x=[cx], y=[cy], width=[w], height=[h])

	def onCanvasDoubleTap(self, event):
		"""Double-click: stick the box and load the ROI once."""
		if event.x is None or event.y is None:
			return
		xmin, ymin, xmax, ymax = self._get_left_image_bounds()
		w, h = float(self.BOX_W), float(self.BOX_H)

		x_ll = max(xmin, min(event.x, xmax - w))
		y_ll = max(ymin, min(event.y, ymax - h))
		cx = x_ll + w/2.0
		cy = y_ll + h/2.0

		# Finalize rect
		self.canvas.bbox_source.data = dict(x=[cx], y=[cy], width=[w], height=[h])

		# Freeze, exit hover, and load explicitly
		self._bbox_stuck = True
		self._disable_bbox_hover_mode()

		print(f"[BBox] STUCK at LL=({x_ll:.1f},{y_ll:.1f}) — loading ROI")
		self._autoload_on_bbox_change = False
		self.load_right_panel_image(None, None, None)

	def onCanvasSingleTap(self, event):
		"""Single-click: resume hover placement so you can pick another ROI quickly."""
		print("[BBox] Single-click: resume hover mode")
		self._enable_bbox_hover_mode()

	# getShowOptions
	def getShowOptions(self):
		return self.show_options

	# setShowOptions
	def setShowOptions(self, value):
		self.show_options=value
		#print(">>> Requested layout:", value)      # <‑‑ add
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
		middle = [Row(*CreateWidgets(row), sizing_mode="fixed") for row in value.get("middle", [])]
		bottom=[Row(*CreateWidgets(row),sizing_mode="stretch_width") for row in value.get("bottom",[[]])]

		self.central_layout[:]=[
					*top,
					self.canvas.fig_layout,
					*middle,
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
		
		dims = [int(v) for v in self.db.getLogicSize()]  # [X, Y, (Z)]
		self.canvas.set_image_bounds(dims[0]-1, dims[1]-1)
		self.canvas.reset_axes_to_image(dims[0]-1, dims[1]-1)

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
		# self.canvas.showData(min(pdim,2), data, self.toPhysic(logic_box), color_bar= self.color_bar) # self.color_bar
		# disabled colorbar
		self.canvas.showData(min(pdim,2), data, self.toPhysic(logic_box), color_bar= None)
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