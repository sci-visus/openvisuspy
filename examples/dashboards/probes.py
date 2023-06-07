import os,sys,logging,time,types

from bokeh.io import show
from bokeh.models import Range1d,Select,CheckboxButtonGroup,Slider, RangeSlider,Button,Row,Column,Div
from bokeh.layouts import column, row
from bokeh.plotting import figure
from bokeh.events import ButtonClick,DoubleTap
import bokeh.colors
from types import SimpleNamespace

COLORS = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"] 
MAX_PROBE_DIM = 101	
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
		self.renderers.target=None
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
		self.probes=[]

		self.view=Slice(show_options=["palette","field","offset"])
		self.view.setDataset(url)
		self.view.setDirection(2)
		self.view.setPalette(palette)
		self.view.setPaletteRange(palette_range)
		self.view.setTimestep(self.view.getTimestep())
		self.view.setField(self.view.getField())
		self.view.canvas.fig.toolbar_location = None

		self.db=self.view.db
		p1,p2=self.db.getLogicBox()
		self.X1,self.Y1,self.Z1=p1
		self.X2,self.Y2,self.Z2=p2
		W,H,D = self.db.getLogicSize()

		# create buttons
		self.css_styles = ""
		for I,color in enumerate(COLORS):
			button = Button(label=color, sizing_mode="stretch_width")
			button.css_classes=[f"custom_button_0_{color}"]
			button.on_event(ButtonClick, lambda evt,I=I:  self.onButtonClick(I))
			self.probes.append(Probe(status=INACTIVE,button=button,color=color))

			self.css_styles +=  """
				.custom_button_0_{color} button.bk.bk-btn.bk-btn-default  {}
				.custom_button_1_{color} button.bk.bk-btn.bk-btn-default  {background-color: {color}; }
				.custom_button_2_{color} button.bk.bk-btn.bk-btn-default  {background-color: {color}; box-shadow: 2px 2px; }
			""".replace("{color}",color)


		self.fig = figure(
			title="Line Plot", 
			x_axis_label="Z", 
			y_axis_label="f", 
			toolbar_location=None, 
			x_range = (self.Z1,self.Z2), 
			y_range = palette_range
		) 

		# change the offset on the proble plot
		self.fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

		# offset in Z 
		self.view_original_setOffset=self.view.setOffset
		self.view.setOffset = self.setOffset
		
		# where the center of the probe (can be set by double click or using this)
		self.slider_x_pos=Slider(start=self.X1, end=self.X2-1, value=0, step=1, title="X coordinate", sizing_mode="stretch_width" )
		self.slider_x_pos .on_change('value_throttled', lambda attr,old, x: self.addProbe())

		self.slider_y_pos=Slider(start=self.Y1, end=self.Y2-1, value=0, step=1, title="Y coordinate", sizing_mode="stretch_width" )
		self.slider_y_pos .on_change('value_throttled', lambda attr,old, y: self.addProbe())

		# probe dims (i.e. rect sizes on the left fiew)
		self.slider_x_dim=Slider(start=1, end=MAX_PROBE_DIM, value=33, step=2, title="X size")
		self.slider_x_dim.on_change('value_throttled', lambda attr,old, x: self.refreshAllProbes())	

		self.slider_y_dim=Slider(start=1, end=MAX_PROBE_DIM, value=33, step=2, title="Y size")
		self.slider_y_dim.on_change('value_throttled', lambda attr,old, y: self.refreshAllProbes())

		# Z range
		self.slider_z_range = RangeSlider(start=self.Z1, end=self.Z2-1, value=[self.Z1, self.Z2-1], step=1, title="Z range", sizing_mode="stretch_width" )
		self.slider_z_range.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

		# Z op
		self.slider_z_op = Select(title="Z op", options=["mean","min-max","median"],value="mean") 
		self.slider_z_op.on_change("value",lambda attr,old, z: self.refreshAllProbes()) 	

		# Z resolution 
		self.slider_z_res = Slider(start=1, end=100, value=15, step=1, title="Z range %", sizing_mode="stretch_width")
		self.slider_z_res.on_change('value_throttled', lambda attr,old, z: self.refreshAllProbes())

		# add probe in case of double click
		self.view.canvas.enableDoubleTap(lambda x,y: self.addProbe(pos=(x,y)))

		self.setOffset(0)
		self.setCurrentButton(0)


	# getLayout
	def getLayout(self):
		return Column(
			Div(text="<style>\n" + self.css_styles + "</style>"),
			Row(self.slider_x_pos, self.slider_x_dim, sizing_mode="stretch_width"),
			Row(self.slider_y_pos, self.slider_y_dim, sizing_mode="stretch_width"),
			Row(*[probe.button for probe in self.probes], sizing_mode="stretch_width"),
			Row(
				self.view.getBokehLayout(doc=doc), 
				Column(
					Row(self.slider_z_range,self.slider_z_res, self.slider_z_op,sizing_mode="stretch_width"),
					self.fig),
				sizing_mode="stretch_width"
			),
			sizing_mode="stretch_both")		

	# onButtonClick
	def onButtonClick(self,  I):

		status=self.probes[I].status
		
		# current -> inactive
		if  status== CURRENT:
			self.probes[I].status = INACTIVE  
			self.removeProbe(I)
			self.setCurrentButton(None)

		# active->current
		elif status==ACTIVE:
			self.setCurrentButton(I)

		# inactive ->  current
		elif status==INACTIVE:
			self.setCurrentButton(I)
			probe=self.probes[I]
			if probe.pos is not None:
				self.addProbe(I=I, pos=probe.pos)		
		else:
			raise Exception("internal Error")

	# setOffset
	def setOffset(self, value):

		# need to pass throught the set offset to the view
		self.view_original_setOffset(value) 
		self.removeRenderer(self.fig,self.renderers.offset)
		self.renderers.offset=None
		self.renderers.offset=self.fig.line([value,value],[self.fig.y_range.start,self.fig.y_range.end],line_width=2,color="lightgray")

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
		for I,probe in enumerate(self.probes):
			if probe.status==CURRENT:
				return I
		return None
	
	# setCurrentButton
	def setCurrentButton(self, value):
		for I,probe in enumerate(self.probes):
			probe.setCurrent(True if I==value else False) 
			

	# addProbe
	def addProbe(self, I=None, pos=None):
		
		if I is None: 
			I=self.getCurrentButton()

		if pos is None:
			pos=(self.slider_x_pos.value,self.slider_y_pos.value)

		x,y=pos
		w=self.slider_x_dim.value
		h=self.slider_y_dim.value

		self.removeProbe(I)
		self.setCurrentButton(I)

		probe=self.probes[I]

		# center x and dimensions
		x=int(x);w=(int(w) -1)//2*2+1
		y=int(y);h=(int(h) -1)//2*2+1
		
		x1,x2=x-w//2, x+w//2
		y1,y2=y-h//2, y+h//2	
		z1,z2=self.slider_z_range.value	
		z2+=1 # z is excluded in comparison to slider
		user_logic_box=([x1,y1,z1],[x2,y2,z2])

		# guess query resolution until I don't get enough samples
		depth=(z2-z1) * (self.slider_z_res.value/100.0)
		endh=self.db.getMaxResolution()
		for H in range(endh,1,-1):
			aligned_box, delta, num_samples=self.db.getAlignedBox(user_logic_box, H)
			if num_samples[2]<depth: break # not enough samples, stick the previous one
			endh=H # goood candidate, may try the next
		
		access=self.db.createAccess()
		aligned_box, delta, num_samples=self.db.getAlignedBox(user_logic_box, endh)
		print(f"# Probe Query color={probe.color} aligned_box={aligned_box} delta={delta} num_samples={num_samples}")		
		data=list(ExecuteBoxQuery(self.db, access=access, logic_box=aligned_box,  endh=endh, num_refinements=1))[0]['data']

		x1,y1,z1=aligned_box[0]
		x2,y2,z2=aligned_box[1]
		
		# render target 
		probe.renderers.target =self.view.canvas.fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=2, color= probe.color)	

		# render plot
		if True:
			xs=list(range(z1,z2,delta[2]))
			ys=[]
			m=self.fig.y_range.start
			M=self.fig.y_range.end
			
			for Y in range(data.shape[1]):
				for X in range(data.shape[2]):

					values=list(data[:,Y,X])
					ys.append(values)

					# enlarge plot Y range 
					m = min(m, min(values))
					M = max(M, max(values))

			self.fig.y_range.start=m
			self.fig.y_range.end  =M	

			op=self.slider_z_op.value
			from statistics import mean,median,stdev
			if op=="mean":
				probe.renderers.plot.append(self.fig.line(xs, [mean(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))
			elif op=="min-max":
				probe.renderers.plot.append(self.fig.line(xs, [min(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))
				probe.renderers.plot.append(self.fig.line(xs, [max(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))
			elif op=="median":
				probe.renderers.plot.append(self.fig.line(xs, [median(p) for p in zip(*ys)], line_width=2, legend_label=probe.color, line_color=probe.color))		
			else:
				raise Exception("internal error")		

		# keep the status for later
		self.slider_x_pos.value  = x
		self.slider_y_pos.value  = y
		probe.pos = [x,y]

	# removeProbe
	def removeProbe(self, I):
		if I == None:  I = self.getCurrentButton()
		if I == None:  return
		self.setCurrentButton(None)
		probe=self.probes[I]

		self.removeRenderer(self.view.canvas.fig, probe.renderers.target)
		probe.renderers.target=None

		self.removeRenderer(self.fig, probe.renderers.plot)
		probe.renderers.plot=[]

	# refreshAllProbes
	def refreshAllProbes(self):
		Button=self.getCurrentButton()

		self.fig.x_range.start = self.slider_z_range.value[0]
		self.fig.x_range.end   = self.slider_z_range.value[1]

		for I,probe in enumerate(self.probes):
			
			if probe.status == INACTIVE: 
				continue 

			# automatic add only if it was added previosly
			if probe.pos is not None:
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
	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")
	import bokeh
	doc=bokeh.io.curdoc()			

	instance=LikeHyperSpy(
		url="http://atlantis.sci.utah.edu/mod_visus?dataset=block_raw&cached=1",
		palette="colorcet.coolwarm",
		palette_range=[ 8644., 65530.//4]
	)
	
	doc.add_root(instance.getLayout())		














