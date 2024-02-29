import os,sys,copy,math,time,logging,types,requests,zlib,xmltodict,urllib,queue,types,threading
import numpy as np

import OpenVisus as ov

from . utils import *
logger = logging.getLogger(__name__)


# ///////////////////////////////////////////////////////////////////
class Aborted:
	
	# constructor
	def __init__(self,value=False):
		self.inner=ov.Aborted()
		if value: self.inner.setTrue()

	# setTrue
	def setTrue(self):
		self.inner.setTrue()

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

	# readStats
	def readStats(self):

		io =ov.File.global_stats()
		net=ov.NetService.global_stats()

		ret= {
			"io": {
				"r":io.getReadBytes(),
				"w":io.getWriteBytes(),
				"n":io.getNumOpen(),
			},
			"net":{
				"r":net.getReadBytes(), 
				"w":net.getWriteBytes(),
				"n":net.getNumRequests(),
			}
		}

		ov.File      .global_stats().resetStats()
		ov.NetService.global_stats().resetStats()

		return ret
			

	# startCollecting
	def startCollecting(self):
		with self.lock:
			self.num_running+=1
			if self.num_running>1: return
		self.t1=time.time()
		self.readStats()
			
	# stopCollecting
	def stopCollecting(self):
		with self.lock:
			self.num_running-=1
			if self.num_running>0: return
		self.printStatistics()

	# printStatistics
	def printStatistics(self):
		sec=max(time.time()-self.t1,1e-8)
		stats=self.readStats()
		logger.info(f"Stats::printStatistics enlapsed={sec} seconds" )
		for k,v in stats.items():
			w,r,n=v['w'],v['r'],v['n']
			logger.info(" ".join([f"  {k:4}",
						f"r={HumanSize(r)} r_sec={HumanSize(r/sec)}/sec",
						f"w={HumanSize(w)} w_sec={HumanSize(w/sec)}/se ",
						f"n={n:,} n_sec={int(n/sec):,}/sec"]))




# /////////////////////////////////////////////////////////////////////////////////////////////////
class QueryNode:

	# shared by all instances (and must remain this way!)
	stats=Stats()

	# constructor
	def __init__(self):
		self.iqueue=queue.Queue()
		self.oqueue=queue.Queue()
		self.wait_for_oqueue=False
		self.thread=None

	# disableOutputQueue
	def disableOutputQueue(self):
		self.oqueue=None

	# start
	def start(self):
		# already running
		if not self.thread is None:
			return
		self.thread = threading.Thread(target=self._threadLoop,daemon=True)
		self.thread.start()

	# stop
	def stop(self):
		self.iqueue.join()
		self.iqueue.put((None,None))
		if self.thread is not None:
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

		logger.info("entering _threadLoop ...")

		is_aborted=ov.Aborted()
		is_aborted.setTrue()

		t1=None
		while True:

			if t1 is None or (time.time()-t1)>5.0:
				logger.info("_threadLoop is Alive")
				t1=time.time()

			db, kwargs=self.iqueue.get()
			if db is None: 
				logger.info("exiting _threadLoop...")
				return 
			
			self.stats.startCollecting() 

			access=kwargs['access'];del kwargs['access']
			query=db.createBoxQuery(**kwargs)
			db.beginBoxQuery(query)
			while db.isQueryRunning(query):
				try:
					result=db.executeBoxQuery(access, query)
				except:
					if not query.aborted == is_aborted:
						logger.error(f"# ***************** db.executeBoxQuery failed {traceback.format_exc()}")
					break

				if result is None: 
					break
				
				if query.aborted == is_aborted:
					break 

				
				db.nextBoxQuery(query)
				result["running"]=db.isQueryRunning(query)

				if self.oqueue:
					self.oqueue.put(result)
					if self.wait_for_oqueue:
						self.oqueue.join()
				
				time.sleep(0.01)

				# remove me
				# break

			logger.info("Query finished")
			self.iqueue.task_done()
			self.stats.stopCollecting()


