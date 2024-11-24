import os,sys,logging

logger = logging.getLogger(__name__)

import numpy as np
from statistics import mean, median

from .slice  import  Slice
from .backend import ExecuteBoxQuery
from .utils   import *

import bokeh.plotting 
import bokeh.events
import bokeh.models.scales

import param
import panel as pn

# //////////////////////////////////////////////////////////////////////////////////////
class Probe:

	# constructor
	def __init__(self, dir, slot):
		self.dir     = dir
		self.slot    = slot
		self.pos     = None
		self.enabled = True

# //////////////////////////////////////////////////////////////////////////////////////
class ProbeTool(param.Parameterized):

	# constructor
	def __init__(self, slice):
		self.slice=slice
		
		self.probes = {}
		self.renderers = {"offset": None}
		for dir in range(3):
			self.probes[dir] = []
			for slot in range(len(COLORS)):
				probe = Probe(dir, slot)
				self.probes[dir].append(probe)
				self.renderers[probe] = {
					"canvas": [], # i am drwing on slice.canva s
					"fig": []     # or probe fig
				}
		self.createGui()

	# getActiveProbes
	def getActiveProbes(self):
		ret=[]
		for dir in range(3):
			for probe in self.probes[dir]:
				if probe.enabled and probe.pos is not None:
					ret.append(probe)
		return ret

	# getBody
	def getBody(self):

		ret= {
				"nx":             self.num_points_x.value, 
				"ny":             self.num_points_y.value,
				"op":             self.z_op.value,
				"res":            self.z_res.value,
				"probes":[
					{
						"dir":  probe.dir, 
						"slot": probe.slot, 
						"pos":  probe.pos
					} for probe in  self.getActiveProbes()
				]
			}

		return ret

	# recomputeAllProbes
	def setBody(self, body):
		self.slot=None
		self.removeAllProbes()

		self.num_points_x.value  = body.get("nx",2)
		self.num_points_y.value  = body.get("ny",2)
		self.z_op.value          = body.get("z_op","avg")
		self.z_res.value         = body.get("z_res",24)

		for dir in range(3):
			for probe in self.probes[dir]:
				for it in body.get("probes",[]):
					if probe.dir==it["dir"] and probe.slot==it["slot"]:
						probe.pos=it["pos"]
						probe.enabled=True
						break

	# createFigure
	def createFigure(self):

		ret=bokeh.plotting.figure(
			title=None,
			sizing_mode="stretch_both",
			active_scroll="wheel_zoom",
			toolbar_location=None,
			x_axis_label="Z", x_range=[0.0,256.0],x_axis_type="linear",
			y_axis_label="f", y_range=[0.0,256.0],y_axis_type=self.slice.color_mapper_type.value
			)

		# change the offset on the proble plot (NOTE evt.x in is physic domain)
		def handleDoubleTap(evt): 
			self.slice.offset.value=evt.x

		ret.on_event(bokeh.events.DoubleTap, handleDoubleTap)

		self.fig_placeholder[:]=[ret]
		return ret

		
	# createGui
	def createGui(self):

		self.slot = None
		self.button_css = [None] * len(COLORS)
		self.fig_placeholder = pn.Column(sizing_mode='stretch_both')

		# widgets
		self.num_points_x  = pn.widgets.IntSlider       (name="#x", start=1, end=8, step=1, value=2, width=90)
		self.num_points_y  = pn.widgets.IntSlider       (name="#y", start=1, end=8, step=1, value=2, width=90)
		self.z_res         = pn.widgets.IntSlider       (name="Res", start=20, end=99, step=1, value=24, sizing_mode="stretch_width")
		self.z_op          = pn.widgets.RadioButtonGroup(name="", options=["avg", "mM", "med", "*"], value="avg",max_width=200)

		self.num_points_x.param.watch       (SafeCallback(lambda evt: self.recomputeAllProbes()), 'value_throttled', onlychanged=True,queued=True)
		self.num_points_y.param.watch       (SafeCallback(lambda evt: self.recomputeAllProbes()), 'value_throttled', onlychanged=True,queued=True)
		self.z_res.param.watch              (SafeCallback(lambda evt: self.recomputeAllProbes()), 'value_throttled', onlychanged=True,queued=True)
		self.z_op.param.watch               (SafeCallback(lambda evt: self.recomputeAllProbes()), "value",           onlychanged=True,queued=True)

		# create buttons
		self.buttons = []
		for slot, color in enumerate(COLORS):
			button=pn.widgets.Button(name=color, sizing_mode="stretch_width")
			button.on_click(SafeCallback(lambda evt, slot=slot: self.onProbeButtonClick(slot)))
			self.buttons.append(button)

		self.fig=self.createFigure()

		# to add probes
		self.slice.canvas.on_event(bokeh.events.DoubleTap,SafeCallback(self.onCanvasDoubleTap))

		# watch for color mapper changes
		def onColorMapperTypeChange(evt=None):
			is_log=self.slice.color_mapper_type.value=="log"
			fig_log=isinstance(self.fig.y_scale, bokeh.models.scales.LogScale)
			if is_log==fig_log: return
			if False:
				# changing y_scale DOES NOT WORK (!!!)
				self.fig.y_scale=bokeh.models.scales.LogScale() if is_log else bokeh.models.scales.LinearScale()
			else:
				self.fig=self.createFigure()
				self.recomputeAllProbes()
		self.slice.color_mapper_type.param.watch(SafeCallback(onColorMapperTypeChange),"value", onlychanged=True,queued=True)

		def onSliceOffsetChange(evt=None):
			self.drawSliceOffset()
		self.slice.offset.param.watch(    SafeCallback(onSliceOffsetChange),"value", onlychanged=True,queued=True) # display the new offset

		self.slice.scene.param.watch(     SafeCallback(lambda evt: self.recomputeAllProbes()),"value", onlychanged=True,queued=True)
		self.slice.direction.param.watch(SafeCallback(lambda evt:  self.recomputeAllProbes()),"value", onlychanged=True,queued=True)

		# new data, important for the range
		def onRenderIdChange(evt=None):
			self.refreshFigureRange()
		self.slice.render_id.param.watch(SafeCallback(onRenderIdChange), "value", onlychanged=True,queued=True) 

		top_row=pn.Row(
				self.z_op,
				self.z_res,
				self.num_points_x,
				self.num_points_y,
				sizing_mode="stretch_width"
			)

		button_row=pn.Row(
				*[button for button in self.buttons], 
				sizing_mode="stretch_width"
			)

		self.main_layout = pn.Column(
					top_row,
					button_row,
					self.fig_placeholder,
					sizing_mode="stretch_both"
				)

	# getMainLayout
	def getMainLayout(self):
		return self.main_layout

	# removeRenderer
	def removeRenderer(self, target, value):
		if value in target.renderers:
			target.renderers.remove(value)

	# onCanvasDoubleTap
	def onCanvasDoubleTap(self, evt):
		x,y=evt.x,evt.y
		logger.info(f"[{self.slice.id}] x={x} y={y}")
		dir = self.slice.direction.value
		slot = self.slot
		if slot is None: slot = 0
		probe = self.probes[dir][slot]
		probe.pos = [x, y]
		self.addProbe(probe)

	# onProbeButtonClick
	def onProbeButtonClick(self, slot):
		dir = self.slice.direction.value
		probe = self.probes[dir][slot]
		logger.info(f"[{self.slice.id}] slot={slot} self.slot={self.slot} probe.pos={probe.pos} probe.enabled={probe.enabled}")

		# when I click on the same slot, I am disabling the probe
		if self.slot == slot:
			self.removeProbe(probe)
			self.slot = None
		else:
			# when I click on a new slot..
			self.slot = slot

			# automatically enable a disabled probe
			if not probe.enabled and probe.pos is not None:
				self.addProbe(probe)

		self.updateButtons()

	# findProbe
	def findProbe(self, probe):
		for dir in range(3):
			for slot in range(len(COLORS)):
				if self.probes[dir][slot] == probe:
					return dir, slot
		return None

	# addProbe
	def addProbe(self, probe):

		dir, slot = self.findProbe(probe)
		logger.info(f"[{self.slice.id}] dir={dir} slot={slot} probe.pos={probe.pos}")
		self.removeProbe(probe)
		probe.enabled = True

		pbox = self.slice.getPhysicBox()
		pdim=self.slice.getPointDim()
		(X, Y, Z), titles = self.slice.getLogicAxis()

		X1,X2=(pbox[X][0],pbox[X][1])
		Y1,Y2=(pbox[Y][0],pbox[Y][1])
		Z1,Z2=(pbox[Z][0],pbox[Z][1]) if pdim==3 else (0,1)

		print("----------------- Logic_to_physic:----------------", self.slice.logic_to_physic)
		vt = [self.slice.logic_to_physic[I][0] for I in range(3)]
		vs = [self.slice.logic_to_physic[I][1] for I in range(3)]

		def LogicToPhysic(P):
			ret = [vt[I] + vs[I] * P[I] for I in range(3)]
			last = ret[dir]
			del ret[dir]
			ret.append(last)
			return ret

		def PhysicToLogic(p):
			ret = [it for it in p]
			last = ret[2]
			del ret[2]
			ret.insert(dir, last)
			return [(ret[I] - vt[I]) / vs[I] for I in range(3)]

		# __________________________________________________________
		# here is all in physical coordinates
		assert (probe.pos is not None)

		x,y=probe.pos
		z1,z2=Z1,Z2
	
		p1 = (x, y, Z1)
		p2 = (x, y, Z2)

		# logger.info(f"Add Probe vs={vs} vt={vt} p1={p1} p2={p2}")

		# keep the status for later

		# __________________________________________________________
		# here is all in logical coordinates
		# compute x1,y1,x2,y2 but eigther extrema included (NOTE: it's working at full-res)

		# compute delta
		Delta = [1, 1, 1]
		endh = self.z_res.value
		maxh = self.slice.db.getMaxResolution()
		bitmask = self.slice.db.getBitmask()
		for K in range(maxh, endh, -1):
			Delta[ord(bitmask[K]) - ord('0')] *= 2

		P1 = PhysicToLogic(p1)
		P2 = PhysicToLogic(p2)
		# print(P1,P2)

		def Align(idx, p):
			return int(Delta[idx] * (p[idx] // Delta[idx]))

		P1[X] = Align(X, P1)
		P2[X] = Align(X, P2) + (self.num_points_x.value) * Delta[X]

		P1[Y] = Align(Y, P1)
		P2[Y] = Align(Y, P2) + (self.num_points_y.value) * Delta[Y]

		P1[Z] = Align(Z, P1)
		P2[Z] = Align(Z, P2) + Delta[Z]

		logger.info(f"Add Probe aligned is P1={P1} P2={P2}")

		# invalid query
		if not all([P1[I] < P2[I] for I in range(3)]):
			return

		color = COLORS[slot]

		# for debugging draw points
		if True:
			xs, ys = [[], []]
			for _Z in range(P1[2], P2[2], Delta[2]) if dir != 2 else (P1[2],):
				for _Y in range(P1[1], P2[1], Delta[1]) if dir != 1 else (P1[1],):
					for _X in range(P1[0], P2[0], Delta[0]) if dir != 0 else (P1[0],):
						x, y, z = LogicToPhysic([_X, _Y, _Z])
						xs.append(x)
						ys.append(y)

			x1, x2 = min(xs), max(xs);
			cx = (x1 + x2) / 2.0
			y1, y2 = min(ys), max(ys);
			cy = (y1 + y2) / 2.0

			fig = self.slice.canvas.fig
			self.renderers[probe]["canvas"] = [
				fig.scatter(xs, ys, color=color),
				fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=1, color=color),
				fig.line(self.slice.getPhysicBox()[X], [cy, cy], line_width=1, color=color),
				fig.line([cx, cx], self.slice.getPhysicBox()[Y], line_width=1, color=color),
			]

		# execute the query
		access = self.slice.db.createAccess()
		logger.info(f"ExecuteBoxQuery logic_box={[P1, P2]} endh={endh} num_refinements={1} full_dim={True}")
		multi = ExecuteBoxQuery(self.slice.db, access=access, logic_box=[P1, P2], endh=endh, num_refinements=1,
								full_dim=True)  # full_dim means I am not quering a slice
		data = list(multi)[0]['data']

		# render probe
		if dir == 2:
			xs = list(np.linspace(z1, z2, num=data.shape[0]))
			ys = []
			for Y in range(data.shape[1]):
				for X in range(data.shape[2]):
					ys.append(list(data[:, Y, X]))

		elif dir == 1:
			xs = list(np.linspace(z1, z2, num=data.shape[1]))
			ys = []
			for Z in range(data.shape[0]):
				for X in range(data.shape[2]):
					ys.append(list(data[Z, :, X]))

		else:
			xs = list(np.linspace(z1, z2, num=data.shape[2]))
			ys = []
			for Z in range(data.shape[0]):
				for Y in range(data.shape[1]):
					ys.append(list(data[Z, Y, :]))

		if True:
			op = self.z_op.value

			if op == "avg":
				ys = [[mean(p) for p in zip(*ys)]]

			if op == "mM":
				ys = [
					[min(p) for p in zip(*ys)],
					[max(p) for p in zip(*ys)]
				]

			if op == "med":
				ys = [[median(p) for p in zip(*ys)]]

			if op == "*":
				ys = [it for it in ys]

			for it in ys:
				if self.slice.color_mapper_type.value=="log":
					it = [max(Slice.EPSILON, value) for value in it]
				self.renderers[probe]["fig"].append(
					self.fig.line(xs, it, line_width=2, legend_label=color, line_color=color))

		self.refreshFigureRange()
		self.drawSliceOffset()
		self.updateButtons()

	# removeProbe
	def removeProbe(self, probe):
		fig = self.slice.canvas.fig
		for r in self.renderers[probe]["canvas"]:
			self.removeRenderer(fig, r)
		self.renderers[probe]["canvas"] = []

		for r in self.renderers[probe]["fig"]:
			self.removeRenderer(self.fig, r)
		self.renderers[probe]["fig"] = []

		probe.enabled = False
		self.updateButtons()

	# refreshFigureRange
	def refreshFigureRange(self):

		pbox = self.slice.getPhysicBox()
		pdim=self.slice.getPointDim()
		(X, Y, Z), titles = self.slice.getLogicAxis()
		X1,X2=(pbox[X][0],pbox[X][1])
		Y1,Y2=(pbox[Y][0],pbox[Y][1])
		Z1,Z2=(pbox[Z][0],pbox[Z][1]) if pdim==3 else (0,1)


		self.fig.xaxis.axis_label = titles[2]
		self.fig.x_range.start = Z1
		self.fig.x_range.end   = Z2

		self.fig.y_range.start = self.slice.color_bar.color_mapper.low  if self.slice.color_bar else 0.0
		self.fig.y_range.end   = self.slice.color_bar.color_mapper.high if self.slice.color_bar else 1.0

	# drawSliceOffset
	def drawSliceOffset(self):
			offset = self.slice.offset.value
			self.removeRenderer(self.fig, self.renderers["offset"])
			self.renderers["offset"] = self.fig.line(
				[offset, offset],
				[self.fig.y_range.start, self.fig.y_range.end],
				line_width=1, color="black")

	# updateButtons
	def updateButtons(self):
		dir = self.slice.direction.value
		for slot, button in enumerate(self.buttons):
			color = COLORS[slot]
			probe = self.probes[dir][slot]

			css = [".bk-btn-default {"]

			if slot == self.slot:
				css.append("font-weight: bold;")
				css.append("border: 2px solid black;")

			if slot == self.slot or (probe.pos is not None and probe.enabled):
				css.append("background-color: " + color + " !important;")

			css.append("}")
			css = " ".join(css)

			if self.button_css[slot] != css:
				self.button_css[slot] = css
				button.stylesheets = [css]		

	# removeAllProbes
	def removeAllProbes(self):
		was_enabled = {}
		for dir in range(3):
			for probe in self.probes[dir]:
				was_enabled[probe] = probe.enabled
				self.removeProbe(probe)
		return was_enabled

	# recomputeAllProbes
	def recomputeAllProbes(self):
		
		self.z_res.end = self.slice.db.getMaxResolution()

		self.drawSliceOffset()

		# remove all old probes
		was_enabled = self.removeAllProbes()

		# restore enabled
		for dir in range(3):
			for probe in self.probes[dir]:
				probe.enabled = was_enabled[probe]

		# add the probes only if sibile
		dir = self.slice.direction.value
		for slot, probe in enumerate(self.probes[dir]):
			if probe.pos is not None and probe.enabled:
				self.addProbe(probe)

		self.refreshFigureRange()
		self.updateButtons()