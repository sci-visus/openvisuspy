
import OpenVisus as ov
import types

from .backend import BaseDataset

# ///////////////////////////////////////////////////////////////////
class Aborted:
	
	# constructor
	def __init__(self,value=False):
		self.inner=ov.Aborted()
		if value: self.inner.setTrue()

	# setTrue
	def setTrue(self):
		self.inner.setTrue()

	# isTrue
	def isTrue(self):
		ABORTED=ov.Aborted()
		ABORTED.setTrue() 		
		return self.inner.__call__()==ABORTED.__call__()


# ///////////////////////////////////////////////////////////////////
class Dataset (BaseDataset):
	
	# coinstructor
	def __init__(self,url):
		self.url=url
		self.inner=ov.LoadDataset(url)
		
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

	# ///////////////////////////////////////////////////////////////////////////

	# createBoxQuery
	def createBoxQuery(self, timestep, field, logic_box, end_resolutions, aborted=None):
		query = self.inner.createBoxQuery(
			ov.BoxNi(ov.PointNi(logic_box[0]), ov.PointNi(logic_box[1])), 
			self.inner.getField(field), 
			timestep, 
			ord('r'), 
			aborted.inner if aborted is not None else ov.Aborted())

		if query:
			for H in end_resolutions:
				query.end_resolutions.push_back(H)		

		return query	 

	# begin
	def beginBoxQuery(self,query):
		if query is None: return
		self.inner.beginBoxQuery(query)

	# isRunning
	def isQueryRunning(self,query):
		return query.isRunning() if query is not None else False

	# getQueryCurrentResolution
	def getQueryCurrentResolution(self, query):
		if not self.isQueryRunning(query): return -1
		return query.getCurrentResolution() if query and query.isRunning() else -1

	# execute
	def executeBoxQuery(self,access, query):
		assert self.isQueryRunning(query)
		if not self.inner.executeBoxQuery(access, query):
			return None
		return ov.Array.toNumPy(query.buffer, bShareMem=False) 

	# next
	def nextBoxQuery(self,query):
		assert self.isQueryRunning(query)
		self.inner.nextBoxQuery(query)

# ///////////////////////////////////////////////////////////////////
def LoadDataset(url):
	return Dataset(url)


# ///////////////////////////////////////////////////////////////////
def ReadStats(reset=False):

	io =ov.File.global_stats()
	net=ov.NetService.global_stats()

	return {
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

	if reset:
		ov.File      .global_stats().resetStats()
		ov.NetService.global_stats().resetStats()


	
	