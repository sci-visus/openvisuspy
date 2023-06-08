import os,sys,logging,time,types,copy
import numpy as np

# bokeh dep
import bokeh
from bokeh.io import show
from bokeh.models import Range1d,Select,CheckboxButtonGroup,Slider, RangeSlider,Button,Row,Column,Div,CheckboxGroup
from bokeh.layouts import column, row
from bokeh.plotting import figure
from bokeh.events import ButtonClick,DoubleTap
from types import SimpleNamespace

# OpenVisus depencency
from openvisuspy import SetupLogger, GetBackend, Slice, Slices,ExecuteBoxQuery


COLORS = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"] 
INACTIVE,ACTIVE,CURRENT=0,1,2	

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
class ProbeTool:

	# constructor
	def __init__(self, view):
		self.view=view
		self.renderers=SimpleNamespace()
		self.renderers.offset=None
		self.probes={0: [], 1: [], 2: []}
		self.db=self.view.db

		# create buttons
		self.buttons=[]
		self.css_styles = ""
		for I,color in enumerate(COLORS):
			button = Button(label=color, sizing_mode="stretch_width")
			button.css_classes=[f"custom_button_0_{color}"]
			button.on_event(ButtonClick, lambda evt,I=I:  self.onButtonClick(I))
			self.buttons.append(button)
			self.css_styles +=  """
				.custom_button_0_{color} button.bk.bk-btn.bk-btn-default  {}
				.custom_button_1_{color} button.bk.bk-btn.bk-btn-default  {background-color: {color}; }
				.custom_button_2_{color} button.bk.bk-btn.bk-btn-default  {background-color: {color}; box-shadow: 2px 2px; }
			""".replace("{color}",color)

			for dir in range(3):
				self.probes[dir].append(Probe(status=INACTIVE,button=button,color=color))
				
		self.fig = figure(
			title="Line Plot", 
			x_axis_label="Z", 
			y_axis_label="f", 
			toolbar_location=None, 
			x_range = (0,1), 
			y_range = view.getPaletteRange(),
			sizing_mode="stretch_both"
		) 

		# change the offset on the proble plot
		self.fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

		# probe XY space
		if True:

			# where the center of the probe (can be set by double click or using this)
			self.slider_x_pos=Slider(step=1, title="X coordinate", sizing_mode="stretch_width" )
			self.slider_x_pos .on_change('value_throttled', lambda attr,old, x: self.addProbe())

			self.slider_y_pos=Slider(value=0, step=1, title="Y coordinate", sizing_mode="stretch_width" )
			self.slider_y_pos .on_change('value_throttled', lambda attr,old, y: self.addProbe())

			# probe dims (i.e. rect sizes on the left fiew)
			self.slider_x_dim=Slider(start=1, end=33, value=15 , step=2, title="X size")
			self.slider_x_dim.on_change('value_throttled', lambda attr,old, x: self.refreshAllProbes())	

			self.slider_y_dim=Slider(start=1, end=33, value=15, step=2, title="Y size")
			self.slider_y_dim.on_change('value_throttled', lambda attr,old, y: self.refreshAllProbes())

		# probe Z space
		if True:

			# Z range
			self.slider_z_range = RangeSlider(step=1, title="Range")
			self.slider_z_range.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

			# Z resolution 
			self.slider_z_res = Slider(start=1, end=self.db.getMaxResolution(), value=self.db.getMaxResolution(), step=1, title="Res")
			self.slider_z_res.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

			# Z op
			self.slider_z_op = CheckboxButtonGroup(labels=["avg","mM","med","*"], active=[0])
			self.slider_z_op.on_change("active",lambda attr,old, z: self.refreshAllProbes()) 	

			self.debug_mode = CheckboxButtonGroup(labels=["Debug"], active=[])
			self.debug_mode.on_change("active",lambda attr,old, z: self.refreshAllProbes())		

		# add probe in case of double click
		self.view.canvas.enableDoubleTap(lambda x,y: self.addProbe(pos=(x,y)))

		# need to take control 
		self.view.__setOffset=self.view.setOffset
		self.view.__setDirection=self.view.setDirection
		self.view.setOffset    = self.setOffset
		self.view.setDirection = self.setDirection
		self.setDirection(2)


	# getBokehLayout
	def getBokehLayout(self, doc):
		return Column(
			Div(text="<style>\n" + self.css_styles + "</style>"),
			Row(self.slider_x_pos, self.slider_x_dim, sizing_mode="stretch_width"),
			Row(self.slider_y_pos, self.slider_y_dim, sizing_mode="stretch_width"),
			Row(*[button for button in self.buttons], sizing_mode="stretch_width"),
			Row(
				self.view.getBokehLayout(doc=doc), 
				
				Column(
					Row(self.debug_mode, self.slider_z_range,self. slider_z_res, self.slider_z_op, sizing_mode="stretch_width"),
					self.fig,
					sizing_mode="stretch_both"
				),
				sizing_mode="stretch_both"
			),
			sizing_mode="stretch_both")		


	# getDirection
	def getDirection(self):
		return self.view.getDirection()

	# clearProbes
	def clearProbes(self):
		for dir in range(3):
			for probe in self.probes[dir]:
				self.removeProbe(probe)

	# setDirection
	def setDirection(self, dir):

		self.clearProbes()
		self.view.__setDirection(dir)  
		P1,P2=self.db.getLogicBox()
		x1,y1=self.view.project(P1);z1=P1[dir]
		x2,y2=self.view.project(P2);z2=P2[dir]

		self.slider_x_pos.start = x1;self.slider_x_pos.end   = x2-1;self.slider_x_pos.value = x1
		self.slider_y_pos.start = y2;self.slider_y_pos.end   = y2-1;self.slider_y_pos.value = y1
		self.slider_z_range.start=z1;self.slider_z_range.end  =z2-1;self.slider_z_range.value=[z1, z2-1]

		self.fig.x_range.start = self.slider_z_range.start
		self.fig.x_range.end   = self.slider_z_range.end

		self.setOffset(z1)
		self.setCurrentButton(0)
		self.refreshAllProbes()

	# getoffset
	def getoffset(self):
		return self.view.getOffset()

	# setOffset
	def setOffset(self, value):
		self.view.__setOffset(value) # internally this update the slider widget
		self.removeRenderer(self.fig, self.renderers.offset)
		self.renderers.offset=None
		self.renderers.offset=self.fig.line([value,value],[self.slider_z_range.start,self.slider_z_range.end],line_width=2,color="lightgray")

	# onButtonClick
	def onButtonClick(self,  I):
		
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

	# renderTarget
	def renderTarget(self,probe,x1,y1,x2,y2,line_width=1,color="black"):
		
		x=(x1+x2)/2.0
		y=(y1+y2)/2.0
		probe.renderers.target.append(self.view.canvas.fig.line([x-0.5, x+0.5], [y,y], line_width=line_width, color= color))
		probe.renderers.target.append(self.view.canvas.fig.line([x, x], [y-0.5,y+0.5], line_width=line_width, color= color))
		probe.renderers.target.append(self.view.canvas.fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=line_width, color= color))

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

		for it in self.slider_z_op.active:
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

		P1=self.view.unproject([x1,y1]);P1[dir]=z1
		P2=self.view.unproject([x2,y2]);P2[dir]=z2
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
		if self.debug_mode.active==[0]:
			print(f"Executing probe query  bitmask={bitmask} maxh={maxh} (x1,y1)={(x1,y1)} (x2,y2)={(x2,y2)} endh={endh} delta={delta}")
			print(f"unprojected box at full-res [{P1},{P2}) ")
			print(f"aligned box at endh resolution  [{A},{B})")
			
			points=[[],[]]
			for Z in range(A[2],B[2],delta[2]):
				for Y in range(A[1],B[1],delta[1]):
					for X in range(A[0],B[0],delta[0]):
						x,y=self.view.project([X,Y,Z])
						points[0].append(x)
						points[1].append(y)
			probe.renderers.target.append(self.view.canvas.fig.scatter(points[0], points[1], color= "black"))

		# execute the query
		if all([P1[I]<P2[I] for I in range(3)]):
			access=self.db.createAccess()
			data=list(ExecuteBoxQuery(self.db, access=access, logic_box=[A,B],  endh=endh, num_refinements=1, full_dim=True))[0]['data']
			self.fig.y_range.start=min(self.fig.y_range.start,np.min(data))
			self.fig.y_range.end  =max(self.fig.y_range.end  ,np.max(data))	
			self.renderProbe(probe, [A,B], delta, data)

	# removeProbe
	def removeProbe(self, probe):
		self.removeRenderer(self.view.canvas.fig, probe.renderers.target)
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
