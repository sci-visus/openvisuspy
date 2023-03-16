import os,sys,time,threading,queue,math, types,logging,copy
import numpy as np

from . utils import IsIterable,Clamp, HumanSize
from . backend import ReadStats, Aborted

logger = logging.getLogger(__name__)


# ////////////////////////////////////////////////////////////////////////////////////////////////////////////
def ExecuteBoxQuery(
	db,  
	access=None, 
	timestep=None, 
	field=None, 
	logic_box=None,
	max_pixels=None, 
	endh=None, 
	num_refinements=1, 
	aborted=Aborted()):

	assert(db)
	pdim=db.getPointDim()
	assert pdim==2 or pdim==3 # todo other cases?

	maxh=db.getMaxResolution()
	bitmask=db.getBitmask()
	dims=db.getLogicSize()

	if access is None:
		access=db.createAccess()

	if timestep is None:
		timestep=db.getTimestep()

	if field is None:
		field=db.getField()

	if logic_box is None:
		logic_box=db.getLogicBox()

	if endh is None:
		endh=maxh

	logger.info(f"begin timestep={timestep} field={field} logic_box={logic_box} num_refinements={num_refinements} max_pixels={max_pixels} endh={endh}")

	if IsIterable(max_pixels):
		max_pixels=int(np.prod(max_pixels,dtype=np.int64))
	 
	# if box is not specified get the all box
	if logic_box is None:
		W,H,D=[int(it) for it in db.getLogicSize()]
		logic_box=[[0,0,0],[W,H,D]]
	  
	# fix logic box by cropping
	if True:
		p1,p2=list(logic_box[0]),list(logic_box[1])
		slice_dir=None
		for I in range(pdim):
			# *************** is a slice? *******************
			if pdim==3 and (p2[I]-p1[I])==1:
				assert slice_dir is None 
				slice_dir=I
				p1[I]=Clamp(p1[I],0,dims[I])
				p2[I]=p1[I]+1
			else:
				p1[I]=Clamp(int(math.floor(p1[I])),     0,dims[I])
				p2[I]=Clamp(int(math.ceil (p2[I])) ,p1[I],dims[I])
			assert p1[I]<p2[I]
		logic_box=(p1,p2)
	 
	# is view dependent? if so guess max resolution 
	if max_pixels:
		original_box=logic_box
		for H in range(maxh,0,-1):
			aligned_box,delta,num_pixels=db.getAlignedBox(original_box,H, slice_dir=slice_dir)
			tot_pixels=np.prod(num_pixels,dtype=np.int64)
			if tot_pixels<=max_pixels*1.10:
				endh=H
				logger.info(f"Guess resolution H={H} original_box={original_box} aligned_box={aligned_box} delta={delta} num_pixels={repr(num_pixels)} tot_pixels={tot_pixels:,} max_pixels={max_pixels:,} end={endh}")
				logic_box=aligned_box
				break

	# this is the query I need
	logic_box,delta,num_pixels=db.getAlignedBox(logic_box, endh, slice_dir=slice_dir)

	logic_box=[
		[int(it) for it in logic_box[0]],
		[int(it) for it in logic_box[1]]
	]

	end_resolutions=list(reversed([endh-pdim*I for I in range(num_refinements) if endh-pdim*I>=0]))

	# print("beginBoxQuery","box",logic_box.toString(),"field",field,"timestep",timestep,"end_resolutions",end_resolutions)
	t1=time.time()
	I,N=0,len(end_resolutions)
	query=db.createBoxQuery(timestep=timestep, field=field, logic_box=logic_box, end_resolutions=end_resolutions, aborted=aborted)
	db.beginBoxQuery(query)
	while db.isQueryRunning(query):

		data=db.executeBoxQuery(access,query)

		if data is None: 
			break
		

		# is a slice? I need to reduce the size (i.e. from 3d data to 2d data)
		if slice_dir is not None:
			dims=list(reversed(data.shape))
			assert dims[slice_dir]==1
			del dims[slice_dir]
			while len(dims)>2 and dims[-1]==1: dims=dims[0:-1] # remove right `1`
			data=data.reshape(list(reversed(dims))) 
    
		H=db.getQueryCurrentResolution(query)
		msec=int(1000*(time.time()-t1))
		logger.info(f"got data {I}/{N} timestep={timestep} field={field} H={H} data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box} m={np.min(data)} M={np.max(data)} ms={msec}")
		yield {"I":I,"N":N,"timestep":timestep,"field":field,"logic_box":logic_box, "H":H, "data":data,"msec":msec}
		I+=1
		db.nextBoxQuery(query)

	logger.info(f"read done")


# ///////////////////////////////////////////////////////////////////
class Stats:
	
	# constructor
	def __init__(self):
		self.lock = threading.Lock()
		self.num_running=0
		
	# isRunning
	def isRunning(self):
		with self.lock:
			return self.num_running>0

	# startCollecting
	def startCollecting(self):
		with self.lock:
			self.num_running+=1
			if self.num_running>1: return
		self.t1=time.time()
		ReadStats()
			
	# stopCollecting
	def stopCollecting(self):
		with self.lock:
			self.num_running-=1
			if self.num_running>0: return
		self.printStatistics()

	# printStatistics
	def printStatistics(self):
		sec=time.time()-self.t1
		stats=ReadStats()
		logger.info(f"Stats::printStatistics enlapsed={sec} seconds" )
		try: # division by zero
			for k,v in stats.items():
				logger.info(f"   {k}  r={HumanSize(v['r'])} r_sec={HumanSize(v['r']/sec)}/sec w={HumanSize(v['w'])} w_sec={HumanSize(v['w']/sec)}/sec n={v.n:,} n_sec={int(v/sec):,}/sec")
		except:
			pass

# /////////////////////////////////////////////////////////////////////////////////////////////////
class QueryNode:

	# shared by all instances (and must remain this way!)
	stats=Stats()

	# constructor
	def __init__(self):
		self.iqueue=queue.Queue()
		self.oqueue=queue.Queue()
		self.wait_for_oqueue=False

	# disableOutputQueue
	def disableOutputQueue(self):
		self.oqueue=None

	# startThread
	def startThread(self):
		self.thread = threading.Thread(target=lambda: self._threadLoop())
		self.thread.start()   

	# stopThread
	def stopThread(self):
		self.iqueue.join()
		self.iqueue.put((None,None))
		self.thread.join()
		self.thread=None   

	# waitIdle
	def waitIdle(self):
		self.iqueue.join()

	# pushJob
	def pushJob(self, db, **kwargs):
		self.iqueue.put([db,kwargs])

	# popResult
	def popResult(self, last_only=True):
		assert self.oqueue is not None
		ret=None
		while not self.oqueue.empty():
			ret=self.oqueue.get()
			self.oqueue.task_done()
			if not last_only: break
		return ret
  
	# _threadLoop
	def _threadLoop(self):

		while True:
			db, kwargs=self.iqueue.get()

			# need to exit
			if db is None: 
				return 

			# collect statistics
			self.stats.startCollecting() 
			
			for result in ExecuteBoxQuery(db, **kwargs):
       
				if result is None: 
					break 

				# push the result to the output quue
				if self.oqueue:
					self.oqueue.put(result)
					if self.wait_for_oqueue:
						self.oqueue.join()

			# let the main task know I am done
			self.iqueue.task_done()
			self.stats.stopCollecting() 

