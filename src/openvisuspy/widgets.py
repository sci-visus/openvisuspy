import os,sys,logging,types,time,copy
from typing import Any
import colorcet
from requests.auth import HTTPBasicAuth
import requests

from . utils import *
from . backend import LoadDataset
import bokeh

from bokeh.models import Select,LinearColorMapper,LogColorMapper,ColorBar,Button,Slider,TextInput,Row,Column,Div
import os,sys,base64,json
from bokeh.models import TabPanel,Tabs, Button,Column, Div
from bokeh.models.callbacks import CustomJS
from bokeh.models import NumeralTickFormatter ,LinearColorMapper, ColorBar, BasicTicker, ColumnDataSource
from bokeh.models import LogColorMapper, LogTicker, ColorBar

logger = logging.getLogger(__name__)

PALETTES=[
	"Greys256", 
	"Inferno256", 
	"Magma256", 
	"Plasma256", 
	"Viridis256", 
	"Cividis256", 
	"Turbo256"
	] + [
		it  for it in [
		'colorcet.blueternary', 
		'colorcet.coolwarm', 
		'colorcet.cyclicgrey', 
		'colorcet.depth', 
		'colorcet.divbjy', 
		'colorcet.fire', 
		'colorcet.geographic', 
		'colorcet.geographic2', 
		'colorcet.gouldian', 
		'colorcet.gray', 
		'colorcet.greenternary', 
		'colorcet.grey', 
		'colorcet.heat', 
		'colorcet.phase2', 
		'colorcet.phase4', 
		'colorcet.rainbow', 
		'colorcet.rainbow2', 
		'colorcet.rainbow3', 
		'colorcet.rainbow4', 
		'colorcet.redternary', 
		'colorcet.reducedgrey', 
		'colorcet.yellowheat']
		if hasattr(colorcet,it[9:])
	]  

# //////////////////////////////////////////////////////////////////////////////////////
def cdouble(value):
	try:
		return float(value)
	except:
		return 0.0



