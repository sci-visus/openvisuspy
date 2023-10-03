import os,sys,logging,time,types,copy
import numpy as np

# bokeh dep
import bokeh
from bokeh.io import show
from bokeh.models import Range1d,Select,CheckboxButtonGroup,Slider, RangeSlider,Button,Row,Column,Div,CheckboxGroup, RadioButtonGroup
from bokeh.layouts import column, row
from bokeh.plotting import figure
from bokeh.events import ButtonClick,DoubleTap
from types import SimpleNamespace
from bokeh.models import InlineStyleSheet

from statistics import mean,median,stdev

from openvisuspy import SetupLogger, GetBackend, Slice, Slices,ExecuteBoxQuery

logger = logging.getLogger(__name__)

# //////////////////////////////////////////////////////////////////////////////////////
class Probe:

	# constructor
	def __init__(self):
		self.pos=None
		self.enabled=True

		# run-time
		self.renderers=[]


# //////////////////////////////////////////////////////////////////////////////////////
class ProbeTool(Slice):

	colors = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"] 

	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None):
		super().__init__(doc=doc, is_panel=is_panel, parent=parent)
		self.show_options.append("show-probe")
		self.render_offset=None

		N=len(self.colors)
		self.probes={0: [Probe() for I in range(N)], 1: [Probe() for I in range(N)], 2: [Probe() for I in range(N)]}
		self.slot=None
		self.button_css=[None]*N

		# create buttons
		self.buttons=[Button(label=color, sizing_mode="stretch_width") for color in self.colors]
		for slot,button in enumerate(self.buttons):
			button.on_event(ButtonClick, lambda evt,slot=slot: self.onButtonClick(slot=slot))

		vmin,vmax=self.getPaletteRange()

		self.widgets.show_probe=Button(label="Probe",width=80,sizing_mode="stretch_height")
		self.widgets.show_probe.on_click(self.toggleVisible)

		self.probe_fig = bokeh.plotting.figure(
			title=None, 
			x_axis_label="Z", 
			y_axis_label="f", 
			toolbar_location=None, 
			x_range = [0.0,1.0], 
			y_range = [0.0,1.0], 
			sizing_mode="stretch_both"
		) 

		# change the offset on the proble plot (NOTE evt.x in is physic domain)
		self.probe_fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

		# probe XY space
		if True:

			# where the center of the probe (can be set by double click or using this)
			self.slider_x_pos=Slider(value=0.0, start=0.0, end=1.0, step=1.0, title="X coordinate", sizing_mode="stretch_width" )
			self.slider_x_pos .on_change('value_throttled', lambda attr,old, new: self.onProbeXYChange())

			self.slider_y_pos=Slider(value=0, start=0, end=1, step=1, title="Y coordinate", sizing_mode="stretch_width" )
			self.slider_y_pos .on_change('value_throttled', lambda attr,old, new: self.onProbeXYChange())

			self.slider_num_points=Slider(value=2 , start=1, end=8, step=1, title="#points",width=60)
			self.slider_num_points.on_change('value_throttled', lambda attr,old, new: self.refreshAll())	

		# probe Z space
		if True:

			# Z range
			self.slider_z_range = RangeSlider(start=0.0, end=1.0, value=(0.0,1.0), title="Range", sizing_mode="stretch_width")
			self.slider_z_range.on_change('value_throttled', lambda attr,old, new: self.refreshAll())

			# Z resolution 
			self.slider_z_res = Slider(value=24, start=1, end=31, step=1, title="Res", width=80)
			self.slider_z_res.on_change('value_throttled', lambda attr,old, new: self.refreshAll())

			# Z op
			self.slider_z_op = RadioButtonGroup(labels=["avg","mM","med","*"], active=0)
			self.slider_z_op.on_change("active",lambda attr,old, new: self.refreshAll()) 	

	
	# updateButtons
	def updateButtons(self):

		logger.info(f"[{self.id}] updateButtons self.slot={self.slot}")
		
		dir=self.getDirection()

		for slot, button in enumerate(self.buttons):
			color=self.colors[slot]
			probe=self.probes[dir][slot]

			css=[".bk-btn-default {"]

			if slot==self.slot:
				css.append("font-weight: bold;")
				css.append("border: 2px solid black;")

			if slot==self.slot or (probe.pos is not None and probe.enabled):
				css.append("background-color: " + color + " !important;")

			css.append("}")
			css=" ".join(css)
			
			if self.button_css[slot]!=css:
				self.button_css[slot]=css
				button.stylesheets=[InlineStyleSheet(css=css)] 


	# onProbeXYChange
	def onProbeXYChange(self):
		dir=self.getDirection()
		slot=self.slot
		probe=self.probes[dir][slot]
		probe.pos=(self.slider_x_pos.value,self.slider_y_pos.value)
		self.enableProbe(probe)

	# removeRenderers
	def removeRenderers(self,probe):
		for fig,r in probe.renderers:
			if r in fig.renderers:
				fig.renderers.remove(r)
		probe.renderers=[]	

	# removeAllRenderers
	def removeAllRenderers(self):
		for dir in range(3):
			for probe in self.probes[dir]:
				self.removeRenderers(probe)

	# disableProbe
	def disableProbe(self, probe):
		self.removeRenderers(probe)
		probe.enabled=False
		self.updateButtons()
	
	# refreshAll
	def refreshAll(self):
		dir=self.getDirection() # only in current direction
		self.removeAllRenderers()
		if self.isVisible():
			for slot,probe in enumerate(self.probes[dir]):
				if probe.pos is not None and probe.enabled:
					self.enableProbe(probe)

	# isVisible
	def isVisible(self):
		return self.probe_layout.visible

	# setVisible
	def setVisible(self,value):
		self.probe_layout.visible=value

	# toggleVisible
	def toggleVisible(self):
		value=not self.isVisible()
		self.setVisible(value)
		self.refreshAll()
			
	# onDoubleTap
	def onDoubleTap(self,x,y):
		logger.info(f"onDoubleTap x={x} y={y}")
		dir=self.getDirection()
		slot=self.slot
		if slot is None: slot=0
		probe=self.probes[dir][slot]
		probe.pos=[x,y]
		self.enableProbe(probe)

	# setDataset
	def setDataset(self, url,db=None, force=False):
		super().setDataset(url, db=db, force=force)
		if self.db: 
			self.slider_z_res.end=self.db.getMaxResolution()

	# getMainLayout
	def getMainLayout(self):
		slice_layout=super().getMainLayout()
		self.probe_layout=Column(
				Row(
					self.slider_x_pos, 
					self.slider_y_pos, 
					self.slider_z_range,
					self.slider_z_op, 
					self.slider_z_res, 
					self.slider_num_points,
					sizing_mode="stretch_width"),
				Row(*[button for button in self.buttons], sizing_mode="stretch_width"),
				self.probe_fig,
				sizing_mode="stretch_both"
			)
		self.probe_layout.visible=False
		return Row(
				slice_layout, 
				self.probe_layout,
				sizing_mode="stretch_both")

	# setDirection
	def setDirection(self, dir):
		super().setDirection(dir)

		pbox=self.getPhysicBox()
		logger.info(f"[{self.id}] physic-box={pbox}")

		(X,Y,Z),titles=self.getLogicAxis()

		self.slider_x_pos.title   = titles[0]
		self.slider_x_pos.start   = pbox[X][0]
		self.slider_x_pos.end     = pbox[X][1]
		self.slider_x_pos.step    = (pbox[X][1]-pbox[X][0])/10000
		self.slider_x_pos.value   = pbox[X][0]

		self.slider_y_pos.title   = titles[1]
		self.slider_y_pos.start   = pbox[Y][0]
		self.slider_y_pos.end     = pbox[Y][1]
		self.slider_y_pos.step    = (pbox[Y][1]-pbox[Y][0])/10000
		self.slider_y_pos.value   = pbox[Y][0]

		self.slider_z_range.title = titles[2]
		self.slider_z_range.start = pbox[Z][0]
		self.slider_z_range.end   = pbox[Z][1]
		self.slider_z_range.step  = (pbox[Z][1]-pbox[Z][0])/10000
		self.slider_z_range.value = [pbox[Z][0], pbox[Z][1]]

		self.probe_fig.xaxis.axis_label = self.slider_z_range.title
		self.guessOffset()

		self.refreshAll()
		self.slot=None

	# setOffset
	def setOffset(self, value):
		super().setOffset(value)
		self.drawOffsetLine()

	# drawOffsetLine 
	def drawOffsetLine(self):
		offset=self.getOffset()
		if self.render_offset in self.probe_fig.renderers:
			self.probe_fig.renderers.remove(self.render_offset)
		self.render_offset=self.probe_fig.line(
			[offset,offset],
			[self.probe_fig.y_range.start, self.probe_fig.y_range.end],
			line_width=1,color="black")

	# onButtonClick
	def onButtonClick(self, slot):
		dir=self.getDirection()
		probe=self.probes[dir][slot]
		logger.info(f"[{self.id}] onButtonClick slot={slot} self.slot={self.slot} probe.pos={probe.pos} probe.enabled={probe.enabled}")
		
		# when I click on the same slot, I am disabling the probe
		if self.slot==slot:
			self.disableProbe(probe)
			self.slot=None
		else:
			# when I click on a new slot..
			self.slot=slot

			# automatically enable a disabled probe
			if not probe.enabled and probe.pos is not None:
				self.enableProbe(probe)

		self.updateButtons()

	# findProbe
	def findProbe(self,probe):
		for dir in range(3):
			for slot in range(len(self.colors)):
				if self.probes[dir][slot]==probe:
					return dir,slot
		return None

	# addProbeRenderers
	def addProbeRenderers(self, probe):
		
		dir,slot=self.findProbe(probe)

		vt=[self.logic_to_physic[I][0] for I in range(3)]
		vs=[self.logic_to_physic[I][1] for I in range(3)]

		def LogicToPhysic(P):
			ret=[vt[I] + vs[I]*P[I] for I in range(3)] 
			last=ret[dir]
			del ret[dir]
			ret.append(last)
			return ret

		def PhysicToLogic(p):
			ret=[it for it in p]
			last=ret[2]
			del ret[2]
			ret.insert(dir,last)
			return [(ret[I]-vt[I])/vs[I] for I in range(3)]

		# __________________________________________________________
		# here is all in physical coordinates
		assert(probe.pos is not None)
		x,y=probe.pos
		z1,z2=self.slider_z_range.value
		p1=(x,y,z1)
		p2=(x,y,z2)

		logger.info(f"Add Probe vs={vs} vt={vt} p1={p1} p2={p2}")

		# automatically update the fig X axis range
		self.probe_fig.x_range.start = z1
		self.probe_fig.x_range.end   = z2

		# automatically update the XY slider values
		self.slider_x_pos.value  = x
		self.slider_y_pos.value  = y

		# keep the status for later
		
		# __________________________________________________________
		# here is all in logical coordinates
		# compute x1,y1,x2,y2 but eigther extrema included (NOTE: it's working at full-res)

		# compute delta
		Delta=[1,1,1]
		endh=self.slider_z_res.value
		maxh=self.db.getMaxResolution()
		bitmask=self.db.getBitmask()
		for K in range(maxh,endh,-1):
			Delta[ord(bitmask[K])-ord('0')]*=2

		P1=PhysicToLogic(p1)
		P2=PhysicToLogic(p2)
		# print(P1,P2)

		# align to the bitmask
		num_points=self.slider_num_points.value
		for I in range(3):
			P1[I]=int(Delta[I]*(P1[I]//Delta[I]))
			P2[I]=int(Delta[I]*(P2[I]//Delta[I])) # P2 is excluded
			if I!=dir:
				P2[I]+=(num_points-1)*Delta[I]
			P2[I]+=Delta[I]

		logger.info(f"Add Probe P1={P1} P2={P2}")
		
		# invalid query
		if not all([P1[I]<P2[I] for I in range(3)]):
			return
		
		color=self.colors[slot]

		# for debugging draw points
		if True:
			xs,ys=[[],[]]
			for Z in range(P1[2],P2[2],Delta[2]) if dir!=2 else (P1[2],):
				for Y in range(P1[1],P2[1],Delta[1]) if dir!=1 else (P1[1],):
					for X in range(P1[0],P2[0],Delta[0]) if dir!=0 else (P1[0],):
						x,y,z=LogicToPhysic([X,Y,Z])
						xs.append(x)
						ys.append(y)

			r=self.canvas.fig.scatter(xs, ys, color= color)
			probe.renderers.append([self.canvas.fig,r])

			x1,x2=min(xs),max(xs)
			y1,y2=min(ys),max(ys)
			r=self.canvas.fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=1, color= color)
			probe.renderers.append([self.canvas.fig, r])

		# execute the query
		access=self.db.createAccess()
		logger.info(f"ExecuteBoxQuery logic_box={[P1,P2]} endh={endh} num_refinements={1} full_dim={True}")
		multi=ExecuteBoxQuery(self.db, access=access, logic_box=[P1,P2],  endh=endh, num_refinements=1, full_dim=True) # full_dim means I am not quering a slice
		data=list(multi)[0]['data']

		# render probe
		if dir==2:
			xs=list(np.linspace(z1,z2, num=data.shape[0]))
			ys=[]
			for Y in range(data.shape[1]):
				for X in range(data.shape[2]):
					ys.append(list(data[:,Y,X]))

		elif dir==1:
			xs=list(np.linspace(z1,z2, num=data.shape[1]))
			ys=[]
			for Z in range(data.shape[0]):
				for X in range(data.shape[2]):
					ys.append(list(data[Z,:,X]))

		else:
			xs=list(np.linspace(z1,z2, num=data.shape[2]))
			ys=[]
			for Z in range(data.shape[0]):
				for Y in range(data.shape[1]):
					ys.append(list(data[Z,Y,:]))

		for it in [self.slider_z_op.active]:
			op=self.slider_z_op.labels[it]
		
			if op=="avg":
				probe.renderers.append([self.probe_fig,self.probe_fig.line(xs, [mean(p) for p in zip(*ys)], line_width=2, legend_label=color, line_color=color)])

			if op=="mM":
				probe.renderers.append([self.probe_fig,self.probe_fig.line(xs, [min(p) for p in zip(*ys)], line_width=2, legend_label=color, line_color=color)])
				probe.renderers.append([self.probe_fig,self.probe_fig.line(xs, [max(p) for p in zip(*ys)], line_width=2, legend_label=color, line_color=color)])

			if op=="med":
				probe.renderers.append([self.probe_fig,self.probe_fig.line(xs, [median(p) for p in zip(*ys)], line_width=2, legend_label=color, line_color=color)])	

			if op=="*":
				for it in ys:
					probe.renderers.append([self.probe_fig,self.probe_fig.line(xs, it, line_width=2, legend_label=color, line_color=color)])

		self.refreshFigureYScale()	

	# enableProbe
	def enableProbe(self, probe):
		dir,slot=self.findProbe(probe)
		logger.info(f"enableProbe dir={dir} slot={slot} probe.pos={probe.pos}")
		self.removeRenderers(probe)
		probe.enabled = True
		self.addProbeRenderers(probe)
		self.updateButtons()

	# refreshFigureYScale
	def refreshFigureYScale(self):
		is_log=isinstance(self.color_bar.color_mapper, bokeh.models.LogColorMapper)
		vmin,vmax=[self.color_bar.color_mapper.low,self.color_bar.color_mapper.high	]
		#self.probe_fig.y_range.start=vmin
		#self.probe_fig.y_range.end  =vmax
		self.probe_fig.y_range.start=0.0001
		self.probe_fig.y_range.end=131591
		self.probe_fig.yaxis=bokeh.models.LinearAxis(axis_label="aaa", ticker = bokeh.models.BasicTicker())

		print("*******************",self.probe_fig.yaxis)

		self.y_scale = bokeh.models.LogScale() # if is_log else bokeh.models.LinearScale()
		self.drawOffsetLine()
		logger.info(f"!!!!!!!!! refreshFigureYScale is_log={is_log} range={[vmin,vmax]}")

	# gotNewData
	def gotNewData(self, result):
		super().gotNewData(result)
		self.refreshFigureYScale()

