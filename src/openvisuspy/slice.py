import os,sys,io,types,threading,time,logging
import numpy as np

from . backend import Aborted,LoadDataset,QueryNode
from . canvas import Canvas
from . widgets import Widgets

from . utils   import IsPyodide, AddAsyncLoop

from bokeh.models import Select,LinearColorMapper,LogColorMapper,ColorBar,Button,Slider,TextInput,Row,Column,Div



logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////////////////////////////////
class Slice(Widgets):
	
	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None):

		super().__init__(doc=doc, is_panel=is_panel, parent=parent)
		self.show_options  = ["palette","timestep","field","direction","offset","viewdep","quality"]
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
		self.canvas = Canvas(self.id, self.color_bar, sizing_mode='stretch_both',toolbar_location=None)
		self.canvas.on_resize=self.onCanvasResize
		self.canvas.enableDoubleTap(self.onDoubleTap)

	# getShowOptions
	def getShowOptions(self):
		return self.show_options

	# setShowOptions
	def setShowOptions(self,value):
		self.show_options=value
		self.first_row_layout.children=[getattr(self.widgets,it.replace("-","_")) for it in self.show_options ] 

	# getMainLayout 
	# NOTE: doc is needed in case of jupyter notebooks, where curdoc() gives the wrong value
	def getMainLayout(self):

		self.first_row_layout.children=[getattr(self.widgets,it.replace("-","_")) for it in self.show_options ] 

		ret = Column(
			self.first_row_layout,
			Row(self.canvas.fig, self.widgets.metadata, sizing_mode='stretch_both'),
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
		logger.info(f"[{self.id}]::setQueryLogicBox value={value}")
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
		logger.info(f"[{self.id}]::gotoPoint point={point}")
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
		self.canvas.renderPoints([self.toPhysic(point)])
  
  

	# gotNewData
	def gotNewData(self, result):

		data=result['data']
		try:
			data_range=np.min(data),np.max(data)
		except:
			data_range=0.0,0.0

		# depending on the palette range mode, I need to use different color mapper low/high
		mode=self.getPaletteRangeMode()
		
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
			low,high=self.getPaletteRange()
			is_log=isinstance(self.color_bar.color_mapper, LogColorMapper)
			if is_log:
				low =max(self.epsilon,low )
				high=max(self.epsilon,high)

			self.color_bar.color_mapper.low = low
			self.color_bar.color_mapper.high= high

		logic_box=result['logic_box'] 
		logger.info(f"[{self.id}]::rendering result data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box} data-range={data_range} palette-range={[low,high]} color-mapper-range={[self.color_bar.color_mapper.low,self.color_bar.color_mapper.high]}")

		# update the image
		(x1,y1),(x2,y2)=self.toPhysic(logic_box)
		self.canvas.setImage(data,x1,y1,x2,y2)

		(X,Y,Z),(tX,tY,tZ)=self.getLogicAxis()
		self.canvas.fig.xaxis.axis_label  = tX
		self.canvas.fig.yaxis.axis_label  = tY

		# update the status bar
		tot_pixels=data.shape[0]*data.shape[1]
		canvas_pixels=self.canvas.getWidth()*self.canvas.getHeight()
		MaxH=self.db.getMaxResolution()
		self.H=result['H']
		self.widgets.status_bar["response"].value=f"{result['I']}/{result['N']} {str(logic_box).replace(' ','')} {data.shape[0]}x{data.shape[1]} H={result['H']}/{MaxH} {result['msec']}msec"
		self.render_id+=1     
  
	# pushJobIfNeeded
	def pushJobIfNeeded(self):

		canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
		query_logic_box=self.getQueryLogicBox()
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

		quality=self.getQuality()

		if self.getViewDepedent():
			canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
			endh=None
			max_pixels=canvas_w*canvas_h
			if quality<0:
				max_pixels=int(max_pixels/pow(1.3,abs(quality))) # decrease the quality
			elif quality>0:
				max_pixels=int(max_pixels*pow(1.3,abs(quality))) # increase the quality
		else:
			max_pixels=None
			endh=self.db.getMaxResolution()+quality
		
		timestep=self.getTimestep()
		field=self.getField()
		box_i=[[int(it) for it in jt] for jt in query_logic_box]
		self.widgets.status_bar["request"].value=f"t={timestep} b={str(box_i).replace(' ','')} {canvas_w}x{canvas_h}"

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