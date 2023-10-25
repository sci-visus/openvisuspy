import logging
from statistics import mean, median

# bokeh dep
import bokeh
import numpy as np
from bokeh.events import ButtonClick, DoubleTap
from bokeh.models import InlineStyleSheet
from bokeh.models import Slider, RangeSlider, Button, Row, Column, RadioButtonGroup
from bokeh.plotting import figure
from openvisuspy import Slice, ExecuteBoxQuery

logger = logging.getLogger(__name__)


# //////////////////////////////////////////////////////////////////////////////////////
class Probe:

	# constructor
	def __init__(self):
		self.pos = None
		self.enabled = True


# //////////////////////////////////////////////////////////////////////////////////////
class ProbeTool(Slice):
	colors = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"]

	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None):
		super().__init__(doc=doc, is_panel=is_panel, parent=parent)
		self.show_options.append("show-probe")

		N = len(self.colors)

		self.probes = {}
		self.renderers = {
			"offset": None
		}
		for dir in range(3):
			self.probes[dir] = []
			for I in range(N):
				probe = Probe()
				self.probes[dir].append(probe)
				self.renderers[probe] = {
					"canvas": [],
					"fig": []
				}

		self.slot = None
		self.button_css = [None] * N

		# create buttons
		self.buttons = [Button(label=color, sizing_mode="stretch_width") for color in self.colors]
		for slot, button in enumerate(self.buttons):
			button.on_event(ButtonClick, lambda evt, slot=slot: self.onButtonClick(slot=slot))

		vmin, vmax = self.getPaletteRange()

		self.widgets.show_probe = Button(label="Probe", width=80, sizing_mode="stretch_height")
		self.widgets.show_probe.on_click(self.toggleProbeVisibility)

		self.probe_fig = bokeh.plotting.figure(
			title=None,
			x_axis_label="Z", x_axis_type="linear",
			y_axis_label="f", y_axis_type=self.getColorMapperType(),
			x_range=[0.0, 1.0],
			y_range=[0.0, 1.0],
			sizing_mode="stretch_both",
			active_scroll="wheel_zoom",
			toolbar_location=None,
		)

		# change the offset on the proble plot (NOTE evt.x in is physic domain)
		self.probe_fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

		self.probe_fig_col = Column(self.probe_fig, sizing_mode='stretch_both')

		# probe XY space
		if True:
			# where the center of the probe (can be set by double click or using this)
			self.slider_x_pos = Slider(value=0.0, start=0.0, end=1.0, step=1.0, title="X coordinate",
									   sizing_mode="stretch_width")
			self.slider_x_pos.on_change('value_throttled', lambda attr, old, new: self.onProbeXYChange())

			self.slider_y_pos = Slider(value=0, start=0, end=1, step=1, title="Y coordinate",
									   sizing_mode="stretch_width")
			self.slider_y_pos.on_change('value_throttled', lambda attr, old, new: self.onProbeXYChange())

			self.slider_num_points_x = Slider(value=2, start=1, end=8, step=1, title="#x", width=60)
			self.slider_num_points_x.on_change('value_throttled', lambda attr, old, new: self.recompute())

			self.slider_num_points_y = Slider(value=2, start=1, end=8, step=1, title="#y", width=60)
			self.slider_num_points_y.on_change('value_throttled', lambda attr, old, new: self.recompute())

		# probe Z space
		if True:
			# Z range
			self.slider_z_range = RangeSlider(start=0.0, end=1.0, value=(0.0, 1.0), title="Range",
											  sizing_mode="stretch_width")
			self.slider_z_range.on_change('value_throttled', lambda attr, old, new: self.recompute())

			# Z resolution
			self.slider_z_res = Slider(value=24, start=self.start_resolution, end=99, step=1, title="Res", width=80)
			self.slider_z_res.on_change('value_throttled', lambda attr, old, new: self.recompute())

			# Z op
			self.slider_z_op = RadioButtonGroup(labels=["avg", "mM", "med", "*"], active=0)
			self.slider_z_op.on_change("active", lambda attr, old, new: self.recompute())

		self.probe_layout = Column(
			Row(
				self.slider_x_pos,
				self.slider_y_pos,
				self.slider_z_range,
				self.slider_z_op,
				self.slider_z_res,
				self.slider_num_points_x,
				self.slider_num_points_y,
				sizing_mode="stretch_width"
			),
			Row(*[button for button in self.buttons], sizing_mode="stretch_width"),
			self.probe_fig_col,
			sizing_mode="stretch_both"
		)
		self.probe_layout.visible = False

	# removeRenderer
	def removeRenderer(self, target, value):
		if value in target.renderers:
			target.renderers.remove(value)

	# setColorMapperType
	def setColorMapperType(self, value):
		super().setColorMapperType(value)

		# need to recomute to create a brand new figure (because Bokeh cannot change the type of Y axis)
		old_probe_fig = self.probe_fig
		self.probe_fig = bokeh.plotting.figure(
			title=None,
			x_axis_label="Z",
			y_axis_label="f", y_axis_type=value,
			x_range=[0.0, 1.0],
			y_range=[0.0, 1.0],
			sizing_mode="stretch_both",
			active_scroll="wheel_zoom",
			toolbar_location=None,
		)
		self.probe_fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))
		self.probe_fig_col.children = [self.probe_fig]
		self.recompute()

	# onProbeXYChange
	def onProbeXYChange(self):
		dir = self.getDirection()
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
		self.recompute()

	# onDoubleTap
	def onDoubleTap(self, x, y):
		logger.info(f"[{self.id}] x={x} y={y}")
		dir = self.getDirection()
		slot = self.slot
		if slot is None: slot = 0
		probe = self.probes[dir][slot]
		probe.pos = [x, y]
		self.addProbe(probe)

	# setDataset
	def setDataset(self, name, db=None, force=False):
		super().setDataset(name, db=db, force=force)
		if self.db:
			self.slider_z_res.end = self.db.getMaxResolution()

	# getMainLayout
	def getMainLayout(self):
		return Row(
			super().getMainLayout(),
			self.probe_layout,
			sizing_mode="stretch_both")

	# setDirection
	def setDirection(self, dir):
		super().setDirection(dir)

		pbox = self.getPhysicBox()
		logger.info(f"[{self.id}] physic-box={pbox}")

		(X, Y, Z), titles = self.getLogicAxis()

		self.slider_x_pos.title = titles[0]
		self.slider_x_pos.start = pbox[X][0]
		self.slider_x_pos.end = pbox[X][1]
		self.slider_x_pos.step = (pbox[X][1] - pbox[X][0]) / 10000
		self.slider_x_pos.value = pbox[X][0]

		self.slider_y_pos.title = titles[1]
		self.slider_y_pos.start = pbox[Y][0]
		self.slider_y_pos.end = pbox[Y][1]
		self.slider_y_pos.step = (pbox[Y][1] - pbox[Y][0]) / 10000
		self.slider_y_pos.value = pbox[Y][0]

		self.slider_z_range.title = titles[2]
		self.slider_z_range.start = pbox[Z][0]
		self.slider_z_range.end = pbox[Z][1]
		self.slider_z_range.step = (pbox[Z][1] - pbox[Z][0]) / 10000
		self.slider_z_range.value = [pbox[Z][0], pbox[Z][1]]

		self.guessOffset()
		self.recompute()
		self.slot = None

	# setOffset
	def setOffset(self, value):

		# do not send float offset if it's all integer
		if all([int(it) == it for it in self.getOffsetStartEnd()]):
			value = int(value)

		super().setOffset(value)
		self.refreshProbe()

	# onButtonClick
	def onButtonClick(self, slot):
		dir = self.getDirection()
		probe = self.probes[dir][slot]
		logger.info(
			f"[{self.id}] slot={slot} self.slot={self.slot} probe.pos={probe.pos} probe.enabled={probe.enabled}")

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

		self.refreshProbe()

	# findProbe
	def findProbe(self, probe):
		for dir in range(3):
			for slot in range(len(self.colors)):
				if self.probes[dir][slot] == probe:
					return dir, slot
		return None

	# addProbe
	def addProbe(self, probe):
		dir, slot = self.findProbe(probe)
		logger.info(f"[{self.id}] dir={dir} slot={slot} probe.pos={probe.pos}")
		self.removeProbe(probe)
		probe.enabled = True

		vt = [self.logic_to_physic[I][0] for I in range(3)]
		vs = [self.logic_to_physic[I][1] for I in range(3)]

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
		maxh = self.db.getMaxResolution()
		bitmask = self.db.getBitmask()
		for K in range(maxh, endh, -1):
			Delta[ord(bitmask[K]) - ord('0')] *= 2

		P1 = PhysicToLogic(p1)
		P2 = PhysicToLogic(p2)
		# print(P1,P2)

		# align to the bitmask
		(X, Y, Z), titles = self.getLogicAxis()

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

		color = self.colors[slot]

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

			fig = self.canvas.getFigure()
			self.renderers[probe]["canvas"] = [
				fig.scatter(xs, ys, color=color),
				fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=1, color=color),
				fig.line(self.getPhysicBox()[X], [cy, cy], line_width=1, color=color),
				fig.line([cx, cx], self.getPhysicBox()[Y], line_width=1, color=color),
			]

		# execute the query
		access = self.db.createAccess()
		logger.info(f"ExecuteBoxQuery logic_box={[P1, P2]} endh={endh} num_refinements={1} full_dim={True}")
		multi = ExecuteBoxQuery(self.db, access=access, logic_box=[P1, P2], endh=endh, num_refinements=1,
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

		for it in [self.slider_z_op.active]:
			op = self.slider_z_op.labels[it]

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
				if self.getColorMapperType() == "log":
					it = [max(self.epsilon, value) for value in it]
				self.renderers[probe]["fig"].append(
					self.probe_fig.line(xs, it, line_width=2, legend_label=color, line_color=color))

		self.refreshProbe()

	# removeProbe
	def removeProbe(self, probe):
		fig = self.canvas.getFigure()
		for r in self.renderers[probe]["canvas"]:
			self.removeRenderer(fig, r)
		self.renderers[probe]["canvas"] = []

		for r in self.renderers[probe]["fig"]:
			self.removeRenderer(self.probe_fig, r)
		self.renderers[probe]["fig"] = []

		probe.enabled = False
		self.refreshProbe()

	# refreshProbe
	def refreshProbe(self):

		dir = self.getDirection()

		# buttons
		if True:

			for slot, button in enumerate(self.buttons):
				color = self.colors[slot]
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
					button.stylesheets = [InlineStyleSheet(css=css)]

			# X axis
		if True:
			z1, z2 = self.slider_z_range.value
			self.probe_fig.xaxis.axis_label = self.slider_z_range.title
			self.probe_fig.x_range.start = z1
			self.probe_fig.x_range.end = z2

		# Y axis
		if True:
			self.probe_fig.y_range.start = self.color_bar.color_mapper.low
			self.probe_fig.y_range.end = self.color_bar.color_mapper.high

		# draw figure line for offset
		if True:
			offset = self.getOffset()
			self.removeRenderer(self.probe_fig, self.renderers["offset"])
			self.renderers["offset"] = self.probe_fig.line(
				[offset, offset],
				[self.probe_fig.y_range.start, self.probe_fig.y_range.end],
				line_width=1, color="black")

	# recompute
	def recompute(self):

		self.refreshProbe()

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
			dir = self.getDirection()
			for slot, probe in enumerate(self.probes[dir]):
				if probe.pos is not None and probe.enabled:
					self.addProbe(probe)

	# gotNewData
	def gotNewData(self, result):
		super().gotNewData(result)
		self.refreshProbe()