# //////////////////////////////////////////////////////////////////////////
class Dataset:

	def __init__(self,url):
		self.url=url

		# handle security
		if all([
				url.startswith("http"),
				"mod_visus" in url,
			  "MODVISUS_USERNAME" in os.environ,
				"MODVISUS_PASSWORD" in os.environ,
				"~auth_username" not in url,
				"~auth_password" not in url,
		 	]) :

			url=url + f"&~auth_username={os.environ['MODVISUS_USERNAME']}&~auth_password={os.environ['MODVISUS_PASSWORD']}"

		self.inner=ov.LoadDataset(url)

	# getAlignedBox
	def getAlignedBox(self, logic_box, endh, slice_dir:int=None):
		p1,p2=copy.deepcopy(logic_box)
		pdim=self.getPointDim()
		maxh=self.getMaxResolution()
		bitmask=self.getBitmask()
		delta=[1,1,1]
		
		for K in range(maxh,endh,-1):
			bit=ord(bitmask[K])-ord('0')
			delta[bit]*=2

		for I in range(pdim):
			p1[I]=delta[I]*(p1[I]//delta[I])
			p2[I]=delta[I]*(p2[I]//delta[I])
			p2[I]=max(p1[I]+delta[I], p2[I])
		
		num_pixels=[(p2[I]-p1[I])//delta[I] for I in range(pdim)]


		#  force to be a slice?
		# REMOVE THIS!!!
		if pdim==3 and slice_dir is not None:
			offset=p1[slice_dir]
			p2[slice_dir]=offset+0
			p2[slice_dir]=offset+1
		
		# print(f"getAlignedBox logic_box={logic_box} endh={endh} slice_dir={slice_dir} (p1,p2)={(p1,p2)} delta={delta} num_pixels={num_pixels}")

		return (p1,p2), delta, num_pixels

	# getUrl
	def getUrl(self):
		return self.url       

	# getPointDim
	def getPointDim(self):
		return self.inner.getPointDim()

	# getLogicBox
	def getLogicBox(self):
		return self.inner.getLogicBox()

	# getMaxResolution
	def getMaxResolution(self):
		return self.inner.getMaxResolution()

	# getBitmask
	def getBitmask(self):
		return self.inner.getBitmask().toString()

	# getLogicSize
	def getLogicSize(self):
		return self.inner.getLogicSize()
	
	# getTimesteps
	def getTimesteps(self):
		return self.inner.getTimesteps() 

	# getTimestep
	def getTimestep(self):
		return self.inner.getTime()

	# getFields
	def getFields(self):
		return self.inner.getFields()

	# createAccess
	def createAccess(self):
		return self.inner.createAccess()

	# getField
	def getField(self,field=None):
		return self.inner.getField(field) if field is not None else self.inner.getField()

	# getDatasetBody
	def getDatasetBody(self):
		return self.inner.getDatasetBody()


	# returnBoxQueryData
	def returnBoxQueryData(self,access, query, data):
		
		if query is None or data is None:
			logger.info(f"read done {query} {data}")
			return None

		# is a slice? I need to reduce the size (i.e. from 3d data to 2d data)
		if query.slice_dir is not None:
			dims=list(reversed(data.shape))
			assert dims[query.slice_dir]==1
			del dims[query.slice_dir]
			while len(dims)>2 and dims[-1]==1: dims=dims[0:-1] # remove right `1`
			data=data.reshape(list(reversed(dims)))

		H=self.getQueryCurrentResolution(query)
		msec=int(1000*(time.time()-query.t1))
		logger.info(f"got data cursor={query.cursor} end_resolutions{query.end_resolutions} timestep={query.timestep} field={query.field} H={H} data.shape={data.shape} data.dtype={data.dtype} logic_box={query.logic_box} m={np.min(data)} M={np.max(data)} ms={msec}")

		return {
			"I": query.cursor,
			"timestep": query.timestep,
			"field": query.field, 
			"logic_box": query.logic_box,
			#"logic_box":  #BoxToPyList(query.inner.logic_samples.logic_box),
			#"logic_size": PointToPyList(query.inner.logic_samples.delta), 
			"H": H, 
			"data": data,
			"msec": msec,
			}

	# createBoxQuery
	def createBoxQuery(self, 		
		timestep=None, 
		field=None, 
		logic_box=None,
		max_pixels=None, 
		endh=None, 
		num_refinements=1, 
		aborted=None,
		full_dim=False):


		pdim=self.getPointDim()
		assert pdim in [1,2,3]

		maxh=self.getMaxResolution()
		bitmask=self.getBitmask()
		dims=self.getLogicSize()

		if timestep is None:
			timestep=self.getTimestep()

		if field is None:
			field=self.getField()

		if logic_box is None:
			logic_box=self.getLogicBox()

		if endh is None and not max_pixels:
			endh=maxh

		if aborted is None:
			aborted=Aborted()

		logger.info(f"begin timestep={timestep} field={field} logic_box={logic_box} num_refinements={num_refinements} max_pixels={max_pixels} endh={endh}")

		# if box is not specified get the all box
		if logic_box is None:
			W,H,D=[int(it) for it in self.getLogicSize()]
			logic_box=[[0,0,0],[W,H,D]]
		
		# crop logic box
		if True:
			p1,p2=list(logic_box[0]),list(logic_box[1])
			slice_dir=None
			for I in range(pdim):
				
				# *************** is a slice? *******************
				if not full_dim and  pdim==3 and (p2[I]-p1[I])==1:
					assert slice_dir is None 
					slice_dir=I
					p1[I]=Clamp(p1[I],0,dims[I])
					p2[I]=p1[I]+1
				else:
					p1[I]=Clamp(int(math.floor(p1[I])),     0,dims[I])
					p2[I]=Clamp(int(math.ceil (p2[I])) ,p1[I],dims[I])
				if not p1[I]<p2[I]:
					return None
			logic_box=(p1,p2)
		
		# is view dependent? if so guess max resolution and endh is IGNORED and overwritten 
		if max_pixels:

			if IsIterable(max_pixels):
				max_pixels=int(np.prod(max_pixels,dtype=np.int64))

			original_box=logic_box
			for __endh in range(maxh,0,-1):
				aligned_box, delta, num_pixels=self.getAlignedBox(original_box,__endh, slice_dir=slice_dir)
				tot_pixels=np.prod(num_pixels, dtype=np.int64)
				if tot_pixels<=max_pixels:
					endh=__endh
					logger.info(f"Guess resolution endh={endh} original_box={original_box} aligned_box={aligned_box} delta={delta} num_pixels={repr(num_pixels)} tot_pixels={tot_pixels:,} max_pixels={max_pixels:,} end={endh}")
					logic_box=aligned_box
					break
		else:
			original_box=logic_box
			aligned_box, delta, num_pixels=self.getAlignedBox(original_box,endh, slice_dir=slice_dir)

		# this is the query I need
		end_resolutions=list(reversed([endh-pdim*I for I in range(num_refinements) if endh-pdim*I>=0]))

		# scrgiorgio: end_resolutions[0] is wrong, I need to align to the finest resolution
		logic_box, delta, num_pixels=self.getAlignedBox(logic_box, end_resolutions[-1], slice_dir=slice_dir)

		logic_box=[
			[int(it) for it in logic_box[0]],
			[int(it) for it in logic_box[1]]
		]

		query=types.SimpleNamespace()
		query.logic_box=logic_box
		query.timestep=timestep
		query.field=field
		query.end_resolutions=end_resolutions
		query.slice_dir=slice_dir
		query.aborted=aborted
		query.t1=time.time()
		query.cursor=0
		
		query.inner  = self.inner.createBoxQuery(
			ov.BoxNi(ov.PointNi(query.logic_box[0]), ov.PointNi(query.logic_box[1])), 
			self.inner.getField(query.field), 
			query.timestep, 
			ord('r'), 
			query.aborted.inner)

		if not query.inner:
			return None

		# important
		query.inner.enableFilters()

		for H in query.end_resolutions:
			query.inner.end_resolutions.push_back(H)

		return query

	# beginBoxQuery
	def beginBoxQuery(self,query):
		if query is None: return
		logger.info(f"beginBoxQuery timestep={query.timestep} field={query.field} logic_box={query.logic_box} end_resolutions={query.end_resolutions}")	
		query.cursor=0	
		self.inner.beginBoxQuery(query.inner)

	# isRunning
	def isQueryRunning(self,query):
		if query is None: return False
		return query.inner.isRunning() 

	# getQueryCurrentResolution
	def getQueryCurrentResolution(self, query):
		return query.inner.getCurrentResolution() if self.isQueryRunning(query) else -1

	# executeBoxQuery
	def executeBoxQuery(self,access, query):
		assert self.isQueryRunning(query)
		if not self.inner.executeBoxQuery(access, query.inner):
			return None
		data=ov.Array.toNumPy(query.inner.buffer, bShareMem=False) 
		return self.returnBoxQueryData(access, query, data)

	# nextBoxQuery
	def nextBoxQuery(self,query):
		if not self.isQueryRunning(query): return
		self.inner.nextBoxQuery(query.inner)
		if not self.isQueryRunning(query): return
		query.cursor+=1



# ///////////////////////////////////////////////////////////////////
def LoadDataset(url):
	return Dataset(url)

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////
def ExecuteBoxQuery(db,*args,**kwargs):
	access=kwargs['access'];del kwargs['access']
	query=db.createBoxQuery(*args,**kwargs)
	t1=time.time()
	I,N=0,len(query.end_resolutions)
	db.beginBoxQuery(query)
	while db.isQueryRunning(query):
		result=db.executeBoxQuery(access, query)
		if result is None: break
		db.nextBoxQuery(query)
		result["running"]=db.isQueryRunning(query)
		yield result