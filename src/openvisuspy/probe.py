import os,sys
import numpy as np
import logging
from statistics import mean, median

from .slice import Slice, Widgets
from .backend import ExecuteBoxQuery

import bokeh
from bokeh.events import DoubleTap
from bokeh.plotting import figure

import panel as pn

logger = logging.getLogger(__name__)

COLORS = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"]

# //s////////////////////////////////////////////////////////////////////////////////////
class Probe:

	def __init__(self):
		self.pos = None
		self.enabled = True

# //////////////////////////////////////////////////////////////////////////////////////
class ProbeTool(Slice):

	# constructor
	def __init__(self, parent=None, show_options=None):
		super().__init__(parent=parent, show_options=show_options)
		self.owner=self

		self.probes = {}
		self.renderers = {
			"offset": None
		}
		for dir in range(3):
			self.probes[dir] = []
			for I in range(len(COLORS)):
				probe = Probe()
				self.probes[dir].append(probe)
				self.renderers[probe] = {
					"canvas": [], # i am drwing on slice.canva s
					"fig": []     # or probe fig
				}

		self.createProbeGui()

		self.owner.on_change('dataset',lambda attr,old,new: self.setProbeDataset(new))
		self.owner.on_change('log_colormapper',lambda attr,old, new: self.setYAxisLog(new))
		self.owner.on_change('direction',lambda attr,old, new: self.setProbesPlane(new))
		self.owner.on_change('offset',lambda attr,old, new: self.refreshGui())
		self.owner.on_change('data',lambda attr,old, new: self.refreshGui())

	# setProbeFigure
	def setProbeFigure(self,value):
		self.probe_fig=value

		# change the offset on the proble plot (NOTE evt.x in is physic domain)
		self.probe_fig.on_event(DoubleTap, lambda evt: self.owner.setOffset(evt.x))

		while len(self.probe_fig_col):
			self.probe_fig_col.pop(0)

		self.probe_fig_col.append(self.probe_fig)

	# createGui
	def createProbeGui(self):

		self.slot = None
		self.button_css = [None] * len(COLORS)

		# create buttons
		self.buttons = []
		for slot, color in enumerate(COLORS):
			self.buttons.append(Widgets.Button(name=color, sizing_mode="stretch_width", callback=lambda slot=slot:self.onProbeButtonClick(slot)))

		vmin, vmax = self.owner.getPaletteRange()

		self.widgets.show_probe = Widgets.Button(name="Probe", callback=self.toggleProbeVisibility)

		self.probe_fig_col = pn.Column(sizing_mode='stretch_both')
		self.setProbeFigure(bokeh.plotting.figure(
			title=None,
			x_axis_label="Z", x_axis_type="linear",
			y_axis_label="f", y_axis_type="log" if self.owner.isLogColorMapper() else "linear",
			x_range=[0.0, 1.0],
			y_range=[0.0, 1.0],
			sizing_mode="stretch_both",
			active_scroll="wheel_zoom",
			toolbar_location=None,
		))


		# probe XY space
		if True:
			# where the center of the probe (can be set by double click or using this)
			self.slider_x_pos = Widgets.Slider(name="X coordinate", type="float", value=0.0, start=0.0, end=1.0, step=1.0, editable=True, sizing_mode="stretch_width", 
																								 callback=lambda new: self.onProbeXYChange(), 
																								 parameter_name="value_throttled")

			self.slider_y_pos = Widgets.Slider(name="Y coordinate", type="float", value=0, start=0, end=1, step=1, editable=True, sizing_mode="stretch_width", 
																								 callback=lambda new: self.onProbeXYChange(), 
																								 parameter_name="value_throttled")

			self.slider_num_points_x = Widgets.Slider(name="#x", type="int", start=1, end=8, step=1, value=2, editable=False, width=60, callback=self.recomputeProbes, parameter_name='value_throttled')
			self.slider_num_points_y = Widgets.Slider(name="#y", type="int", start=1, end=8, step=1, value=2, editable=False, width=60, callback=self.recomputeProbes, parameter_name='value_throttled')

		# probe Z space
			self.slider_z_range = Widgets.RangeSlider(name="Range", type="float", start=0.0, end=1.0, value=(0.0, 1.0), editable=True, sizing_mode="stretch_width", callback=self.recomputeProbes)

		# probe z res
		self.slider_z_res = Widgets.Slider(name="Res", type="int", start=self.start_resolution, end=99, step=1, value=24, editable=False, width=80, callback=self.recomputeProbes, parameter_name='value_throttled')

		# Z op
		self.slider_z_op = Widgets.RadioButtonGroup(name="", options=["avg", "mM", "med", "*"], value="avg", callback=self.recomputeProbes)

		self.probe_layout = pn.Column(
			pn.Row(
				self.slider_x_pos,
				self.slider_y_pos,
				self.slider_z_range,
				self.slider_z_op,
				self.slider_z_res,
				self.slider_num_points_x,
				self.slider_num_points_y,
				sizing_mode="stretch_width"
			),
			pn.Row(*[button for button in self.buttons], sizing_mode="stretch_width"),
			self.probe_fig_col,
			sizing_mode="stretch_both"
		)
		self.probe_layout.visible = False

		self.canvas.on_event(DoubleTap, self.onDoubleTap)


	# removeRenderer
	def removeRenderer(self, target, value):
		if value in target.renderers:
			target.renderers.remove(value)

	# setProbeDataset
	def setProbeDataset(self,value):
		self.slider_z_res.end = self.owner.db.getMaxResolution()

	# setYAxisLog
	def setYAxisLog(self, value):

		# need to recomute to create a brand new figure (because Bokeh cannot change the type of Y axis)
		self.setProbeFigure(bokeh.plotting.figure(
			title=None,
			x_axis_label="Z",
			y_axis_label="f", y_axis_type="log" if value else "linear",
			x_range=[0.0, 1.0],
			y_range=[0.0, 1.0],
			sizing_mode="stretch_both",
			active_scroll="wheel_zoom",
			toolbar_location=None,
		))

		self.recomputeProbes()

	# onProbeXYChange
	def onProbeXYChange(self):
		dir = self.owner.getDirection()
		slot = self.slot
		if slot is None: return
		probe = self.probes[dir][slot]
		probe.pos = (self.slider_x_pos.value, self.slider_y_pos.value)
		self.addProbe(probe)

	# isProbeVisible
	def isProbeVisible(self):
		return self.probe_layout.visible

	# setProbeVisible
	def setProbeVisible(self, value):
		self.probe_layout.visible = value

	# toggleProbeVisibility
	def toggleProbeVisibility(self):
		value = not self.isProbeVisible()
		self.setProbeVisible(value)
		self.recomputeProbes()

	# onDoubleTap
	def onDoubleTap(self, evt):
		x,y=evt.x,evt.y
		logger.info(f"[{self.owner.id}] x={x} y={y}")
		dir = self.owner.getDirection()
		slot = self.slot
		if slot is None: slot = 0
		probe = self.probes[dir][slot]
		probe.pos = [x, y]
		self.addProbe(probe)

	# setProbesPlane
	def setProbesPlane(self, dir):

		pbox = self.getPhysicBox()
		pdim=self.getPointDim()
		logger.info(f"[{self.owner.id}] physic-box={pbox} pdim={pdim}")
	
		(X, Y, Z), titles = self.owner.getLogicAxis()

		X1,X2=(pbox[X][0],pbox[X][1])
		Y1,Y2=(pbox[Y][0],pbox[Y][1])
		Z1,Z2=(pbox[Z][0],pbox[Z][1]) if pdim==3 else (0,1)

		self.slider_x_pos.name = titles[0]
		self.slider_x_pos.start = X1
		self.slider_x_pos.end   = X2
		self.slider_x_pos.step  = (X2 - X1) / 10000
		self.slider_x_pos.value  = X1

		self.slider_y_pos.name = titles[1]
		self.slider_y_pos.start = Y1
		self.slider_y_pos.end   = Y2
		self.slider_y_pos.step  = (Y2 - Y1) / 10000
		self.slider_y_pos.value = Y1

		self.slider_z_range.name = titles[2]
		self.slider_z_range.start = Z1 
		self.slider_z_range.end   = Z2
		self.slider_z_range.step  = (Z2 - Z1) / 10000
		self.slider_z_range.value = (Z1, Z2)

		self.recomputeProbes()
		self.slot = None

	# onProbeButtonClick
	def onProbeButtonClick(self, slot):
		dir = self.owner.getDirection()
		probe = self.probes[dir][slot]
		logger.info(
			f"[{self.owner.id}] slot={slot} self.slot={self.slot} probe.pos={probe.pos} probe.enabled={probe.enabled}")

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

		self.refreshGui()

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
		logger.info(f"[{self.owner.id}] dir={dir} slot={slot} probe.pos={probe.pos}")
		self.removeProbe(probe)
		probe.enabled = True

		vt = [self.owner.logic_to_physic[I][0] for I in range(3)]
		vs = [self.owner.logic_to_physic[I][1] for I in range(3)]

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
		x, y = probe.pos
		z1, z2 = self.slider_z_range.value
		p1 = (x, y, z1)
		p2 = (x, y, z2)

		# logger.info(f"Add Probe vs={vs} vt={vt} p1={p1} p2={p2}")

		# automatically update the XY slider values
		self.slider_x_pos.value = x
		self.slider_y_pos.value = y

		# keep the status for later

		# __________________________________________________________
		# here is all in logical coordinates
		# compute x1,y1,x2,y2 but eigther extrema included (NOTE: it's working at full-res)

		# compute delta
		Delta = [1, 1, 1]
		endh = self.slider_z_res.value
		maxh = self.owner.db.getMaxResolution()
		bitmask = self.owner.db.getBitmask()
		for K in range(maxh, endh, -1):
			Delta[ord(bitmask[K]) - ord('0')] *= 2

		P1 = PhysicToLogic(p1)
		P2 = PhysicToLogic(p2)
		# print(P1,P2)

		# align to the bitmask
		(X, Y, Z), titles = self.owner.getLogicAxis()

		def Align(idx, p):
			return int(Delta[idx] * (p[idx] // Delta[idx]))

		P1[X] = Align(X, P1)
		P2[X] = Align(X, P2) + (self.slider_num_points_x.value) * Delta[X]

		P1[Y] = Align(Y, P1)
		P2[Y] = Align(Y, P2) + (self.slider_num_points_y.value) * Delta[Y]

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

			fig = self.owner.canvas.getFigure()
			self.renderers[probe]["canvas"] = [
				fig.scatter(xs, ys, color=color),
				fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=1, color=color),
				fig.line(self.owner.getPhysicBox()[X], [cy, cy], line_width=1, color=color),
				fig.line([cx, cx], self.owner.getPhysicBox()[Y], line_width=1, color=color),
			]

		# execute the query
		access = self.owner.db.createAccess()
		logger.info(f"ExecuteBoxQuery logic_box={[P1, P2]} endh={endh} num_refinements={1} full_dim={True}")
		multi = ExecuteBoxQuery(self.owner.db, access=access, logic_box=[P1, P2], endh=endh, num_refinements=1,
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
			op = self.slider_z_op.value

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
				if self.owner.isLogColorMapper():
					it = [max(self.owner.epsilon, value) for value in it]
				self.renderers[probe]["fig"].append(
					self.probe_fig.line(xs, it, line_width=2, legend_label=color, line_color=color))

		self.refreshGui()

	# removeProbe
	def removeProbe(self, probe):
		fig = self.owner.canvas.getFigure()
		for r in self.renderers[probe]["canvas"]:
			self.removeRenderer(fig, r)
		self.renderers[probe]["canvas"] = []

		for r in self.renderers[probe]["fig"]:
			self.removeRenderer(self.probe_fig, r)
		self.renderers[probe]["fig"] = []

		probe.enabled = False
		self.refreshGui()

	# refreshGui
	def refreshGui(self):

		dir = self.owner.getDirection()

		# buttons
		if True:

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

			# X axis
		if True:
			z1, z2 = self.slider_z_range.value
			self.probe_fig.xaxis.axis_label = self.slider_z_range.name
			self.probe_fig.x_range.start = z1
			self.probe_fig.x_range.end = z2

		# draw figure line for offset
		if True:
			offset = self.owner.getOffset()
			self.removeRenderer(self.probe_fig, self.renderers["offset"])
			self.renderers["offset"] = self.probe_fig.line(
				[offset, offset],
				[self.probe_fig.y_range.start, self.probe_fig.y_range.end],
				line_width=1, color="black")

	# recomputeProbes
	def recomputeProbes(self, evt=None):

		self.refreshGui()

		# remove all old probes
		was_enabled = {}
		for dir in range(3):
			for probe in self.probes[dir]:
				was_enabled[probe] = probe.enabled
				self.removeProbe(probe)

		# restore enabled
		for dir in range(3):
			for probe in self.probes[dir]:
				probe.enabled = was_enabled[probe]

		# add the probes only if sibile
		if self.isProbeVisible():
			dir = self.owner.getDirection()
			for slot, probe in enumerate(self.probes[dir]):
				if probe.pos is not None and probe.enabled:
					self.addProbe(probe)