# //////////////////////////////////////////////////////////////////////////////////////
class Widgets:

	ID=0

	# constructor
	def __init__(self,doc=None, is_panel=False, parent=None):

		if doc is None and not is_panel:
			import bokeh.io
			doc=bokeh.io.curdoc()

		assert(not isinstance(doc,list))

		self.is_panel=is_panel
		self.doc=doc
		self.parent=parent

		self.id=f"{type(self).__name__}/{Widgets.ID}"
		Widgets.ID+=1
		self.config=None
		self.db=None
		self.access=None
		self.current_dataset=None
		self.render_id=None # by default I am not rendering
		self.logic_to_physic=[(0.0,1.0)]*3
		self.children=[]
  
		self.first_row_layout=Row(sizing_mode="stretch_width")

		self.widgets=types.SimpleNamespace()

		# datasets
		self.widgets.datasets = Select(title="Dataset", options=[],width=60) 
		self.widgets.datasets.on_change("value",lambda attr,old,new: self.setDataset(new)) 
 
		# palette
		self.palette='Viridis256'
		self.widgets.palette = Select(title='Palette', options=PALETTES,value=self.palette)
		self.widgets.palette.on_change("value",lambda attr, old, new: self.setPalette(new))  

		# palette range
		self.metadata_palette_range=[0.0,255.0]
		self.widgets.palette_range_mode = Select(title="range",options=["metadata","user","dynamic","dynamic-acc"], value="metadata",width=80)
		self.widgets.palette_range_vmin = TextInput(title="vmin" ,width=80)
		self.widgets.palette_range_vmax = TextInput(title="vmax" ,width=80)

		self.widgets.palette_range_mode.on_change("value",lambda attr, old, new: self.setPaletteRangeMode(new))
		self.widgets.palette_range_vmin.on_change("value",lambda attr, old, new: self.onPaletteRangeChange())
		self.widgets.palette_range_vmax.on_change("value",lambda attr, old, new: self.onPaletteRangeChange())

		# color_bar
		self.color_bar = ColorBar(ticker=BasicTicker(desired_num_ticks=10))
		self.color_bar.color_mapper=LinearColorMapper() 
		self.color_bar.color_mapper.palette=self.palette
		self.color_bar.color_mapper.low, self.color_bar.color_mapper.high  = self.getPaletteRange()

		# color_mapper type
		self.widgets.colormapper_type=Select(title='colormap',  options=["linear","log"],value='3')
		self.widgets.colormapper_type.on_change("value",lambda attr, old, new: self.setColorMapperType(new)) 

		def PatchSlider(slider):
			slider._check_missing_dimension=None # patch EQUAL_SLIDER_START_END)
			return slider
  
		# num_views
		self.widgets.num_views=Select(title='#Views',  options=["1","2","3","4"],value='1')
		self.widgets.num_views.on_change("value",lambda attr, old, new: self.setNumberOfViews(int(new))) 
 
		# timestep
		self.widgets.timestep = PatchSlider(Slider(title='Time', value=0, start=0, end=1, sizing_mode='stretch_width'))

		def onTimestepChange(attr, old, new):
			if old==new: return
			logger.info("onTimestepChange old={old} new={new}")
			self.setTimestep(int(new))

		self.widgets.timestep.on_change("value",onTimestepChange)

		# timestep delta
		speed_options=["1x","2x","4x","8x","16x","32x","64x","128x"]
		self.widgets.timestep_delta=Select(title="Speed",options=speed_options, value=speed_options[0],width=100)
		self.widgets.timestep_delta.on_change("value", lambda attr, old, new: self.setTimestepDelta(self.speedFromOption(new)))   

		# field
		self.widgets.field = Select(title='Field',  options=[],value='data')
		self.widgets.field.on_change("value",lambda attr, old, new: self.setField(new))  
  
		# direction 
		self.widgets.direction = Select(title='Direction', options=[('0','X'), ('1','Y'), ('2','Z')],value='2')
		self.widgets.direction.on_change ("value",lambda attr, old, new: self.setDirection(int(new)))  
  
		# offset 
		self.widgets.offset = PatchSlider(Slider(title='Offset', value=0, start=0, end=1024, sizing_mode='stretch_width'))

		def onOffsetChange(attr, old, new):
			if old==new: return
			logging.info(f"\n\n\n\n\n[{self.id}] on_change calling setOffset({new})")
			self.setOffset(new)

		self.widgets.offset.on_change ("value",onOffsetChange)
  
		# num_refimements (0==guess)
		self.widgets.num_refinements=PatchSlider(Slider(title='#Ref', value=0, start=0, end=4))
		self.widgets.num_refinements.on_change("value",lambda attr, old, new: self.setNumberOfRefinements(int(new)))
		self.widgets.num_refinements._check_missing_dimension=None # patch
  
		# quality (0==full quality, -1==decreased quality by half-pixels, +1==increase quality by doubling pixels etc)
		self.widgets.quality = PatchSlider(Slider(title='Quality', value=0, start=-12, end=+12))
		self.widgets.quality.on_change("value",lambda attr, old, new: self.setQuality(int(new)))  
		self.widgets.quality._check_missing_dimension=None # patch

		# viewdep
		self.widgets.viewdep = Select(title="View Dep",options=[('1','Enabled'),('0','Disabled')], value="True",width=100)
		self.widgets.viewdep.on_change("value",lambda attr, old, new: self.setViewDependent(int(new)))  
  
		# status_bar
		self.widgets.status_bar= {}
		self.widgets.status_bar["request" ]=TextInput(title="" ,sizing_mode='stretch_width')
		self.widgets.status_bar["response"]=TextInput(title="" ,sizing_mode='stretch_width')
		self.widgets.status_bar["request" ].disabled=True
		self.widgets.status_bar["response"].disabled=True
  
 		# play time
		self.play=types.SimpleNamespace()
		self.play.is_playing=False
		self.widgets.play_button = Button(label="Play",width=80,sizing_mode='stretch_height')
		self.widgets.play_button.on_click(self.togglePlay)
		self.widgets.play_sec = Select(title="Frame delay",options=["0.00","0.01","0.1","0.2","0.1","1","2"], value="0.01",width=120)

		# metadata
		self.widgets.metadata=Column(width=640,sizing_mode='stretch_both')
		self.widgets.metadata.visible=False

		self.widgets.show_metadata=Button(label="Metadata",width=80,sizing_mode='stretch_height')
		self.widgets.show_metadata.on_click(self.onShowMetadataClick)

		self.panel_layout=None
		self.idle_callback=None

	# onShowMetadataClick
	def onShowMetadataClick(self):
		self.widgets.metadata.visible=not self.widgets.metadata.visible

	# start
	def start(self):
		for it in self.children:
			it.start()	

	# stop
	def stop(self):
		logger.info(f"[{self.id}]:: stop ")
		for it in self.children:
			it.stop()		

	# onIdle
	async def onIdle(self):

		self.playNextIfNeeded()

		if self.panel_layout:
			import panel as pn
			pn.io.push_notebook(self.panel_layout)

		for it in self.children:
			await it.onIdle()


	# setWidgetsDisabled
	def setWidgetsDisabled(self,value):
		self.widgets.datasets.disabled=value
		self.widgets.palette.disabled=value
		self.widgets.num_views.disabled=value
		self.widgets.timestep.disabled=value
		self.widgets.timestep_delta.disabled=value
		self.widgets.field.disabled=value
		self.widgets.direction.disabled=value
		self.widgets.offset.disabled=value
		self.widgets.num_refinements.disabled=value
		self.widgets.quality.disabled=value
		self.widgets.viewdep.disabled=value
		self.widgets.status_bar["request" ].disabled=value
		self.widgets.status_bar["response"].disabled=value
		self.widgets.play_button.disabled=value
		self.widgets.play_sec.disabled=value
 		
		for it in self.children:
			it.setWidgetsDisabled(value)  

	# refresh (to override if needed)
	def refresh(self):
		for it in self.children:
			it.refresh()
   
	# getPointDim
	def getPointDim(self):
		return self.db.getPointDim() if self.db else 2

	# gotoPoint
	def gotoPoint(self, p):
		for it in self.children:
			it.gotoPoint(p) 
  
	# getConfig
	def getConfig(self):
		return self.config

	# setConfig
	def setConfig(self,value):
		if value is None: return
		logger.info(f"[{self.id}]::setConfig")
		self.config=value
		self.datasets={it["name"] : it for it in value["datasets"]}
		ordered_names=[it["name"] for it in value["datasets"]]
		self.widgets.datasets.options=ordered_names
		for it in self.children:
			it.setConfig(value)
		self.setDataset(ordered_names[0])
  
	# getLogicToPhysic
	def getLogicToPhysic(self):
		return self.logic_to_physic

	# setLogicToPhysic
	def setLogicToPhysic(self,value):
		logger.info(f"[{self.id}]::setLogicToPhysic value={value}")
		self.logic_to_physic=value
		for it in self.children:
			it.setLogicToPhysic(value)
		self.refresh()
  
	# getPhysicBox
	def getPhysicBox(self):
		dims=self.db.getLogicSize()
		vt=[it[0] for it in self.logic_to_physic]
		vs=[it[1] for it in self.logic_to_physic]
		return [[
			      0*vs[I] + vt[I], 
			dims[I]*vs[I] + vt[I]
			] for I in range(len(dims))]

		# pdim = self.db.getPointDim()
		# physic_box=self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
		# physic_box=[(float(physic_box[I]),float(physic_box[I+1])) for I in range(0,pdim*2,2)]
		# return physic_box

	# setPhysicBox
	def setPhysicBox(self, value):
		dims=self.db.getLogicSize()
		def LinearMapping(a,b, A,B):
			vs=(B-A)/(b-a)
			vt=A-a*vs
			return vt,vs
		T=[LinearMapping(0,dims[I], *value[I]) for I in range(len(dims))]
		self.setLogicToPhysic(T)

	# setDataset
	def setDataset(self, name, db=None, force=False):

		# it's an url
		if not self.config:
			url=name
			ext=os.path.splitext(url)[1]

			# json file 
			if ext==".json":
				if url.startswith("http"):
					username=os.environ.get("MODVISUS_USERNAME","")
					password=os.environ.get("MODVISUS_PASSWORD","")
					if username and password:
						auth=HTTPBasicAuth(username,password) if username else None
					else:
						auth=None
					response = requests.get(url,auth = auth)
					config=response.json()
				else:
					config=json.load(open(url,"r"))
				return self.setConfig(config)
			else:
				# it's a url for a single dataset: create a minimal config
				return self.setConfig({"datasets" : [{"name": url, "url": url }]})
		
		# rehentrant call
		if not force and self.current_dataset and self.current_dataset["name"]==name:
			return 

		logger.info(f"[{self.id}]::setDataset name={name}")

		config=self.datasets[name]
		self.current_dataset=config
		self.widgets.datasets.value=name

		if db is None:
			url=config["url"]
			self.db=LoadDataset(url=url)
		else:
			self.db=db

		self.access=self.db.createAccess()
  
		# avoid reloading db multiple times by specifying db
		for it in self.children:
			it.setDataset(name, db=self.db) 

		pdim = self.db.getPointDim()

		# timestep
		timesteps =self.db.getTimesteps()
		timestep_delta=int(config.get("timestep-delta",1))
		timestep=int(config.get("timestep",timesteps[0]))
		self.setTimesteps(timesteps)
		self.setTimestepDelta(timestep_delta)
		self.setTimestep(timestep)
  
		# axis
		axis=self.db.inner.idxfile.axis.strip().split()
		if not axis: 
			axis=["X","Y","Z"][0:pdim]
		axis=[(str(I),name) for I,name in enumerate(axis)]
		self.setDirections(axis)

		# physic box
		physic_box=self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
		physic_box=[(float(physic_box[I]),float(physic_box[I+1])) for I in range(0,pdim*2,2)]
		self.setPhysicBox(physic_box)

		# field
		fields =self.db.getFields()
		default_fieldname=self.db.getField().name
		fieldname=config.get("field",default_fieldname)
		field=self.db.getField(fieldname)
		self.setFields(fields)
		self.setField(field.name) 
  
		# direction
		self.setDirection(2)
		for I,it in enumerate(self.children):
			it.setDirection((I % 3) if pdim==3 else 2)

		# palette 
		palette=config.get("palette","Viridis256")
		palette_range=config.get("palette-range",None)
		dtype_range=field.getDTypeRange()
		self.setPalette(palette)
		vmin,vmax=dtype_range.From,dtype_range.To
		self.setMetadataPaletteRange([vmin,vmax])
		if palette_range is None:
			self.setPaletteRange([vmin,vmax])
			self.setPaletteRangeMode("dynamic")
		else:
			self.setPaletteRange(*palette_range)
			self.setPaletteRangeMode("user")

		# color mapper
		color_mapper_type=config.get("color-mapper-type","linear")
		self.setColorMapperType(color_mapper_type)

		# view dependent
		view_dep=bool(config.get('view-dep',True))
		self.setViewDependent(view_dep) 

		# quality (>0 higher quality, <0 lower uality)
		quality=int(config.get("quality",0))
		self.setQuality(quality)

		# num_refinements
		num_refinements=int(config.get("num-refinements",2))
		self.setNumberOfRefinements(num_refinements)

		# metadata
		metadata=config.get("metadata",None)
		if metadata:
			tabs=[]
			for T,item in enumerate(metadata):
					
					type=item["type"]
					filename=item["filename"]

					if type=="b64encode":
						# binary encoded in string
						base64_s=item["encoded"]

						try:
							body_s=base64.b64decode(base64_s).decode("utf-8")
						except:
							body_s="" # it's probably full binary
					else:
						# json
						body_s=json.dumps(item,indent=2)
						base64_s = base64.b64encode(bytes(body_s, 'utf-8')).decode('utf-8') 

					base64_s= 'data:application/octet-stream;base64,' + base64_s

					# download button
					download_button=Button(label="download")
					download_button.js_on_click(CustomJS(args=dict(base64_s=base64_s,filename=filename), code="""
						fetch(base64_s, {cache: "no-store"}).then(response => response.blob())
						    .then(blob => {
						        if (navigator.msSaveBlob) {
						            navigator.msSaveBlob(blob, filename);
						        }
						        else {
						            const link = document.createElement('a')
						            link.href = URL.createObjectURL(blob)
						            link.download = filename
						            link.target = '_blank'
						            link.style.visibility = 'hidden'
						            link.dispatchEvent(new MouseEvent('click'))
						        }
						        return response.text();
						    });
						"""))
					
					panel=TabPanel(child=Column(
						Div(text=f"<b><pre><code>{filename}</code></pre></b>"),
						download_button,
						Div(text=f"<div><pre><code>{body_s}</code></pre></div>"), 
						),
						title=f"{T}")
					
					tabs.append(panel)

			self.widgets.metadata.children=[Tabs(tabs=tabs)]

		self.refresh() 
  
	# getNumberOfViews
	def getNumberOfViews(self):
		return int(self.widgets.num_views.value)

	# setNumberOfViews
	def setNumberOfViews(self,value):
		logger.info(f"[{self.id}]::setNumberOfViews value={value}")
		self.widgets.num_views.value=str(value)

	# getTimesteps
	def getTimesteps(self):
		try:
			return [int(value) for value in self.db.db.getTimesteps().asVector()]
		except:
			return []

	# setTimesteps
	def setTimesteps(self,value):
		logger.info(f"[{self.id}]::setTimesteps start={value[0]} end={value[-1]}")
		self.widgets.timestep.start =  value[0]
		self.widgets.timestep.end   =  value[-1]
		self.widgets.timestep.step  = 1

	# speedFromOption
	def speedFromOption(self,option):
		return (int(option[:-1]))

	# optionFromSpeed
	def optionFromSpeed(self,speed):
		return (str(speed)+"x")

	# getTimestepDelta
	def getTimestepDelta(self):
		return self.speedFromOption(self.widgets.timestep_delta.value)

	# setTimestepDelta
	def setTimestepDelta(self,value):
		logger.info(f"[{self.id}]::setTimestepDelta value={value}")
		self.widgets.timestep_delta.value=self.optionFromSpeed (value)
		self.widgets.timestep.step=value
		A=self.widgets.timestep.start
		B=self.widgets.timestep.end
		T=self.getTimestep()
		T=A+value*int((T-A)/value)
		T=min(B,max(A,T))
		self.setTimestep(T)
  
		for it in self.children:
			it.setTimestepDelta(value)  
  
		self.refresh()

	# getTimestep
	def getTimestep(self):	
		return int(self.widgets.timestep.value)

	# setTimestep
	def setTimestep(self, value):
		logger.info(f"[{self.id}]::setTimestep value={value} A")
		self.widgets.timestep.value=value
		logger.info(f"[{self.id}]::setTimestep value={value} B")
		for it in self.children:
			it.setTimestep(value)  
		self.refresh()
  
	# getFields
	def getFields(self):
		return self.widgets.field.options 
  
	# setFields
	def setFields(self, value):
		logger.info(f"[{self.id}]::setFields value={value}")
		self.widgets.field.options =list(value)

	# getField
	def getField(self):
		return str(self.widgets.field.value)

	# setField
	def setField(self,value):
		logger.info(f"[{self.id}]::setField value={value}")
		if value is None: return
		self.widgets.field.value=value
		for it in self.children:
			it.setField(value)  
		self.refresh()

	# getPalette
	def getPalette(self):
		return self.palette

	# setPalette
	def setPalette(self, value):	 
		logger.info(f"[{self.id}]::setPalette value={value}")
		self.palette=value
		self.widgets.palette.value=value
		self.color_bar.color_mapper.palette=getattr(colorcet,value[len("colorcet."):]) if value.startswith("colorcet.") else value
		for it in self.children:
			it.setPalette(value)  
		self.refresh()

	# getMetadataPaletteRange
	def getMetadataPaletteRange(self):
		return self.metadata_palette_range
	
	# setMetadataPaletteRange
	def setMetadataPaletteRange(self,value):
		vmin,vmax=value
		self.metadata_palette_range=[vmin,vmax]
		for it in self.children:
			it.setMetadataPaletteRange(value)

	# getPaletteRangeMode
	def getPaletteRangeMode(self):
		return self.widgets.palette_range_mode.value
	
	# setPaletteRangeMode
	def setPaletteRangeMode(self,mode):
		logger.info(f"[{self.id}]::setPaletteRangeMode mode={mode} ")
		self.widgets.palette_range_mode.value=mode

		wmin=self.widgets.palette_range_vmin
		wmax=self.widgets.palette_range_vmax

		if mode=="metadata":
				wmin.value = str(self.metadata_palette_range[0])
				wmax.value = str(self.metadata_palette_range[1])

		if mode=="dynamic-acc":
			wmin.value=str(float('+inf'))
			wmax.value=str(float('-inf'))

		wmin.disabled=False if mode=="user" else True
		wmax.disabled=False if mode=="user" else True
			
		for it in self.children:
			it.setPaletteRangeMode(mode)
		self.refresh()

	# getPaletteRange
	def getPaletteRange(self):
		return [
			cdouble(self.widgets.palette_range_vmin.value),
			cdouble(self.widgets.palette_range_vmax.value),
		]

	# setPaletteRange (backward compatible)
	def setPaletteRange(self,value):
		vmin,vmax=value
		self.widgets.palette_range_vmin.value=str(vmin)
		self.widgets.palette_range_vmax.value=str(vmax)
		for it in self.children:
			it.setPaletteRange(value)
		self.refresh()

	# onPaletteRangeChange
	def onPaletteRangeChange(self):
		if self.getPaletteRangeMode()=="user": 
			vmin,vmax=self.getPaletteRange()
			self.setPaletteRange([vmin, vmax])

	# getColorMapperType
	def getColorMapperType(self):
		return "log" if isinstance(self.color_bar.color_mapper,LogColorMapper) else "linear"

	# getColorMapperType
	def setColorMapperType(self,value):
		logger.info(f"[{self.id}]::setColorMapperType value={value}")
		palette=self.getPalette()
		vmin,vmax=self.getPaletteRange()
		self.widgets.colormapper_type.value=value
		assert value=="linear" or value=="log"

		if value=="log":
			self.color_bar.color_mapper = LogColorMapper(palette=palette, low =max(0.01,vmin), high=max(0.01,vmax)) 
			
			self.color_bar.ticker=LogTicker()
		else:
			self.color_bar.color_mapper = LinearColorMapper(palette=palette, low =vmin, high=vmax)
			self.color_bar.ticker=BasicTicker(desired_num_ticks=10)

		for it in self.children:
			it.setColorMapperType(value)  
		self.refresh()


	# getNumberOfRefinements
	def getNumberOfRefinements(self):
		return self.widgets.num_refinements.value

	# setNumberOfRefinements
	def setNumberOfRefinements(self,value):
		logger.info(f"[{self.id}]::setNumberOfRefinements value={value}")
		self.widgets.num_refinements.value=value
		for it in self.children:
			it.setNumberOfRefinements(value)
		self.refresh()

	# getQuality
	def getQuality(self):
		return self.widgets.quality.value

	# setQuality
	def setQuality(self,value):
		logger.info(f"[{self.id}]::setQuality value={value}")
		self.widgets.quality.value=value
		for it in self.children:
			it.setQuality(value) 
		self.refresh()

	# getViewDepedent
	def getViewDepedent(self):
		return cbool(self.widgets.viewdep.value)

	# setViewDependent
	def setViewDependent(self,value):
		logger.info(f"[{self.id}]::setViewDependent value={value}")
		self.widgets.viewdep.value=str(int(value))
		for it in self.children:
			it.setViewDependent(value)     
		self.refresh()

	# getDirections
	def getDirections(self):
		return self.widgets.direction.options

	# setDirections
	def setDirections(self,value):
		logger.info(f"[{self.id}]::setDirections value={value}")
		self.widgets.direction.options=value
		for it in self.children:
			it.setDirections(value)

	# getDirection
	def getDirection(self):
		return int(self.widgets.direction.value)

	# setDirection
	def setDirection(self,value):
		logger.info(f"[{self.id}]::setDirection value={value}")
		pdim=self.getPointDim()
		if pdim==2: value=2
		dims=[int(it) for it in self.db.getLogicSize()]
		self.widgets.direction.value = str(value)

		# default behaviour is to guess the offset
		self.guessOffset()

		for it in self.children:
			it.setDirection(value)
   
		self.refresh()

	# getLogicAxis (depending on the projection XY is the slice plane Z is the orthogoal direction)
	def getLogicAxis(self):
		dir=self.getDirection()
		dirs=self.getDirections()
		titles=[it[1] for it in dirs]
		# print(dir,dirs,titles)

		# this is the projected slice
		XY=[int(it[0]) for it in dirs]

		if len(XY)==3:
			del XY[dir]
		else:
			assert(len(XY)==2)
		X,Y=XY

		# this is the cross dimension
		Z=2
		if len(dirs)==3:
			Z=int(dirs[dir][0])
			
		return (X,Y,Z),(titles[X],titles[Y],titles[Z] if len(titles)==3 else 'Z')

	# getOffsetStartEnd
	def getOffsetStartEnd(self):
		return self.widgets.offset.start, self.widgets.offset.end,self.widgets.offset.step

	# setOffsetStartEnd
	def setOffsetStartEndStep(self, value):
		A,B,step=value
		logger.info(f"[{self.id}]::setOffsetStartEndStep value={value}")
		self.widgets.offset.start, self.widgets.offset.end,self.widgets.offset.step=A,B,step
		for it in self.children:
			it.setOffsetStartEndStep(value)

	# getOffset (in physic domain)
	def getOffset(self):
		return self.widgets.offset.value

	# setOffset (3d only) (in physic domain)
	def setOffset(self,value):
		logger.info(f"[{self.id}]::setOffset new-value={value} old-value={self.getOffset()} A")

		self.widgets.offset.value=value
		assert(self.widgets.offset.value==value)
		logger.info(f"[{self.id}]::setOffset value={value} B")
		for it in self.children:
			logging.info(f"[{self.id}] recursively calling setOffset({value}) for children={it.id}")
			it.setOffset(value) 
		self.refresh()
  
	# guessOffset
	def guessOffset(self):
		
		pdim=self.getPointDim()
		dir=self.getDirection()

		# 2d there is no direction 
		if pdim==2:
			assert dir==2
			value=0
			logging.info(f"[{self.id}]::guessOffset pdim==2calling setOffset({value})")
			self.setOffsetStartEndStep([0,0,1]) # both extrema included
			self.setOffset(value)
		else:
			vt=[self.logic_to_physic[I][0] for I in range(pdim)]
			vs=[self.logic_to_physic[I][1] for I in range(pdim)]

			if all([it==0 for it in vt]) and all([it==1.0 for it in vs]):
				dims=[int(it) for it in self.db.getLogicSize()]
				value=dims[dir]//2
				logging.info(f"[{self.id}]::guessOffset CASE pdim==3 calling integer setOffset({value})")
				self.setOffsetStartEndStep([0,int(dims[dir])-1,1])
				self.setOffset(value)
			else:
				A,B=self.getPhysicBox()[dir]
				value=(A+B)/2.0				
				logging.info(f"[{self.id}]::guessOffset pdim==3 calling float setOffset({value})")

				self.setOffsetStartEndStep([A,B,1e-6])
				self.setOffset(value)


	# toPhysic
	def toPhysic(self,value):

		# is a box
		if hasattr(value[0],"__iter__"):
			p1,p2=[self.toPhysic(p) for p in value]
			return [p1,p2]

		pdim=self.getPointDim()
		dir=self.getDirection()
		assert(pdim==len(value))

		vt=[self.logic_to_physic[I][0] for I in range(pdim)]
		vs=[self.logic_to_physic[I][1] for I in range(pdim)]

		# apply scaling and translating
		ret=[vs[I]*value[I] + vt[I] for I in range(pdim)]

		if pdim==3: del ret[dir] # project

		assert(len(ret)==2)
		return ret

	# toLogic
	def toLogic(self,value):
		assert(len(value)==2)
		pdim=self.getPointDim() 
		dir=self.getDirection()

		# is a box?
		if hasattr(value[0],"__iter__"):
			p1,p2=[self.toLogic(p) for p in value]
			if pdim==3: 
				p2[dir]+=1 # make full dimensional
			return [p1,p2]

		ret=list(value)

		# unproject
		if pdim==3:
			ret.insert(dir, 0)

		assert(len(ret)==pdim)
		
		vt=[self.logic_to_physic[I][0] for I in range(pdim)]
		vs=[self.logic_to_physic[I][1] for I in range(pdim)]

		# scaling/translatation
		try:
			ret=[(ret[I]-vt[I])/vs[I] for I in range(pdim)]
		except Exception as ex:
			logger.info(f"Exception {ex} with logic_to_physic={self.logic_to_physic}",self.logic_to_physic)
			raise

		# unproject
		
		if pdim==3:
			offset=self.getOffset() # this is in physic coordinates
			ret[dir]=int((offset-vt[dir])/vs[dir])

		assert(len(ret)==pdim)
		return ret

	# togglePlay
	def togglePlay(self,evt=None):
		if self.play.is_playing:
			self.stopPlay()  
		else:
			self.startPlay()
			
	# startPlay
	def startPlay(self):
		logger.info(f"[{self.id}]::startPlay")
		self.play.is_playing=True
		self.play.t1=time.time()
		self.play.wait_render_id=None
		self.play.num_refinements=self.getNumberOfRefinements()
		self.setNumberOfRefinements(1)
		self.setWidgetsDisabled(True)
		self.widgets.play_button.disabled=False
		self.widgets.play_button.label="Stop"
	
	# stopPlay
	def stopPlay(self):
		logger.info(f"[{self.id}]::stopPlay")
		self.play.is_playing=False
		self.play.wait_render_id=None
		self.setNumberOfRefinements(self.play.num_refinements)
		self.setWidgetsDisabled(False)
		self.widgets.play_button.disabled=False
		self.widgets.play_button.label="Play"
  
	# playNextIfNeeded
	def playNextIfNeeded(self):
	 
		if not self.play.is_playing: 
			return

		# avoid playing too fast by waiting a minimum amount of time
		t2=time.time()
		if (t2-self.play.t1)<float(self.widgets.play_sec.value):
			return   

		render_id = [self.render_id] + [it.render_id for it in self.children]

		if self.play.wait_render_id is not None:
			if any([a<b for (a,b) in zip(render_id,self.play.wait_render_id) if a is not None and b is not None]):
				# logger.info(f"Waiting render {render_id} {self.play.wait_render_id}")
				return

		# advance
		T=self.getTimestep()+self.getTimestepDelta()

		# reached the end -> go to the beginning?
		if T>=self.widgets.timestep.end: 
			T=self.timesteps.widgets.timestep.start
   
		logger.info(f"[{self.id}]::playing timestep={T}")
		
		# I will wait for the resolution to be displayed
		self.play.wait_render_id=[(it+1) if it is not None else None for it in render_id]
		self.play.t1=time.time()
		self.setTimestep(T) 
