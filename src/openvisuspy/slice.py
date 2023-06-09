import os,sys,io,types,threading,time,logging
import numpy as np

from . backend import Aborted,LoadDataset,QueryNode
from . canvas import Canvas
from . widgets import Widgets

logger = logging.getLogger(__name__)

# ////////////////////////////////////////////////////////////////////////////////////
class Slice(Widgets):
	
	# constructor
	def __init__(self,
			show_options=["palette","timestep","field","direction","offset","viewdep","quality","status_bar"],
			toolbar_location=None
			):

		super().__init__()
		self.render_id     = 0
		self.aborted       = Aborted()
		self.new_job       = False
		self.current_img   = None
		self.options={}
		self.canvas = Canvas(self.color_bar, self.color_mapper, sizing_mode='stretch_both',toolbar_location=toolbar_location)
		self.canvas.on_resize=self.onCanvasResize
		# self.canvas.enableDoubleTap(lambda x,y: self.gotoPoint(self.unproject([x,y])))
		self.last_logic_box = None
		self.gui=self.createGui(central_layout=self.canvas.fig, options=show_options)
		self.query_node=QueryNode()
		self.t1=time.time()
		self.H=None


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
		dir=self.getDirection()
		offset=self.getOffset()
		self.setDirection(dir)
		self.setOffset(offset)

	# onIdle
	async def onIdle(self):

		# not ready for jobs
		if not self.db:
			return

		# problem in pyodide, I will not get pixel size until I resize the window (remember)
		if self.canvas.getWidth()<=0 or self.canvas.getHeight()<=0:
			return 

		await super().onIdle()
		self.renderResultIfNeeded()
		self.pushJobIfNeeded()

	# setDataset
	def setDataset(self, url,db=None):
		super().setDataset(url,db=db)
		self.last_canvas_size=[0,0] 

	# refresh
	def refresh(self):
		super().refresh()
		self.aborted.setTrue()
		self.new_job=True	
   
	# project
	def project(self,value):

		pdim=self.getPointDim()
		dir=self.getDirection()

		# is a box
		if hasattr(value[0],"__iter__"):
			p1,p2=[self.project(p) for p in value]
			return [p1,p2]

		assert(pdim==len(value))

		# apply scaling and translating
		ret=[self.logic_to_pixel[I][0] + self.logic_to_pixel[I][1]*value[I] for I in range(pdim)]

		if pdim==3:
			del ret[dir]

		assert(len(ret)==2)
		return ret

	# unproject
	def unproject(self,value):

		assert(len(value)==2)

		pdim=self.getPointDim() 
		dir=self.getDirection()

		# is a box?
		if hasattr(value[0],"__iter__"):
			p1,p2=[self.unproject(p) for p in value]
			if pdim==3: 
				p2[dir]+=1 # make full dimensional
			return [p1,p2]

		ret=list(value)

		# reinsert removed coordinate
		if pdim==3:
			ret.insert(dir, 0)

		assert(len(ret)==pdim)

		# scaling/translatation
		ret=[(ret[I]-self.logic_to_pixel[I][0])/self.logic_to_pixel[I][1] for I in range(pdim)]

		
		# this is the right value in logic domain
		if pdim==3:
			ret[dir]=self.getOffset()

		assert(len(ret)==pdim)
		return ret
  
	# getLogicBox
	def getLogicBox(self):
		x1,y1,x2,y2=self.canvas.getViewport()
		return self.unproject(((x1,y1),(x2,y2)))

	# setLogicBox (NOTE: it ignores the coordinates on the direction)
	def setLogicBox(self,value):
		logger.info(f"Slice[{self.id}]::setLogicBox value={value}")
		proj=self.project(value)
		self.canvas.setViewport(*(proj[0] + proj[1]))
		self.refresh()
  
	# getLogicCenter
	def getLogicCenter(self):
		pdim=self.getPointDim()  
		p1,p2=self.getLogicBox()
		assert(len(p1)==pdim and len(p2)==pdim)
		return [(p1[I]+p2[I])*0.5 for I in range(pdim)]

	# getLogicSize
	def getLogicSize(self):
		pdim=self.getPointDim()
		p1,p2=self.getLogicBox()
		assert(len(p1)==pdim and len(p2)==pdim)
		return [(p2[I]-p1[I]) for I in range(pdim)]

	# setAccess
	def setAccess(self, value):
		self.access=value
		self.refresh()

	# setDirection
	def setDirection(self,dir):
		super().setDirection(dir)
		dims=[int(it) for it in self.db.getLogicSize()]
		self.setLogicBox(([0]*self.getPointDim(),dims))
		self.refresh()
  
  # gotoPoint
	def gotoPoint(self,point):
		logger.info(f"Slice[{self.id}]::gotoPoint point={point}")
		pdim=self.getPointDim()
		# go to the slice
		if pdim==3:
			dir=self.getDirection()
			self.setOffset(point[dir])
		# the point should be centered in p3d
		(p1,p2),dims=self.getLogicBox(),self.getLogicSize()
		p1,p2=list(p1),list(p2)
		for I in range(pdim):
			p1[I],p2[I]=point[I]-dims[I]/2,point[I]+dims[I]/2
		self.setLogicBox([p1,p2])
		self.canvas.renderPoints([self.project(point)])
  
	# renderResultIfNeeded
	def renderResultIfNeeded(self):
		result=self.query_node.popResult(last_only=True) 
		if result is None: return
		data=result['data']
		logic_box=result['logic_box'] 
		logger.info(f"Slice[{self.id}]::rendering result data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box}")
		(x1,y1),(x2,y2)=self.project(logic_box)
		self.canvas.setImage(data,x1,y1,x2,y2)
		tot_pixels=data.shape[0]*data.shape[1]
		canvas_pixels=self.canvas.getWidth()*self.canvas.getHeight()
		MaxH=self.db.getMaxResolution()
		self.H=result['H']
		self.widgets.status_bar["response"].value=f"{result['I']}/{result['N']} {str(logic_box).replace(' ','')} {data.shape[0]}x{data.shape[1]} H={result['H']}/{MaxH} {result['msec']}msec"
		self.render_id+=1     
  
	# pushJobIfNeeded
	def pushJobIfNeeded(self):
     
		canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
 
		logic_box=self.getLogicBox()
		pdim=self.getPointDim()
		if not self.new_job and str(self.last_logic_box)==str(logic_box):
			return

		logger.info("pushing new job")

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
		box_i=[[int(it) for it in jt] for jt in logic_box]
		self.widgets.status_bar["request"].value=f"t={timestep} b={str(box_i).replace(' ','')} {canvas_w}x{canvas_h}"

		self.query_node.pushJob(
			self.db, 
			access=self.access,
			timestep=timestep, 
			field=field, 
			logic_box=logic_box, 
			max_pixels=max_pixels, 
			num_refinements=num_refinements, 
			endh=endh, 
			aborted=self.aborted
		)
		self.last_logic_box=logic_box
		self.new_job=False

  
