import os,sys,copy,math,time,logging,types,requests,zlib,xmltodict,urllib,queue,types,threading
import numpy as np

import requests
import re
from urllib.parse import urlparse, urlunparse

import OpenVisus as ov

from . utils import *
logger = logging.getLogger(__name__)


# ///////////////////////////////////////////////////////////////////
class Aborted:
	
	# constructor
	def __init__(self,value=False):
		self.ov_aborted=ov.Aborted()
		if value: self.ov_aborted.setTrue()

	# setTrue
	def setTrue(self):
		self.ov_aborted.setTrue()

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
		self.T1=time.time()
		self.readStats()
			
	# stopCollecting
	def stopCollecting(self):
		with self.lock:
			self.num_running-=1
			if self.num_running>0: return
		self.printStatistics()

	# printStatistics
	def printStatistics(self):
		sec=max(time.time()-self.T1,1e-8)
		stats=self.readStats()
		logger.info(f"Stats::printStatistics enlapsed={sec} seconds" )
		for k,v in stats.items():
			w,r,n=v['w'],v['r'],v['n']
			logger.info(" ".join([f"  {k:4}",
						f"r={HumanSize(r)} r_sec={HumanSize(r/sec)}/sec",
						f"w={HumanSize(w)} w_sec={HumanSize(w/sec)}/se ",
						f"n={n:,} n_sec={int(n/sec):,}/sec"]))



