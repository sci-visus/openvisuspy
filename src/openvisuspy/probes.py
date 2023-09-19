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
		self.renderers.target=[]
		self.renderers.plot=[]

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

		self.fig = figure(
			title="Line Plot", 
			x_axis_label="Z", 
			y_axis_label="f", 
			toolbar_location=None, 
			x_range = (0,1), 
			y_range = [vmin,vmax],
			sizing_mode="stretch_both"
		) 

		# change the offset on the proble plot
		self.fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

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

		# add probe in case of double click
		self.canvas.enableDoubleTap(lambda x,y: self.addProbe(pos=(x,y)))


	# setDataset
	def setDataset(self, url,db=None, force=False):
		super().setDataset(url, db=db, force=force)

		# rehentrant call
		if self.db: 
			self.slider_z_res.end=self.db.getMaxResolution()

	# getBokehLayout
	def getBokehLayout(self, doc):
		return Row(
				super().getBokehLayout(doc=doc), 
				Column(
					Div(text="<style>\n" + self.css_styles + "</style>"),
					Row(*[button for button in self.buttons], sizing_mode="stretch_width"),
					Row(
						self.slider_x_pos, 
						self.slider_y_pos, 
						self.slider_z_range,
						self.slider_z_op, 
						self.slider_z_res, 
						self.slider_num_points,
						sizing_mode="stretch_width"),
					self.fig,
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

		self.fig.xaxis.axis_label = self.slider_z_range.title

		self.setOffset(pbox[Z][0])
		self.setCurrentButton(0)
		self.refreshAllProbes()


	# setOffset
	def setOffset(self, value):
		super().setOffset(value)
		self.removeRenderer(self.fig, self.renderers.offset)
		self.renderers.offset=None
		self.renderers.offset=self.fig.line([value,value],[self.slider_z_range.start,self.slider_z_range.end],line_width=2,color="lightgray")

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

	# renderProbe
	def renderProbe(self, probe, aligned_box, delta, data):
		dir=self.getDirection()
		X1,Y1,Z1=aligned_box[0]
		X2,Y2,Z2=aligned_box[1]

		if dir==2:
			xs,ys=list(range(Z1,Z2,delta[2])),[]
			for Y in range(data.shape[1]):
				for X in range(data.shape[2]):
					ys.append(list(data[:,Y,X]))

		elif dir==1:
			xs,ys=list(range(Y1,Y2,delta[1])),[]
			for Z in range(data.shape[0]):
				for X in range(data.shape[2]):
					ys.append(list(data[Z,:,X]))

		else:
			xs,ys=list(range(X1,X2,delta[0])),[]
			for Z in range(data.shape[0]):
				for Y in range(data.shape[1]):
					ys.append(list(data[Z,Y,:]))


		from statistics import mean,median,stdev

		for it in [self.slider_z_op.active]:
			op=self.slider_z_op.labels[it]
		
			if op=="avg":
				probe.renderers.plot.append(self.fig.line(xs, [mean(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))

			if op=="mM":
				probe.renderers.plot.append(self.fig.line(xs, [min(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))
				probe.renderers.plot.append(self.fig.line(xs, [max(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))

			if op=="med":
				probe.renderers.plot.append(self.fig.line(xs, [median(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))	

			if op=="*":
				for it in ys:
					probe.renderers.plot.append(self.fig.line(xs, it, line_width=2, legend_label=probe.color, line_color=probe.color))
				
		

	# addProbe
	def addProbe(self, I=None, pos=None):
		
		if I is None: 
			I=self.getCurrentButton()

		if pos is None:
			pos=(self.slider_x_pos.value,self.slider_y_pos.value)

		# automatically update the fig X axis range
		self.fig.x_range.start = self.slider_z_range.value[0]
		self.fig.x_range.end   = self.slider_z_range.value[1]			

		x,y=pos
		w=self.slider_x_dim.value
		h=self.slider_y_dim.value

		dir=self.getDirection()
		probe=self.probes[dir][I]

		self.removeProbe(probe)
		self.setCurrentButton(I)

		# update trhe slider values
		self.slider_x_pos.value  = x
		self.slider_y_pos.value  = y

		# keep the status for later
		probe.pos = [x,y]		

		# compute x1,y1,x2,y2 but eigther extrema included (NOTE: it's working at full-res)
		x,y,w,h=[int(it) for it in (x,y,w,h)]
		if (w % 2) == 0 : w+=1
		if (h % 2) == 0 : h+=1
		x1=x-(w//2);x2=x+(w//2)
		y1=y-(h//2);y2=y+(h//2)
		z1=self.slider_z_range.value[0]
		z2=self.slider_z_range.value[1] 
		self.renderTarget(probe,x-w//2,y-h//2,x+w//2,y+h//2,line_width=3,color=probe.color)

		maxh=self.db.getMaxResolution()
		bitmask=self.db.getBitmask()

		P1=self.unproject([x1,y1]);P1[dir]=z1
		P2=self.unproject([x2,y2]);P2[dir]=z2
		for I in range(3): P2[I]+=1 # in OpenVisus the  box is [P1,P2) so I am enlarging a little

		endh=self.slider_z_res.value

		# compute delta
		delta=[1,1,1]
		for K in range(maxh,endh,-1):
			delta[ord(bitmask[K])-ord('0')]*=2

		# compute aligned start point inside the full-res target 
		A=[0,0,0]
		for I in range(3):
			A[I]=int(delta[I]*(P1[I]//delta[I]))
			while A[I]<P1[I]:  A[I]+=delta[I] 

		# target aligned end point, just outside the full-res target
		B=[A[0],A[1],A[2]]
		for I in range(3):
			while B[I]<P2[I]: B[I]+=delta[I]

		# for debugging draw points
		if True:
			logger.info(f"Executing probe query  bitmask={bitmask} maxh={maxh} (x1,y1)={(x1,y1)} (x2,y2)={(x2,y2)} endh={endh} delta={delta}")
			logger.info(f"unprojected box at full-res [{P1},{P2}) ")
			logger.info(f"aligned box at endh resolution  [{A},{B})")
			
			points=[[],[]]
			for Z in range(A[2],B[2],delta[2]):
				for Y in range(A[1],B[1],delta[1]):
					for X in range(A[0],B[0],delta[0]):
						x,y=self.project([X,Y,Z])
						points[0].append(x)
						points[1].append(y)
			probe.renderers.target.append(self.canvas.fig.scatter(points[0], points[1], color= "black"))

		# execute the query
		if all([P1[I]<P2[I] for I in range(3)]):
			access=self.db.createAccess()
			data=list(ExecuteBoxQuery(self.db, access=access, logic_box=[A,B],  endh=endh, num_refinements=1, full_dim=True))[0]['data']
			self.fig.y_range.start=min(self.fig.y_range.start,np.min(data))
			self.fig.y_range.end  =max(self.fig.y_range.end  ,np.max(data))	
			self.renderProbe(probe, [A,B], delta, data)

	# removeProbe
	def removeProbe(self, probe):
		self.removeRenderer(self.canvas.fig, probe.renderers.target)
		probe.renderers.target=[]

		self.removeRenderer(self.fig, probe.renderers.plot)
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
