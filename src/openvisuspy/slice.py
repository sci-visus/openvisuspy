import os,sys,io,types,threading,time,logging
import numpy as np

from . backend import Aborted,LoadDataset,QueryNode
from . canvas import Canvas
from . widgets import Widgets

from . utils   import IsPyodide, AddAsyncLoop,cdouble

from bokeh.models import Select,LinearColorMapper,LogColorMapper,ColorBar,Button,Slider,TextInput,Row,Column,Div,UIElement



logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////////////////////////////////
class Slice(Widgets):
	
	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None):

		super().__init__(doc=doc, is_panel=is_panel, parent=parent)
		self.show_options  = ["palette","timestep","field","direction","offset","view_dep","resolution"]
		self.render_id     = 0
		self.aborted       = Aborted()
		self.new_job       = False
		self.current_img   = None
		self.options={}

		self.last_query_logic_box = None
		self.query_node=QueryNode()
		self.t1=time.time()
		self.H=None

		# create Gui
		self.canvas = Canvas(self.id)
		self.canvas.on_resize=self.onCanvasResize
		self.canvas.enableDoubleTap(self.onDoubleTap)

	# getShowOptions
	def getShowOptions(self):
		return self.show_options

	# getFirstRowChildren
	def getFirstRowChildren(self):
		ret=[getattr(self.widgets,it.replace("-","_")) for it in self.show_options ] 
		ret=[it.getMainLayout() if not isinstance(it,UIElement) else it for it in ret]
		return ret		

	# setShowOptions
	def setShowOptions(self,value):
		self.show_options=value
		self.first_row_layout.children=self.getFirstRowChildren()

	# getMainLayout 
	# NOTE: doc is needed in case of jupyter notebooks, where curdoc() gives the wrong value
	def getMainLayout(self):

		self.first_row_layout.children=self.getFirstRowChildren()

		ret = Column(
			self.first_row_layout,
			Row(self.canvas.getMainLayout(), self.widgets.metadata, sizing_mode='stretch_both'),
			Row(
				self.widgets.status_bar["request"],
				self.widgets.status_bar["response"], 
				sizing_mode='stretch_width'
			),
			sizing_mode="stretch_both")

		if IsPyodide():
			self.idle_callback=AddAsyncLoop(f"{self}::onIdle",self.onIdle,1000//30)

		elif self.is_panel:
			import panel as pn
			self.idle_callback=pn.state.add_periodic_callback(self.onIdle, period=1000//30)

			# i should return some panel
			if self.parent is None:
				self.panel_layout=pn.pane.Bokeh(ret,sizing_mode="stretch_both")
				ret=self.panel_layout

		else:
			self.idle_callback=self.doc.add_periodic_callback(self.onIdle, 1000//30)
			
		self.start()
		return ret

	# onDoubleTap (NOTE: x,y are in physic coords)
	def onDoubleTap(self,x,y):
		if False: 
			self.gotoPoint([x,y])

	# start
	def start(self):
		super().start()
		self.query_node.start()

	# stop
	def stop(self):
		super().stop()
		self.aborted.setTrue()
		self.query_node.stop()	

	# onCanvasResize
	def onCanvasResize(self):
		if not self.db: return
		dir=self.getDirection()
		offset=self.getOffset()
		self.setDirection(dir)
		self.setOffset(offset)

	# onIdle
	async def onIdle(self):

		# not ready for jobs
		if not self.db:
			return
		
		self.canvas.checkFigureResize()

		# problem in pyodide, I will not get pixel size until I resize the window (remember)
		if self.canvas.getWidth()<=0 or self.canvas.getHeight()<=0:
			return 
		
		await super().onIdle()

		result=self.query_node.popResult(last_only=True) 
		if result is not None: 
			self.gotNewData(result)

		self.pushJobIfNeeded()

	# refresh
	def refresh(self):
		super().refresh()
		self.aborted.setTrue()
		self.new_job=True
  
	# getQueryLogicBox
	def getQueryLogicBox(self):
		(x1,x2),(y1,y2)=self.canvas.getViewport()
		return self.toLogic([(x1,y1),(x2,y2)])

	# setQueryLogicBox (NOTE: it ignores the coordinates on the direction)
	def setQueryLogicBox(self,value,):
		logger.info(f"[{self.id}] value={value}")
		proj=self.toPhysic(value) 
		x1,y1=proj[0]
		x2,y2=proj[1]
		self.canvas.setViewport([(x1,x2),(y1,y2)])
		self.refresh()
  
	# getLogicCenter
	def getLogicCenter(self):
		pdim=self.getPointDim()  
		p1,p2=self.getQueryLogicBox()
		assert(len(p1)==pdim and len(p2)==pdim)
		return [(p1[I]+p2[I])*0.5 for I in range(pdim)]

	# getLogicSize
	def getLogicSize(self):
		pdim=self.getPointDim()
		p1,p2=self.getQueryLogicBox()
		assert(len(p1)==pdim and len(p2)==pdim)
		return [(p2[I]-p1[I]) for I in range(pdim)]

	# setDirection
	def setDirection(self,dir):
		super().setDirection(dir)
		dims=[int(it) for it in self.db.getLogicSize()]
		self.setQueryLogicBox(([0]*self.getPointDim(),dims))
		self.refresh()
  

	# setAccess
	def setAccess(self, value):
		self.access=value
		self.refresh()

  # gotoPoint
	def gotoPoint(self,point):
		assert(False) # not sure if point is in physic or logic corrdinates (I think physic)
		logger.info(f"[{self.id}] point={point}")
		pdim=self.getPointDim()
		# go to the slice
		if pdim==3:
			dir=self.getDirection()
			self.setOffset(point[dir])
		# the point should be centered in p3d
		(p1,p2),dims=self.getQueryLogicBox(),self.getLogicSize()
		p1,p2=list(p1),list(p2)
		for I in range(pdim):
			p1[I],p2[I]=point[I]-dims[I]/2,point[I]+dims[I]/2
		self.setQueryLogicBox([p1,p2])
		self.canvas.renderPoints([self.toPhysic(point)]) # COMMENTED OUT
  
	# gotNewData
	def gotNewData(self, result):

		data=result['data']
		try:
			data_range=np.min(data),np.max(data)
		except:
			data_range=0.0,0.0

		logic_box=result['logic_box'] 

		# depending on the palette range mode, I need to use different color mapper low/high
		mode=self.getPaletteRangeMode()

		# show the user what is the current offset
		maxh=self.db.getMaxResolution()
		dir=self.getDirection()
		vt,vs=self.logic_to_physic[dir]
		endh=result['H']

		user_physic_offset=self.getOffset()
		real_logic_offset=logic_box[0][dir]
		real_physic_offset=vs*real_logic_offset + vt 
		user_logic_offset=int((user_physic_offset-vt)/vs)
		
		self.widgets.offset.show_value=False

		if False and (vs==1.0 and vt==0.0):
			self.widgets.offset.title=" ".join([
				f"Offset: {user_logic_offset}±{abs(user_logic_offset-real_logic_offset)}",
				f"Max Res: {endh}/{maxh}"
			])

		else:
			self.widgets.offset.title=" ".join([
				f"Offset: {user_physic_offset:.3f}±{abs(user_physic_offset-real_physic_offset):.3f}",
				f"Pixel: {user_logic_offset}±{abs(user_logic_offset-real_logic_offset)}",
				f"Max Res: {endh}/{maxh}"
			])
		
		# refresh the range
		if True:

			# in dynamic mode, I need to use the data range
			if mode=="dynamic":
				self.widgets.palette_range_vmin.value = str(data_range[0])
				self.widgets.palette_range_vmax.value = str(data_range[1])
				
			# in data accumulation mode I am accumulating the range
			if mode=="dynamic-acc":
				self.widgets.palette_range_vmin.value = str(min(float(self.widgets.palette_range_vmin.value), data_range[0]))
				self.widgets.palette_range_vmax.value = str(max(float(self.widgets.palette_range_vmax.value), data_range[1]))

			# update the color bar
			low =cdouble(self.widgets.palette_range_vmin.value)
			high=cdouble(self.widgets.palette_range_vmax.value)

			self.color_bar.color_mapper.low = max(self.epsilon,low ) if self.getColorMapperType()=="log" else low
			self.color_bar.color_mapper.high= max(self.epsilon,high) if self.getColorMapperType()=="log" else high

		logger.info(f"[{self.id}]::rendering result data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box} data-range={data_range} palette-range={[low,high]} color-mapper-range={[self.color_bar.color_mapper.low,self.color_bar.color_mapper.high]}")

		# update the image
		(x1,y1),(x2,y2)=self.toPhysic(logic_box)
		self.canvas.setImage(data,x1,y1,x2,y2, self.color_bar)

		(X,Y,Z),(tX,tY,tZ)=self.getLogicAxis()
		self.canvas.setAxisLabels(tX,tY)

		# update the status bar
		tot_pixels=data.shape[0]*data.shape[1]
		canvas_pixels=self.canvas.getWidth()*self.canvas.getHeight()
		self.H=result['H']
		query_status="running" if result['running'] else "FINISHED"
		self.widgets.status_bar["response"].value=" ".join([
			f"#{result['I']+1}",
			f"{str(logic_box).replace(' ','')}",
			f"{data.shape[0]}x{data.shape[1]}",
			f"Res={result['H']}/{maxh}",
			f"{result['msec']}msec",
			str(query_status)
		])
		self.render_id+=1     
  
	# pushJobIfNeeded
	def pushJobIfNeeded(self):

		canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
		query_logic_box=self.getQueryLogicBox()
		offset=self.getOffset()
		pdim=self.getPointDim()
		if not self.new_job and str(self.last_query_logic_box)==str(query_logic_box):
			return

		logger.info(f"[{self.id}] pushing new job query_logic_box={query_logic_box}...")

		# abort the last one
		self.aborted.setTrue()
		self.query_node.waitIdle()
		num_refinements = self.getNumberOfRefinements()
		if num_refinements==0:
			num_refinements=3 if pdim==2 else 4
		self.aborted=Aborted()

		resolution=self.getResolution()
		
		# I will use max_pixels to decide what resolution, I am using resolution just to add/remove a little the 'quality'
		if self.isViewDependent():
			endh=None 
			canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
			max_pixels=canvas_w*canvas_h
			delta=resolution-self.getMaxResolution()
			if resolution<self.getMaxResolution():
				max_pixels=int(max_pixels/pow(1.3,abs(delta))) # decrease 
			elif resolution>self.getMaxResolution():
				max_pixels=int(max_pixels*pow(1.3,abs(delta))) # increase 
		else:
			# I am not using the information about the pixel on screen
			max_pixels=None
			endh=resolution
		
		timestep=self.getTimestep()
		field=self.getField()
		box_i=[[int(it) for it in jt] for jt in query_logic_box]
		self.widgets.status_bar["request"].value=f"t={timestep} b={str(box_i).replace(' ','')} {canvas_w}x{canvas_h}"
		self.widgets.status_bar["response"].value="Running..."

		self.query_node.pushJob(
			self.db, 
			access=self.access,
			timestep=timestep, 
			field=field, 
			logic_box=query_logic_box, 
			max_pixels=max_pixels, 
			num_refinements=num_refinements, 
			endh=endh, 
			aborted=self.aborted
		)
		self.last_query_logic_box=query_logic_box
		self.new_job=False

		logger.info(f"[{self.id}] pushed new job query_logic_box={query_logic_box}")

		# link views
		if self.isLinked() and self.parent:
			idx=self.parent.children.index(self)
			for child in self.parent.children:
				if child==self: continue
				child.setQueryLogicBox(query_logic_box)
				child.setOffset(offset)