# /////////////////////////////////////////////////////////////////////////////////////////////////
class BaseDataset(object):

	# shared by all instances (and must remain this way!)
	stats=Stats()

	# constructor
	def __init__(self,url):
		self.url=url
		self.iqueue=queue.Queue()
		self.oqueue=queue.Queue()
		self.wait_for_oqueue=False
		self.thread=None

	# getUrl
	def getUrl(self):
		return self.url      

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

		T1=None
		while True:

			if T1 is None or (time.time()-T1)>5.0:
				logger.info("_threadLoop is Alive")
				T1=time.time()

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
					if not self.aborted == is_aborted:
						logger.error(f"# ***************** db.executeBoxQuery failed {traceback.format_exc()}")
					break

				if result is None: 
					break
				
				if self.aborted == is_aborted:
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
class OpenVisusDataset(BaseDataset):

	# constructor
	def __init__(self,url):
		super().__init__(url)

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

		self.db=ov.LoadDataset(url)


	# getPointDim
	def getPointDim(self):
		return self.db.getPointDim()

	# getLogicBox
	def getLogicBox(self):
		return self.db.getLogicBox()

	# getMaxResolution
	def getMaxResolution(self):
		return self.db.getMaxResolution()

	# getBitmask
	def getBitmask(self):
		return self.db.getBitmask().toString()

	# getLogicSize
	def getLogicSize(self):
		return self.db.getLogicSize()
	
	# getTimesteps
	def getTimesteps(self):
		return self.db.getTimesteps() 

	# getTimestep
	def getTimestep(self):
		return self.db.getTime()

	# getFields
	def getFields(self):
		return self.db.getFields()

	# createAccess
	def createAccess(self):
		return self.db.createAccess()

	# getField
	def getField(self,field:str=None):
		return self.db.getField() if field is None else self.db.getField(field)

	# getFieldRange
	def getFieldRange(self,field:str=None):
		field = self.db.getField(field)
		return [field.getDTypeRange().From, field.getDTypeRange().To]

	# getDatasetBody
	def getDatasetBody(self):
		return self.db.getDatasetBody()

	# getPhysicBox
	def getPhysicBox(self):
		pdim=self.getPointDim()
		ret = self.db.db.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
		ret = [(float(ret[I]), float(ret[I + 1])) for I in range(0, pdim * 2, 2)]
		return ret

	# getAxis
	def getAxis(self):
		ret = self.db.db.idxfile.axis.strip().split()
		ret = {it: I for I, it in enumerate(ret)} if ret else  {'X':0,'Y':1,'Z':2}
		return ret

	# createBoxQuery
	def createBoxQuery(self, 		
		timestep=None, 
		field:str=None, 
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
			field=self.getField().name

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

		self.t1=time.time()
		self.cursor=0
		self.slice_dir=slice_dir
		self.aborted=aborted
		
		query  = self.db.createBoxQuery(
			ov.BoxNi(ov.PointNi(logic_box[0]), ov.PointNi(logic_box[1])), 
			self.db.getField(field), 
			timestep, 
			ord('r'), 
			aborted.ov_aborted)

		if not query:
			return None

		# important
		query.enableFilters()

		for H in end_resolutions:
			query.end_resolutions.push_back(H)

		return query

	# beginBoxQuery
	def beginBoxQuery(self,query):
		if query is None: return
		logic_box=BoxToPyList(query.logic_box)
		logger.info(f"beginBoxQuery timestep={query.time} field={query.field.name} logic_box={logic_box} end_resolutions={[I for I in query.end_resolutions]}")	
		self.cursor=0	
		self.db.beginBoxQuery(query)

	# isRunning
	def isQueryRunning(self,query):
		if query is None: return False
		return query.isRunning() 

	# getCurrentResolution
	def getCurrentResolution(self, query):
		return query.getCurrentResolution() if self.isQueryRunning(query) else -1

	# executeBoxQuery
	def executeBoxQuery(self,access, query):
		assert self.isQueryRunning(query)
		if not self.db.executeBoxQuery(access, query):
			return None
		data=ov.Array.toNumPy(query.buffer, bShareMem=False)

		if data is None:
			logger.info(f"read done {query} {data}")
			return None

		"""
		# is a slice? I need to reduce the size (i.e. from 3d data to 2d data)
		slice_dir=self.slice_dir
		if slice_dir is not None:
			dims=list(reversed(data.shape))
			assert dims[slice_dir]==1
			del dims[slice_dir] 
			while len(dims)>2 and dims[-1]==1: dims=dims[0:-1]  #remove right `1`
			data=data.reshape(list(reversed(dims))) # not worked for 2D color_image
		"""
		# worked for 2D and 3D data with single channel and color 
		data= data.reshape([IT for IT in data.shape if IT > 1])


		logic_box=BoxToPyList(query.logic_box)
		H=self.getCurrentResolution(query)
		msec=int(1000*(time.time()-self.t1))
		logger.info(f"got data cursor={self.cursor} end_resolutions{[I for I in query.end_resolutions]} timestep={query.time} field={query.field.name} H={H} data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box} m={np.min(data)} M={np.max(data)} ms={msec}")

		return {
			"I": self.cursor,
			"timestep": query.time,
			"field": query.field, 
			"logic_box": logic_box,
			"H": H, 
			"data": data,
			"msec": msec,
			}

	# nextBoxQuery
	def nextBoxQuery(self,query):
		if not self.isQueryRunning(query): return
		self.db.nextBoxQuery(query)
		if not self.isQueryRunning(query): return
		self.cursor+=1


# /////////////////////////////////////////////////////////////////////////////////////////////////
class PelicanFed:

	def __init__(self, url):
		self.DiscoveryEndpoint = None
		self.DirectorEndpoint = None
		self.RegistryEndpoint = None
		self.JwksUri = None
		self.BrokerEndpoint = None

		parsed_url = urlparse(url)
		self.DiscoveryEndpoint = f"https://{parsed_url.netloc}"
		config_url = f"https://{parsed_url.netloc}/.well-known/pelican-configuration"
		response = requests.get(config_url)

		if response.status_code == 200:
			config = response.json()
			self.DirectorEndpoint = config.get("director_endpoint")
			self.RegistryEndpoint = config.get("namespace_registration_endpoint")
			self.JwksUri = config.get("jwks_uri")
			self.BrokerEndpoint = config.get("broker_endpoint")

# //////////////////////////////////////////////////////////////////////////
class PelicanDataset(OpenVisusDataset):

	def __init__(self,url):
		# "osdf://" is a shortcut for "pelican://osg-htc.org" that's recognized by most Pelican clients.
		# To comply with proper URL formatting, we technically want "osdf://" + /<namespace>, e.g. "osdf:///nsdf"
		# (notice triple /) because the URL doesn't have a real hostname (which would be between the second/third
		# slashes). However, most people struggle with the triple slash because it's not intuitive, so we handle
		# both cases.
		url = re.sub(r"^osdf:///*", "pelican://osg-htc.org/", url)

		parsed_url = urlparse(url)
		self.pelican_fed = PelicanFed(url)

		# The Pelican v7.8 Director has this baked in, but for now we need to hardcode the api endpoints
		if 'directread' in parsed_url.query:
			director_query = f"{self.pelican_fed.DirectorEndpoint}/api/v1.0/director/origin/{urlunparse(('', '') + parsed_url[2:])}"
		else:
			director_query = f"{self.pelican_fed.DirectorEndpoint}{urlunparse(('', '') + parsed_url[2:])}"

		# Use the discovered endpoints to query the director. In particular, we expect our data
		# to be accessible at the URL encoded in the Link header.
		director_resp = requests.get(director_query, allow_redirects=False)
		data_url = director_resp.headers["Location"]

		# Finally, pass what we've constructed to the OpenVisusDataset constructor
		super().__init__(data_url)

# //////////////////////////////////////////////////////////////////////////
def GuessBitmask(N):
		ret="V"
		while N>1: 
			ret,N=ret+"0", (N>>1)
		logger.info(f"bitmask={ret}")
		return ret

# ////////////////////////////////////////////////////////////////////
def ReplaceExtWith(filename, suffix):
	return os.path.splitext(filename)[0]+suffix

# ////////////////////////////////////////////////////////////////////
class Signal1DDataset(BaseDataset):

	# constructor
	def __init__(self,url):
		super().__init__(url)
		assert(".npz" in url or ".npy" in url)
		self.cursor=-1
		filename=DownloadFile(url)
		logger.info(f"url={url} filename={filename}")

		if ".npz" in filename:
			signal=np.load(filename,mmap_mode="r")["data"]
		else:
			signal=np.load(filename,mmap_mode="r")

		info_filename=ReplaceExtWith(filename, ".json")

		# need to read all the array
		if not os.path.isfile(info_filename):
				SaveJSON(info_filename,{
					"bitmask": GuessBitmask(signal.shape[0]),
					"dtype": str(signal.dtype),
					"shape": signal.shape,
					"vmin": str(np.min(signal)), # Object of type int64 is not JSON serializable
					"vmax": str(np.max(signal))
				})
		
		info=LoadJSON(info_filename)
		self.bitmask=info["bitmask"]
		assert(info["dtype"]=="int64")
		self.dtype=signal.dtype
		# assert(info["shape"]==signal.shape)
		self.vmin=int(info["vmin"]) 
		self.vmax=int(info["vmax"])
		
		endh=len(self.bitmask)-1
		self.levels=[signal]
		logger.info(f"signal endh={endh} shape={signal.shape} dtype={signal.dtype}")
		
		# out of 4 samples I am keeping min,Max
		H=endh
		while self.levels[0].shape[0]>1024:
			H-=1

			# generate cache
			cached_filename=  ReplaceExtWith(filename, f".{H}.npy")
			if not os.path.isfile(cached_filename):
				cur=self.levels[0]
				filtered=np.copy(cur[::2])
				logger.info(f"Computing filter H={H} shape={filtered.shape} dtype={filtered.dtype} ")
				for I in range(0,4*(cur.shape[0]//4),4):
					v=list(cur[I:I+4])
					vmin,vmax=np.min(v),np.max(v)
					filtered[I//2+0:I//2+2]=[vmin,vmax] if v.index(vmin)<v.index(vmax) else [vmax,vmin]
				os.makedirs(os.path.dirname(cached_filename),exist_ok=True)
				np.save(cached_filename, filtered)
				logger.info(f"saved filtered cached_filename={cached_filename}")
			
			# load from cache
			filtered=np.load(cached_filename, mmap_mode="r") # all mem mapped
			self.levels=[filtered]+self.levels
				
		while len(self.levels)!=(endh+1):
			self.levels=[None]+self.levels

		logger.info("ComputeFilter done")

	# getPointDim
	def getPointDim(self):
		return 1

	# getLogicBox
	def getLogicBox(self):
		p1,p2=[0],[self.levels[-1].shape[0]]
		return [p1,p2]

	# getPhysicBox
	def getPhysicBox(self):
		return [[0,self.levels[-1].shape[0]]]

	# getMaxResolution
	def getMaxResolution(self):
		return len(self.bitmask)-1

	# getBitmask
	def getBitmask(self):
		return self.bitmask

	# getLogicSize
	def getLogicSize(self):
		N=1<<(len(self.bitmask)-1)
		return [N]
	
	# getTimesteps
	def getTimesteps(self):
		return [0]

	# getTimestep
	def getTimestep(self):
		return 0

	# getFields
	def getFields(self):
		return ["data"]

	# createAccess
	def createAccess(self):
		return True # no need for access

	# getField
	def getField(self,field:str=None):
		from types import SimpleNamespace
		field=SimpleNamespace()
		field.name="data"
		field.dtype=self.dtype
		return field

	# getFieldRange
	def getFieldRange(self,field:str=None):
		return [self.vmin,self.vmax]

	# getDatasetBody
	def getDatasetBody(self):
		return self.url

	# getAxis
	def getAxis(self):
		return {'X':0,'Y':1,'Z':2}

	# createBoxQuery
	def createBoxQuery(self, 		
		timestep=None, 
		field=None, 
		logic_box=None,
		max_pixels=None, 
		endh=None, 
		num_refinements=1, 
		aborted=None,
		full_dim=False
	):

		self.cursor=-1
		self.aborted=Aborted()	
		self.endh =self.getMaxResolution()
		self.x1=logic_box[0][0] # in pixel coordinates
		self.x2=logic_box[1][0]
		self.step=1
		self.num_pixels=(self.x2-self.x1)//self.step

		while True:
			logger.info(f"max_pixels={max_pixels} maxh={self.getMaxResolution()} endh={self.endh} level={self.levels[self.endh].shape} x1={self.x1} y2={self.x2} step={self.step} numpixels={self.num_pixels}")

			if self.endh<=1 or self.levels[self.endh-1] is None:
				break

			# user specified max num_pixels
			if max_pixels:
				assert(max_pixels and not endh)
				if self.num_pixels <= (1.2*max_pixels):
					break
			# user specified a specific curve
			else:
				assert(endh and not max_pixels)
				if self.endh==endh:
					break

			self.endh-=1
			self.step*=2
			self.x1=(self.x1//self.step)*self.step
			self.x2=(self.x2//self.step)*self.step
			self.num_pixels=(self.x2-self.x1)//self.step

		return True # no need to create a query

	# beginBoxQuery
	def beginBoxQuery(self,query):
		self.cursor=0

	# isQueryRunning
	def isQueryRunning(self,query):
		return self.cursor==0

	# getCurrentResolution
	def getCurrentResolution(self, query):
		return len(self.bitmask)-1 # always at full resolution

	# executeBoxQuery
	def executeBoxQuery(self,access, query):
		assert self.isQueryRunning(query)
		lvl=self.levels[self.endh]
		x1=int(self.x1//self.step)
		x2=int(self.x2//self.step)
		# logger.info(f"lvl shape={lvl.shape} dtype={lvl.dtype} x1={x1} x2={x2} step={self.step}")
		return {
			"I": self.cursor,
			"timestep": self.getTimestep(),
			"field": self.getField().name, 
			"logic_box": [[self.x1],[self.x2]],
			"H": self.endh, 
			"data": lvl[x1:x2],
			"msec": 0,
			}

	# nextBoxQuery
	def nextBoxQuery(self,query):
		self.cursor=-1


# ///////////////////////////////////////////////////////////////////
def LoadDataset(url):
	if ".npz" in url or ".npy" in url:
		return Signal1DDataset(url)

	elif (url.startswith("pelican://") or url.startswith("osdf://")):
		return PelicanDataset(url)
		
	else:
		return OpenVisusDataset(url)
	

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////
def ExecuteBoxQuery(db,*args,**kwargs):
	access=kwargs['access'];del kwargs['access']
	query=db.createBoxQuery(*args,**kwargs)
	I,N=0,len([I for I in query.end_resolutions])
	db.beginBoxQuery(query)
	while db.isQueryRunning(query):
		result=db.executeBoxQuery(access, query)
		if result is None: break
		db.nextBoxQuery(query)
		result["running"]=db.isQueryRunning(query)
		yield result