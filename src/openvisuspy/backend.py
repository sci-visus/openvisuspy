import os,copy,math,time,logging,types
import os,sys,time,threading,queue,math, types,logging,copy
import numpy as np
from . utils import IsIterable,Clamp, HumanSize

logger = logging.getLogger(__name__)

VISUS_BACKEND=os.environ.get("VISUS_BACKEND","cpp").lower()
print(f"VISUS_BACKEND={VISUS_BACKEND}")

# //////////////////////////////////////////////////////////////////////////
class BaseDataset:

	# getAlignedBox
	def getAlignedBox(self, logic_box, H, slice_dir:int=None):
		ret=copy.deepcopy(logic_box)
		pdim=self.getPointDim()
		maxh=self.getMaxResolution()
		bitmask=self.getBitmask()
		delta=[1,1,1]
		for B in range(maxh,H,-1):
			bit=ord(bitmask[B])-ord('0')
			A,B,D=ret[0][bit], ret[1][bit], delta[bit]
			D*=2
			A=int(math.floor(A/D))*D
			B=int(math.ceil (B/D))*D
			B=max(A+D,B)
			ret[0][bit] = A 
			ret[1][bit] = B
			delta[bit] = D
		
		#  force to be a slice?
		if pdim==3 and slice_dir is not None:
			offset=ret[0][slice_dir]
			ret[1][slice_dir]=offset+0
			ret[1][slice_dir]=offset+1
			delta[slice_dir]=1
		
		num_pixels=[(ret[1][I]-ret[0][I])//delta[I] for I in range(pdim)]
		return ret, delta,num_pixels

	# createBoxQuery
	def createBoxQuery(self,
		timestep=None, 
		field=None, 
		logic_box=None,
		max_pixels=None, 
		endh=None, 
		num_refinements=1, 
		aborted=None
	):

		pdim=self.getPointDim()
		assert pdim==2 or pdim==3 # todo other cases?

		maxh=self.getMaxResolution()
		bitmask=self.getBitmask()
		dims=self.getLogicSize()

		if timestep is None:
			timestep=self.getTimestep()

		if field is None:
			field=self.getField()

		if logic_box is None:
			logic_box=self.getLogicBox()

		if endh is None:
			endh=maxh

		if aborted is None:
			aborted=Aborted()

		logger.info(f"begin timestep={timestep} field={field} logic_box={logic_box} num_refinements={num_refinements} max_pixels={max_pixels} endh={endh}")

		if IsIterable(max_pixels):
			max_pixels=int(np.prod(max_pixels,dtype=np.int64))
		
		# if box is not specified get the all box
		if logic_box is None:
			W,H,D=[int(it) for it in self.getLogicSize()]
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
				aligned_box,delta,num_pixels=self.getAlignedBox(original_box,H, slice_dir=slice_dir)
				tot_pixels=np.prod(num_pixels,dtype=np.int64)
				if tot_pixels<=max_pixels*1.10:
					endh=H
					logger.info(f"Guess resolution H={H} original_box={original_box} aligned_box={aligned_box} delta={delta} num_pixels={repr(num_pixels)} tot_pixels={tot_pixels:,} max_pixels={max_pixels:,} end={endh}")
					logic_box=aligned_box
					break

		# this is the query I need
		logic_box,delta,num_pixels=self.getAlignedBox(logic_box, endh, slice_dir=slice_dir)

		logic_box=[
			[int(it) for it in logic_box[0]],
			[int(it) for it in logic_box[1]]
		]

		query=types.SimpleNamespace()
		query.logic_box=logic_box
		query.timestep=timestep
		query.field=field
		query.end_resolutions=list(reversed([endh-pdim*I for I in range(num_refinements) if endh-pdim*I>=0]))
		query.slice_dir=slice_dir
		query.aborted=aborted
		query.t1=time.time()
		query.cursor=0
		return query

	# beginBoxQuery
	def beginBoxQuery(self,query):
		logger.info(f"beginBoxQuery timestep={query.timestep} field={query.field} logic_box={query.logic_box} end_resolutions={query.end_resolutions}")	
		query.cursor=0	

	# isQueryRunning (if cursor==0 , means I have to begin, if cursor==1 means I have the first level ready etc)
	def isQueryRunning(self,query):
		return query is not None and query.cursor>=0 and query.cursor<len(query.end_resolutions)
		
	 # getQueryCurrentResolution
	def getQueryCurrentResolution(self,query):
		if query is None: return -1
		last=query.cursor-1
		return query.end_resolutions[last]  if last>=0 and last<len(query.end_resolutions) else -1

	# projectDataIfNeeded
	def executeBoxQuery(self,access, query, data):
		
		if query is None or data is None:
			logger.info(f"read done")
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
		logger.info(f"got data {query.cursor}/{query.end_resolutions} timestep={query.timestep} field={query.field} H={H} data.shape={data.shape} data.dtype={data.dtype} logic_box={query.logic_box} m={np.min(data)} M={np.max(data)} ms={msec}")
		
		N=len(query.end_resolutions)

		return {
			"I": query.cursor,
			"N": len(query.end_resolutions),
			"timestep": query.timestep,
			"field": query.field, 
			"logic_box": query.logic_box, 
			"H": H, 
			"data": data,
			"msec": msec
			}

	# nextBoxQuery
	def nextBoxQuery(self,query):
		if not self.isQueryRunning(query): return
		query.cursor+=1

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
		yield result
		db.nextBoxQuery(query)

# //////////////////////////////////////////////////
if VISUS_BACKEND=="cpp":
	from . backend_cpp import *

elif VISUS_BACKEND == 'py':
    from . backend_py import *

else:
	raise Exception("internal error, unsupported ")




