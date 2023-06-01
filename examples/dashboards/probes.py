import os,sys,logging,time,types


from bokeh.io import show
from bokeh.models import Range1d,CheckboxButtonGroup,Slider, RangeSlider,Button,Row,Column,Div
from bokeh.layouts import column, row
from bokeh.plotting import figure
from bokeh.events import ButtonClick
import bokeh.colors

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	if "--py" in sys.argv:
		backend="py"
		os.environ["VISUS_BACKEND"]=backend
	
	if "--cpp" in sys.argv:
		backend="cpp"
		os.environ["VISUS_BACKEND"]=backend

	from openvisuspy import SetupLogger, IsPanelServe, GetBackend, Slice, Slices,ExecuteBoxQuery
	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")

	P=0
	
	view=Slice(show_options=["palette","field","offset","quality","status_bar"])
	view.setDataset("http://atlantis.sci.utah.edu/mod_visus?dataset=block_raw&cached=1" )
	view.setDirection(2)
	view.setPalette("colorcet.coolwarm")
	view.setPaletteRange([ 8644., 65530.//4])
	view.setTimestep(view.getTimestep())
	view.setField(view.getField())

	db=view.db
	(X1,Y1,Z1),(X2,Y2,Z2)=db.getLogicBox()
	W,H,D = db.getLogicSize()
	print("Dataset logic_box=",(X1,Y1,Z1),(X2,Y2,Z2),"logic_size",(W,H,D))

	fig = figure(
		title="Line Plot", 
		x_axis_label="Z", 
		y_axis_label="f", 
		toolbar_location=None, 
		x_range = (Z1,Z2), 
		y_range = view.getPaletteRange())	
	
	view_setOffset=view.setOffset
	def SetOffset(slice,value):
		view_setOffset(value)
		global fig
		for it in fig.select(name="draw-offset"):
			fig.renderers.remove(it)
		fig.line([value,value],[fig.y_range.start,fig.y_range.end],name="draw-offset")

	view.setOffset = types.MethodType(SetOffset, view)
	view.setOffset(0)
	
	slider_x=Slider(start=X1, end=X2-1, value=0, step=1, title="X coordindate")
	slider_y=Slider(start=Y1, end=Y2-1, value=0, step=1, title="Y coordinate")

	colors = ["blue","red","green","yellow","orange","brown","cyan","pink","purple"] 

	def RemoveProbe(P):
		for it in fig.select(name=f"draw-probe-{P}"):
			if it in fig.renderers:
				fig.renderers.remove(it)

		for it in view.canvas.fig.select(name=f"draw-probe-{P}"):
			if it in view.canvas.fig.renderers:
				view.canvas.fig.renderers.remove(it)		

	def AddProbe(P, x, y):
		RemoveProbe(P)
		color=colors[P]

		# I need the logic_box to be full-dim enough... is delta enough?
		delta=8
		x,y=int(x),int(y)
		logic_box=([x,y,Z1], [x+delta,y+delta,Z2])

		# I need tom use the current resolution from the view
		endh=view.H 
		logic_box, delta, __num_pixels=db.getAlignedBox(logic_box, endh)
		x,y,Z=logic_box[0]
		
		access=db.createAccess()
		data=list(ExecuteBoxQuery(db, access=access, logic_box=logic_box,  endh=endh, num_refinements=1))[0]['data']
		# print("DrawProbe",logic_box,data.dtype, data.shape)

		ys=list(data[:,0,0])
		xs=[logic_box[0][2]+I*delta[2] for I in range(len(ys))]

		fig.line(xs,ys, line_width=2, legend_label=color, line_color=color,name=f"draw-probe-{P}")
		view.canvas.fig.line([x ,x ], [Y1,Y2],line_width=2, color= color,name=f"draw-probe-{P}")
		view.canvas.fig.line([X1,X2], [y ,y ],line_width=2, color= color,name=f"draw-probe-{P}")

		slider_x.value = x
		slider_y.value = y		

	buttons = []
	for I,color in enumerate(colors):
		button = Button(label=color, width=80, css_classes =[f"custom_button_{color}"])

		def onButtonClick(I):
			global P
			if P==I: RemoveProbe(P)
			P=I
		button.on_event(ButtonClick, lambda evt,I=I:  onButtonClick(I))
		buttons.append(button)

	slider_x.on_change('value_throttled', lambda attr,old, x: AddProbe(P, x,slider_y.value))
	slider_y.on_change('value_throttled', lambda attr,old, y: AddProbe(P, slider_x.value,y))
	
	if not IsPanelServe():
		import bokeh
		doc=bokeh.io.curdoc()

	view.canvas.enableDoubleTap(lambda x,y: AddProbe(P, x,y))

	styles=Div(text="""
<style>
.custom-button                                        {background-color: #FF0000; color: #FFFFFF;}
.custom_button_blue button.bk.bk-btn.bk-btn-default   {color: black;font-size:12pt;background-color: blue;   border-color: #05b7ff;}
.custom_button_red button.bk.bk-btn.bk-btn-default    {color: black;font-size:12pt;background-color: red;    border-color: #05b7ff;}
.custom_button_green button.bk.bk-btn.bk-btn-default  {color: black;font-size:12pt;background-color: green;  border-color: #05b7ff;}
.custom_button_yellow button.bk.bk-btn.bk-btn-default {color: black;font-size:12pt;background-color: yellow;  border-color: #05b7ff;}
.custom_button_orange button.bk.bk-btn.bk-btn-default {color: black;font-size:12pt;background-color: orange;border-color: #05b7ff;}
.custom_button_brown button.bk.bk-btn.bk-btn-default  {color: black;font-size:12pt;background-color: brown;border-color: #05b7ff;}
.custom_button_cyan button.bk.bk-btn.bk-btn-default   {color: black;font-size:12pt;background-color: cyan;border-color: #05b7ff;}
.custom_button_pink button.bk.bk-btn.bk-btn-default   {color: black;font-size:12pt;background-color: pink;border-color: #05b7ff;}
.custom_button_purple button.bk.bk-btn.bk-btn-default {color: black;font-size:12pt;background-color: purple;border-color: #05b7ff;}
</style>	
	""")
	
	main_layout=Column(
		styles,
		slider_x,slider_y,
		Row(*buttons, sizing_mode="stretch_width"),
		Row(view.getPanelLayout() if IsPanelServe() else view.getBokehLayout(doc=doc) , fig))    

	if IsPanelServe():
		from openvisuspy.app import GetPanelApp
		app=GetPanelApp(main_layout)
		app.servable()
	else:
		doc.add_root(main_layout)		














