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

from statistics import mean,median,stdev

from openvisuspy import SetupLogger, GetBackend, Slice, Slices,ExecuteBoxQuery

COLORS = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"] 
INACTIVE,ACTIVE,CURRENT=0,1,2	

logger = logging.getLogger(__name__)

# //////////////////////////////////////////////////////////////////////////////////////
class Probe:

	# constructor
	def __init__(self, status=INACTIVE, button=None,color=None):
		self.status=status
		self.button=button
		self.color=color
		self.pos=None
		self.renderers=SimpleNamespace()
		self.y_range=[0.0,0.0]
		self.renderers.target=[]
		self.renderers.plot  =[]

	# setCurrent
	def setCurrent(self,is_current):

		if is_current:
			self.status=CURRENT
		else:
			if self.status==INACTIVE or self.pos is None:
				self.status=INACTIVE
			else:
				self.status=ACTIVE

		self.button.css_classes=[f"custom_button_{self.status}_{self.color}"]


# //////////////////////////////////////////////////////////////////////////////////////
class ProbeTool(Slice):

	# constructor
	def __init__(self, show_options):
		super().__init__(show_options)
		self.renderers=SimpleNamespace()
		self.renderers.offset=None
		self.probes={0: [], 1: [], 2: []}

		# create buttons
		self.buttons=[]
		self.css_styles = ""
		for I,color in enumerate(COLORS):
			button = Button(label=color, sizing_mode="stretch_width")
			button.css_classes=[f"custom_button_0_{color}"]
			button.on_event(ButtonClick, lambda evt,I=I:  self.onProbeButtonClick(I))
			self.buttons.append(button)
			self.css_styles +=  """
				.custom_button_0_{color} button.bk.bk-btn.bk-btn-default  {}
				.custom_button_1_{color} button.bk.bk-btn.bk-btn-default  {background-color: {color}; }
				.custom_button_2_{color} button.bk.bk-btn.bk-btn-default  {background-color: {color}; box-shadow: 2px 2px; }
			""".replace("{color}",color)

			for dir in range(3):
				self.probes[dir].append(Probe(status=INACTIVE,button=button,color=color))

		vmin,vmax=self.getPaletteRange()

		self.probe_fig = figure(
			title="Line Plot", 
			x_axis_label="Z", 
			y_axis_label="f", 
			toolbar_location=None, 
			x_range = [0.0,1.0], 
			y_range = [0.0,1.0], 
			sizing_mode="stretch_both"
		) 

		# change the offset on the proble plot
		self.probe_fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

		# probe XY space
		if True:

			# where the center of the probe (can be set by double click or using this)
			self.slider_x_pos=Slider(value=0, start=0, end=1, step=1, title="X coordinate", sizing_mode="stretch_width" )
			self.slider_x_pos .on_change('value_throttled', lambda attr,old, x: self.addProbe())

			self.slider_y_pos=Slider(value=0, start=0, end=1, step=1, title="Y coordinate", sizing_mode="stretch_width" )
			self.slider_y_pos .on_change('value_throttled', lambda attr,old, y: self.addProbe())

			self.slider_num_points=Slider(value=2 , start=1, end=8, step=1, title="# points",width=80)
			self.slider_num_points.on_change('value_throttled', lambda attr,old, x: self.refreshAllProbes())	

		# probe Z space
		if True:

			# Z range
			self.slider_z_range = RangeSlider(start=0.0, end=1.0, value=(0.0,1.0), title="Range", sizing_mode="stretch_width")
			self.slider_z_range.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

			# Z resolution 
			self.slider_z_res = Slider(value=21, start=1, end=31, step=1, title="Res", sizing_mode="stretch_width")
			self.slider_z_res.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

			# Z op
			self.slider_z_op = RadioButtonGroup(labels=["avg","mM","med","*"], active=0)
			self.slider_z_op.on_change("active",lambda attr,old, z: self.refreshAllProbes()) 	

	# onDoubleTap
	def onDoubleTap(self,x,y):
		logger.info(f"onDoubleTap x={x} y={y}")
		self.addProbe(pos=(x,y))

	# setDataset
	def setDataset(self, url,db=None, force=False):
		super().setDataset(url, db=db, force=force)

		# rehentrant call
		if self.db: 
			self.slider_z_res.end=self.db.getMaxResolution()

	# getBokehLayout
	def getBokehLayout(self, doc=None):

		slice_layout=super().getBokehLayout(doc=doc)

		return Row(
				slice_layout, 
				Column(
					# Div(text="<style>\n" + self.css_styles + "</style>"),
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
				),
				sizing_mode="stretch_both")


	# clearProbes
	def clearProbes(self):
		for dir in range(3):
			for probe in self.probes[dir]:
				self.removeProbe(probe)

	# setDirection
	def setDirection(self, dir):

		super().setDirection(dir)

		self.clearProbes()
		pbox=self.getPhysicBox()
		logger.info(f"physic-box={pbox}")

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

		self.setOffset(pbox[Z][0])
		self.setCurrentButton(0)
		self.refreshAllProbes()

	# setOffset
	def setOffset(self, value):
		super().setOffset(value)
		self.removeRenderer(self.probe_fig, self.renderers.offset)
		self.renderers.offset=None
		self.renderers.offset=self.probe_fig.line([value,value],[self.slider_z_range.start,self.slider_z_range.end],line_width=2,color="lightgray")

	# onProbeButtonClick
	def onProbeButtonClick(self,  I):
		
		dir=self.getDirection()
		status=self.probes[dir][I].status
		
		# current -> inactive
		if  status== CURRENT:
			self.probes[dir][I].status = INACTIVE  
			self.removeProbe(self.probes[dir][I])
			self.setCurrentButton(None)

		# active->current
		elif status==ACTIVE:
			self.setCurrentButton(I)

		# inactive ->  current
		elif status==INACTIVE:
			self.setCurrentButton(I)
			probe=self.probes[dir][I]
			if probe.pos is not None:
				self.addProbe(I=I, pos=probe.pos)
		else:
			raise Exception("internal Error")

	# removeRenderer
	def removeRenderer(self, fig, value):
		if hasattr(value, '__iter__'):
			for it in value:
				self.removeRenderer(fig,it)
		else:
			if value in fig.renderers:
				fig.renderers.remove(value)

	# getCurrentButton
	def getCurrentButton(self):
		dir=self.getDirection()
		for I,probe in enumerate(self.probes[dir]):
			if probe.status==CURRENT:
				return I
		return None
	
	# setCurrentButton
	def setCurrentButton(self, value):
		dir=self.getDirection()
		for I,probe in enumerate(self.probes[dir]):
			probe.setCurrent(True if I==value else False) 

	# addProbe
	def addProbe(self, I=None, pos=None):

		dir=self.getDirection()
		
		if I is None: 
			I=self.getCurrentButton()
			
		if I is None:
			I=0

		if pos is None:
			pos=(self.slider_x_pos.value,self.slider_y_pos.value)

		logger.info(f"addProbe I={I} pos={pos} dir={dir}")

		probe=self.probes[dir][I]
		self.removeProbe(probe)
		self.setCurrentButton(I)

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

		x,y=pos
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
		probe.pos = [x,y]
		
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
		print(P1,P2)

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

		# for debugging draw points
		if True:
			xs,ys=[[],[]]
			for Z in range(P1[2],P2[2],Delta[2]) if dir!=2 else (P1[2],):
				for Y in range(P1[1],P2[1],Delta[1]) if dir!=1 else (P1[1],):
					for X in range(P1[0],P2[0],Delta[0]) if dir!=0 else (P1[0],):
						x,y,z=LogicToPhysic([X,Y,Z])
						xs.append(x)
						ys.append(y)
			probe.renderers.target.append(self.canvas.fig.scatter(xs, ys, color= probe.color))
			x1,x2=min(xs),max(xs)
			y1,y2=min(ys),max(ys)
			probe.renderers.target.append(self.canvas.fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=1, color= probe.color))
		


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
				probe.renderers.plot.append(self.probe_fig.line(xs, [mean(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))

			if op=="mM":
				probe.renderers.plot.append(self.probe_fig.line(xs, [min(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))
				probe.renderers.plot.append(self.probe_fig.line(xs, [max(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))

			if op=="med":
				probe.renderers.plot.append(self.probe_fig.line(xs, [median(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))	

			if op=="*":
				for it in ys:
					probe.renderers.plot.append(self.probe_fig.line(xs, it, line_width=2, legend_label=probe.color, line_color=probe.color))

		probe.y_range=[np.min(data),np.max(data)]
		self.probe_fig.y_range.start=min([probe.y_range[0] for probe in self.probes[dir] if probe.renderers.plot])
		self.probe_fig.y_range.end  =max([probe.y_range[1] for probe in self.probes[dir] if probe.renderers.plot])


	# removeProbe
	def removeProbe(self, probe):
		self.removeRenderer(self.canvas.fig, probe.renderers.target)
		self.removeRenderer(self.probe_fig , probe.renderers.plot)
		probe.renderers.target=[]
		probe.renderers.plot=[]

	# refreshAllProbes
	def refreshAllProbes(self):
		Button=self.getCurrentButton()
		dir=self.getDirection()
		for I,probe in enumerate(self.probes[dir]):

			if probe.status == INACTIVE or probe.pos is None: 
				continue 
			
			# automatic add only if it was added previosly
			self.addProbe(I=I, pos=probe.pos)
		
		self.setCurrentButton(Button)
