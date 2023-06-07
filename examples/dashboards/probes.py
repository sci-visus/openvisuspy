import os,sys,logging,time,types
import numpy as np

from bokeh.io import show
from bokeh.models import Range1d,Select,CheckboxButtonGroup,Slider, RangeSlider,Button,Row,Column,Div
from bokeh.layouts import column, row
from bokeh.plotting import figure
from bokeh.events import ButtonClick,DoubleTap
import bokeh.colors
from types import SimpleNamespace

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
class LikeHyperSpy:

	# constructor
	def __init__(self, url, palette, palette_range):
		self.renderers=SimpleNamespace()
		self.renderers.offset=None
		self.probes={0: [], 1: [], 2: []}

		self.view=Slice(show_options=["palette","field","offset","direction"])

		self.view.setDataset(url)
		self.view.setDirection(2)
		self.view.setPalette(palette)
		self.view.setPaletteRange(palette_range)
		self.view.setTimestep(self.view.getTimestep())
		self.view.setField(self.view.getField())
		self.view.canvas.fig.toolbar_location = None

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
			y_range = palette_range
		) 

		# change the offset on the proble plot
		self.fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

		# where the center of the probe (can be set by double click or using this)
		self.slider_x_pos=Slider(step=1, title="X coordinate", sizing_mode="stretch_width" )
		self.slider_x_pos .on_change('value_throttled', lambda attr,old, x: self.addProbe())

		self.slider_y_pos=Slider(value=0, step=1, title="Y coordinate", sizing_mode="stretch_width" )
		self.slider_y_pos .on_change('value_throttled', lambda attr,old, y: self.addProbe())

		# probe dims (i.e. rect sizes on the left fiew)
		self.slider_x_dim=Slider(start=1, end=33, value=7, step=2, title="X size")
		self.slider_x_dim.on_change('value_throttled', lambda attr,old, x: self.refreshAllProbes())	

		self.slider_y_dim=Slider(start=1, end=33, value=7, step=2, title="Y size")
		self.slider_y_dim.on_change('value_throttled', lambda attr,old, y: self.refreshAllProbes())

		# Z range
		self.slider_z_range = RangeSlider(step=1, title="Z range", sizing_mode="stretch_width" )
		self.slider_z_range.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

		# Z op
		self.slider_z_op = Select(title="Z op", options=["mean","min-max","median","all"],value="mean") 
		self.slider_z_op.on_change("value",lambda attr,old, z: self.refreshAllProbes()) 	

		# Z resolution 
		self.slider_z_res = Slider(start=1, end=100, value=15, step=1, title="Z range %", sizing_mode="stretch_width")
		self.slider_z_res.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

		# add probe in case of double click
		self.view.canvas.enableDoubleTap(lambda x,y: self.addProbe(pos=(x,y)))

		# need to take control 
		self.view.__setOffset=self.view.setOffset
		self.view.__setDirection=self.view.setDirection
		self.view.setOffset    = self.setOffset
		self.view.setDirection = self.setDirection
		self.setDirection(2)


	# getLayout
	def getLayout(self):
		return Column(
			Div(text="<style>\n" + self.css_styles + "</style>"),
			Row(self.slider_x_pos, self.slider_x_dim, sizing_mode="stretch_width"),
			Row(self.slider_y_pos, self.slider_y_dim, sizing_mode="stretch_width"),
			Row(*[button for button in self.buttons], sizing_mode="stretch_width"),
			Row(
				self.view.getBokehLayout(doc=doc), 
				Column(
					Row(self.slider_z_range,self.slider_z_res, self.slider_z_op,sizing_mode="stretch_width"),
					self.fig),
				sizing_mode="stretch_width"
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


	# getAlignedBox
	def getAlignedBox(self, query_box,H):
		aligned_box, delta, num_sample=self.db.getAlignedBox(query_box, H)

		# fix bug? i need p2 to be a superset
		for I in range(3):
			while aligned_box[1][I]<query_box[1][I]:
				aligned_box[1][I]+=delta[I]

		print(f"# getAlignedBox  query_box={query_box} H={H} aligned_box={aligned_box} delta={delta} num_sample={num_sample}")
		return aligned_box, delta, num_sample

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

		op=self.slider_z_op.value
		from statistics import mean,median,stdev
		if op=="mean":
			probe.renderers.plot.append(self.fig.line(xs, [mean(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))

		elif op=="min-max":
			probe.renderers.plot.append(self.fig.line(xs, [min(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))
			probe.renderers.plot.append(self.fig.line(xs, [max(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))

		elif op=="median":
			probe.renderers.plot.append(self.fig.line(xs, [median(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))	

		elif op=="all":
			for it in ys:
				probe.renderers.plot.append(self.fig.line(xs, it, line_width=2, legend_label=probe.color, line_color=probe.color))
				
		else:
			raise Exception("internal error")			

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

		x,y,w,h=[int(it) for it in (x,y,w,h)]
		if (w % 2) == 0 : w+=1
		if (h % 2) == 0 : h+=1
		x1=x-(w//2);x2=x+(w//2)
		y1=y-(h//2);y2=y+(h//2)
		z1=self.slider_z_range.value[0]
		z2=self.slider_z_range.value[1] 
		self.renderTarget(probe,x-w//2,y-h//2,x+w//2,y+h//2,line_width=3,color=probe.color)
		print("A",(x1,y1),(x2,y2))

		P1=self.view.unproject([x1,y1]);P1[dir]=z1
		P2=self.view.unproject([x2,y2]);P2[dir]=z2
		for I in range(3): P2[I]+=1 
		print("B",P1,P2)
		endh=self.db.getMaxResolution()

		# desired=(z2-z1) * (self.slider_z_res.value/100.0) 
		# for H in range(endh,1,-1):
		#	aligned_box,delta,num_samples=self.getAlignedBox([P1,P2],H)
		#	# if num_samples[dir]<desired: break # not enough samples, stick the previous one
		#	endh=H # goood candidate
		
		access=self.db.createAccess()
		aligned_box, delta, num_sample=self.getAlignedBox([P1,P2], endh)	
		data=list(ExecuteBoxQuery(self.db, access=access, logic_box=aligned_box,  endh=endh, num_refinements=1, full_dim=True))[0]['data']
		self.fig.y_range.start=min(self.fig.y_range.start,np.min(data))
		self.fig.y_range.end  =max(self.fig.y_range.end  ,np.max(data))	

		print("C",aligned_box)
		X1,Y1,Z1=aligned_box[0]
		X2,Y2,Z2=aligned_box[1]		
		P1i=[X1         ,Y1         ,Z1         ];x1i,y1i=self.view.project(P1i);z1i=P1i[dir]
		P2i=[X2-delta[0],Y2-delta[1],Z2-delta[2]];x2i,y2i=self.view.project(P2i);z2i=P2i[dir]
		self.renderTarget(probe, x1i,y1i,x2i,y2i,line_width=1,color="gray")

		self.renderProbe(probe, aligned_box, delta, data)

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




# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	if "--py" in sys.argv:
		backend="py"
		os.environ["VISUS_BACKEND"]=backend
	
	if "--cpp" in sys.argv:
		backend="cpp"
		os.environ["VISUS_BACKEND"]=backend

	from openvisuspy import SetupLogger, GetBackend, Slice, Slices,ExecuteBoxQuery
	#logger=SetupLogger()
	#logger.info(f"GetBackend()={GetBackend()}")
	import bokeh
	doc=bokeh.io.curdoc()			

	instance=LikeHyperSpy(
		url="http://atlantis.sci.utah.edu/mod_visus?dataset=block_raw&cached=1",
		palette="colorcet.coolwarm",
		palette_range=[ 8644., 65530.//4])
	
	doc.add_root(instance.getLayout())		














