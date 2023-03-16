
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
	def createBoxQuery(self, *args,**kwargs):

		query=super().createBoxQuery(*args,**kwargs)
		
		if query is None:
			return None

		query.inner  = self.inner.createBoxQuery(
			ov.BoxNi(ov.PointNi(query.logic_box[0]), ov.PointNi(query.logic_box[1])), 
			self.inner.getField(query.field), 
			query.timestep, 
			ord('r'), 
			query.aborted.inner)

		if not query.inner:
			return None

		for H in query.end_resolutions:
			query.inner.end_resolutions.push_back(H)

		return query

	# begin
	def beginBoxQuery(self,query):
		if query is None: return
		super().beginBoxQuery(query)
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
		return super().executeBoxQuery(access,query,data)

	# nextBoxQuery
	def nextBoxQuery(self,query):
		if not self.isQueryRunning(query): return
		self.inner.nextBoxQuery(query.inner)
		super().nextBoxQuery(query)

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


	
	