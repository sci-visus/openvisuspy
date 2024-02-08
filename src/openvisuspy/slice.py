import base64
import types
import logging
import copy
import traceback
import io 
import threading
import time
from urllib.parse import urlparse, urlencode

import numpy as np

from .utils   import *
from .backend import Aborted,LoadDataset,ExecuteBoxQuery,QueryNode
from .widgets import *
from .widgets import Canvas as Canvas

logger = logging.getLogger(__name__)


DEFAULT_SHOW_OPTIONS=[
	[
		"menu", 
		"view_mode",
		"scene", 
		"timestep",
		"timestep_delta",		
		"field",
		"palette", 
		"color_mapper_type", 
		"resolution", 
		"view_dep", 
		"num_refinements"
		],
		[
			"scene", 
			"direction", 
			"offset", 
			"color_mapper_type", 
			"range_mode", 
			"range_min",  
			"range_max"
		]
]

# ////////////////////////////////////////////////////////////////////////////////////
class Slice:

	ID = 0
	epsilon = 0.001
	start_resolution = 20

	# constructor
	def __init__(self, parent=None):

		self.on_change_callbacks={}

		self.parent = parent
		self.num_hold=0
		if self.parent:  
			self.id=self.parent.id + "."  + str(Slice.ID)
		else:
			self.id="/" + str(Slice.ID)
		Slice.ID += 1
		
		self.db = None
		self.access = None
		self.render_id = 0 
		self.slices = []
		self.linked = False

		self.logic_to_physic        = parent.logic_to_physic        if parent else [(0.0, 1.0)] * 3
		self.metadata_range         = parent.metadata_range         if parent else [0.0, 255.0]

		self.dialogs={}
		self.dialogs_placeholder=Column(height=0, width=0)

		self.createGui()
		logger.info(f"Created Slice id={self.id} parent={self.parent}")

	# onViewModeChange
	def onViewModeChange(self,value):
		body=self.getSceneBody()
		self.setViewMode(value)
		self.setSceneBody(body)

	# createGui
	def createGui(self):

		self.widgets = types.SimpleNamespace()

		self.widgets.copy_url = Widgets.Input(visible=False)

		self.widgets.menu = Widgets.MenuButton(name='File', 
																				 items=[['Load/Save']*2, ['Show Metadata']*2, ['Copy Url']*2, None, ['Logout']*2 ], 
																				 button_type='primary',
																				 callback={'Load/Save':self.showLoadSave, 'Show Metadata': self.showMetadata, 'Copy Url': self.copyUrl}, 
																				 jsargs={"copy_url": self.widgets.copy_url},
																				 jscallback="""function myFunction(){ if (menu.value=="Logout") {logout_url=window.location.href + "/logout";window.location=logout_url;console.log("logout_url=" + logout_url);}   if (menu.value=="Copy Url") {navigator.clipboard.writeText(copy_url.value);console.log("copy_url.value=" + copy_url.value);}   } setTimeout(myFunction, 300);""")


		self.widgets.menu=Column(
			pn.Spacer(height=18),
			self.widgets.menu, width=120)

		self.widgets.view_mode             = Widgets.Select   (name="view Mode", value="1",options=["1", "2", "probe", "2-linked", "4", "4-linked"],width=80, callback=self.onViewModeChange)
		self.widgets.scene                 = Widgets.Select   (name="Scene", options={}, width=180, callback=lambda body: self.setSceneBody(body))
		self.widgets.timestep              = Widgets.Slider   (name="Time", type="float", value=0, start=0, end=1, step=1.0, editable=True, callback=self.setTimestep,  sizing_mode="stretch_width")
		self.widgets.timestep_delta        = Widgets.Select   (name="Speed", options=["1x", "2x", "4x", "8x", "16x", "32x", "64x", "128x"], value="1x", width=60, callback=lambda new_value: self.setTimestepDelta(self.speedFromOption(new_value)))
		self.widgets.field                 = Widgets.Select   (name='Field', options=[], value='data', callback=self.setField, width=80)

		self.widgets.palette               = Widgets.ColorMap (name="Palette", options=GetPalettes(), value_name=DEFAULT_PALETTE, ncols=5, callback=self.setPalette,  width=220)
		self.widgets.range_mode            = Widgets.Select   (name="Range", options=["metadata", "user", "dynamic", "dynamic-acc"], value="dynamic-acc", width=120,callback=self.setRangeMode)
		self.widgets.range_min             = Widgets.Input    (name="Min", type="float", callback=lambda new_value: self.setRangeMin(new_value) if self.getRangeMode() == "user" else None,width=80)
		self.widgets.range_max             = Widgets.Input    (name="Max", type="float", callback=lambda new_value: self.setRangeMax(new_value) if self.getRangeMode() == "user" else None,width=80)
		self.widgets.color_mapper_type     = Widgets.Select   (name="Mapper", options=["linear", "log", ], callback=self.setColorMapperType,width=80)
		
		self.widgets.resolution            = Widgets.Slider   (name='Res', type="int", value=21, start=self.start_resolution, editable=False, end=99, callback=self.setResolution,  sizing_mode="stretch_width")
		self.widgets.view_dep              = Widgets.Select   (name="ViewDep",options={"Yes":True,"No":False}, value=True,width=80, callback=lambda new_value: self.setViewDependent(new_value))
		self.widgets.num_refinements       = Widgets.Slider   (name='#Ref', type="int", value=0, start=0, end=4, editable=False, width=80, callback=self.setNumberOfRefinements)

		self.widgets.direction             = Widgets.Select   (name='Direction', options={'X':0, 'Y':1, 'Z':2}, value=2, width=80, callback=lambda new_value: self.setDirection(new_value))
		self.widgets.offset                = Widgets.Slider   (name="Offset", type="float", start=0.0, end=1024.0, step=1.0, value=0.0, editable=True,  sizing_mode="stretch_width", callback=self.setOffset)
		
		# status_bar
		self.widgets.status_bar = {}
		self.widgets.status_bar["request" ] = Widgets.Input(name="", type="text", sizing_mode='stretch_width', disabled=False)
		self.widgets.status_bar["response"] = Widgets.Input(name="", type="text", sizing_mode='stretch_width', disabled=False)

		self.widgets.scene_body=Widgets.TextAreaInput(
			name='Current',
			sizing_mode="stretch_width",
			height=520,
			stylesheets=["""
				.bk-input {
					background-color: rgb(48, 48, 64);
					color: white;
					font-size: medium;
				}
				"""])

		
		# play time
		self.play = types.SimpleNamespace()
		self.play.is_playing = False
		self.widgets.play_button            = Widgets.Button(name="Play", width=8, callback=self.togglePlay)
		self.widgets.play_sec               = Widgets.Select(name="Frame delay", options=["0.00", "0.01", "0.1", "0.2", "0.1", "1", "2"], value="0.01")

		self.idle_callback = None
		self.color_bar     = None
		self.query_node    = None
		self.canvas        = None

		if self.parent:
			self.t1=time.time()
			self.aborted       = Aborted()
			self.new_job       = False
			self.current_img   = None
			self.last_query_logic_box = NotImplemented	
			self.last_job_pushed =time.time()
			self.query_node=QueryNode()
			self.canvas = Canvas(self.id)

			# redirecting resize events
			self.canvas.on_resize=self.onCanvasResize

		# placeholder
		self.main_layout=Column(sizing_mode='stretch_both')

	# copyUrl
	def copyUrl(self, evt=None):
		self.widgets.copy_url.value=self.getSceneUrl()
		ShowInfoNotification('Copy url done')

	# getSceneUrl
	def getSceneUrl(self):
		body=self.getSceneBody()
		load_s=base64.b64encode(json.dumps(body).encode('utf-8')).decode('ascii')
		current_url=GetCurrentUrl()
		o=urlparse(current_url)
		return o.scheme + "://" + o.netloc + o.path + '?' + urlencode({'load': load_s})		

	# onCanvasResize
	def onCanvasResize(self):
		if not self.db: return
		logger.info(f"id={self.id} width={self.canvas.getWidth()} height={self.canvas.getWidth()}")
		dir,offset=self.getDirection(),self.getOffset()
		self.setDirection(dir)
		self.setOffset(offset)

	# stop
	def stop(self):
		for it in [self] + self.slices:
			if it.query_node:
				it.aborted.setTrue()
				it.query_node.stop()

	# start
	def start(self):

		for it in [self] + self.slices:
			if it.query_node:
				it.query_node.start()

		if not self.parent and not self.idle_callback:

			def onIdleHandleExceptions():
				try:
					self.onIdle()
				except Exception as ex:
					logger.info(f"ERROR {ex}\n{traceback.format_exc()}\n\n\n\n\n\n") 
					raise 

			self.idle_callback = AddPeriodicCallback(onIdleHandleExceptions, 1000 // 30)

		self.refresh()

	# on_change
	def on_change(self, attr, callback):
		if not attr in self.on_change_callbacks:
			self.on_change_callbacks[attr]=[]
		self.on_change_callbacks[attr].append(callback)

	# triggerOnChange
	def triggerOnChange(self, attr, old,new_value):
		for fn in self.on_change_callbacks.get(attr,[]):
			fn(attr,old,new_value)

	# getMainLayout
	def getMainLayout(self):
		return self.main_layout

	# getViewMode
	def getViewMode(self):
		return self.widgets.view_mode.value

	# setViewMode
	def setViewMode(self, value):

		if self.parent:
			return

		logger.debug(f"id={self.id} START")

		scenes=self.getDatasets()

		show_probe ="probe"  in value
		show_linked="linked" in value
		nviews=1 if value=="probe" else int(value[0])

		self.stop()

		widget=self.widgets.view_mode
		with widget.disable_callbacks():
			widget.value=value

		self.main_layout[:]=[]
		for it in self.slices:  del it
		self.slices=[]

		self_show_options=DEFAULT_SHOW_OPTIONS

		# child show options
		for I in range(nviews):

			if nviews==1:
				slice_show_options=[it for it in self_show_options[1] if it not in self_show_options[0]]
			else:
				slice_show_options=self_show_options[1]

			slice = Slice(parent=self)
			slice.widgets.scene.name=f"{slice.widgets.scene.name}.{slice.id}"
			self.slices.append(slice)

			from .probe import ProbeTool
			slice.tool = ProbeTool(slice)
			slice.tool.main_layout.visible=show_probe
			slice.widgets.scene.options=scenes
			slice.linked=I==0 and show_linked

			slice.main_layout=Row(
				Column(
					Row(
						*[getattr(slice.widgets,it.replace("-","_")) for it in slice_show_options], # child
							sizing_mode="stretch_width"
						),
					Row(
						slice.canvas.main_layout, 
						sizing_mode='stretch_both'
					),
					Row(
						slice.widgets.status_bar["request"],
						slice.widgets.status_bar["response"], 
						sizing_mode='stretch_width'
					),
					sizing_mode="stretch_both"
				),
				slice.tool.main_layout,
				sizing_mode="stretch_both"
			)

		# create parent layout
		parent_first_row_widgets=[getattr(self.widgets, it.replace("-", "_")) for it in self_show_options[0]] + [self.widgets.copy_url]
		slices_main_layout=[it.main_layout for it in self.slices ]

		self.main_layout.append(
			Column(
				Row(*parent_first_row_widgets, sizing_mode="stretch_width"), 
				GridBox(*slices_main_layout, ncols=2 if nviews>=2 else 1, sizing_mode="stretch_both"),
				self.dialogs_placeholder,  
				sizing_mode='stretch_both'
			))

		self.start()

		
		logger.debug(f"id={self.id} END")

		 
	# getDefaultScene
	def getDefaultScene(self, name):
		return self.widgets.scene.options[name]

	# getDatasets
	def getDatasets(self):
		return self.widgets.scene.options

	# getLogicToPhysic
	def getLogicToPhysic(self):
		return self.logic_to_physic

	# setLogicToPhysic
	def setLogicToPhysic(self, value):
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			it.logic_to_physic = value
		self.refresh()

	# getPhysicBox
	def getPhysicBox(self):
		dims = self.db.getLogicSize()
		vt = [it[0] for it in self.logic_to_physic]
		vs = [it[1] for it in self.logic_to_physic]
		return [[
			0 * vs[I] + vt[I],
			dims[I] * vs[I] + vt[I]
		] for I in range(len(dims))]

	# setPhysicBox
	def setPhysicBox(self, value):
		dims = self.db.getLogicSize()
		def LinearMapping(a, b, A, B):
			vs = (B - A) / (b - a)
			vt = A - a * vs
			return vt, vs
		T = [LinearMapping(0, dims[I], *value[I]) for I in range(len(dims))]
		self.setLogicToPhysic(T)
		
	# getSceneBody
	def getSceneBody(self):

		ret={

			"view-mode": self.getViewMode(),
			"name": self.getScene(), 
			
			# NOT needed.. they should come automatically from the dataset?
			#   "timesteps": self.getTimesteps(),
			#   "physic_box": self.getPhysicBox(),
			#   "fields": self.getFields(),
			#   "directions" : self.getDirections(),

			"timestep-delta": self.getTimestepDelta(),
			"timestep": self.getTimestep(),
			"direction": self.getDirection(),
			"offset": self.getOffset(), 
			"field": self.getField(),
			"view-dep": self.isViewDependent(),
			"resolution": self.getResolution(),
			"num-refinements": self.getNumberOfRefinements(),
			"play-sec":self.getPlaySec(),
			"palette": self.getPalette(),
			# "metadata-range": self.getMetadataRange(),
			"color-mapper-type": self.getColorMapperType(),
			"range-mode": self.getRangeMode(),
		}

		if self.getRangeMode()=="user" :
			ret=ret.update({
				"range-min": self.getRangeMin(),
				"range-max": self.getRangeMax(),
			} )

		# query
		if self.canvas:
			(x1,x2),(y1,y2)=self.canvas.getViewport()
			ret.update({"x1":x1,"x2":x2,"y1":y1,"y2":y2})

		# children
		else:

			ret["children"]=[]
			for I,it in enumerate(self.slices):
				sub=it.getSceneBody()["scene"]

				# do not repeat same value in child since they will be inherited
				if self.getScene()==it.getScene():
					for k in copy.copy(sub):
						v=sub[k]
						if v==ret.get(k,None):
							del sub[k]
				else:
					"""otherwise to need to dump the full status since they are two different datasets"""
				
				ret["children"].append(sub)

		return {"scene" : ret}

	# hold
	def hold(self):
		self.num_hold=getattr(self,"num_hold",0) + 1
		# if self.num_hold==1: self.doc.hold()

	# unhold
	def unhold(self):
		self.num_hold-=1
		# if self.num_hold==0: self.doc.unhold()

	# load
	def load(self, value):

		if isinstance(value,str):
			ext=os.path.splitext(value)[1].split("?")[0]
			if ext==".json":
				value=LoadJSON(value)
			else:
				value={"scenes": [{"name": os.path.basename(value), "url":value}]}

		# from dictionary
		elif isinstance(value,dict):
			pass
		else:
			raise Exception(f"{value} not supported")

		assert(isinstance(value,dict))
		assert(len(value)==1)
		root=list(value.keys())[0]

		scenes={}
		for it in value[root]:
			scenes[it["name"]]={"scene": it} 

		for it in [self] + self.slices:
			widget=it.widgets.scene
			with widget.disable_callbacks():
				widget.options = scenes

		if scenes:
			self.setScene(list(scenes)[0])

	# setSceneBody
	def setSceneBody(self, scene):

		assert(isinstance(scene,dict))
		assert(len(scene)==1 and list(scene.keys())==["scene"])
		
		# go one level inside
		scene=scene["scene"]
 
		# self.stop()
		logger.info(f"id={self.id} START")

		name=scene.get("name")
		assert(name)

		default_scene=self.getDefaultScene(name)["scene"]
		url =default_scene["url"]
		urls=default_scene.get("urls",{})

		# viewmode is only a thingy for the parent
		if not self.parent:
			viewmode=scene.get("view-mode","1")
			if len(self.slices)==0 or viewmode!=self.getViewMode():
				self.setViewMode(viewmode)

		# special case, I want to force the dataset to be local (case when I have a local dashboards and remove dashboards)
		if "urls" in scene:

			if "--prefer" in sys.argv:
				prefer = sys.argv[sys.argv.index("--prefer") + 1]
				prefers = [it for it in urls if it['id']==prefer]
				if prefers:
					logger.info(f"id={self.id} Overriding url from {prefers[0]['url']} since selected from --select command line")
					url = prefers[0]['url']
					
			else:
				locals=[it for it in urls if it['id']=="local"]
				if locals and os.path.isfile(locals[0]["url"]):
					logger.info(f"id={self.id} Overriding url from {locals[0]['url']} since it exists and is a local path")
					url = locals[0]["url"]

		logger.info(f"id={self.id} LoadDataset url={url}...")
		db=LoadDataset(url=url) if not self.parent else self.parent.db

		for it in [self] + self.slices:
			it.db    =db
			it.access=db.createAccess()

			widget=it.widgets.scene
			with widget.disable_callbacks():
				widget.value=name

		timesteps=self.db.getTimesteps()
		self.setTimesteps(timesteps)

		fields=self.db.getFields()
		self.setFields(fields)

		pdim = self.getPointDim()

		if "logic-to-physic" in scene:
			logic_to_physic=scene["logic-to-physic"]
			self.setLogicToPhysic(logic_to_physic)
		else:
			physic_box = self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
			physic_box = [(float(physic_box[I]), float(physic_box[I + 1])) for I in range(0, pdim * 2, 2)]
			self.setPhysicBox(physic_box)

		if "directions" in scene:
			directions=scene["directions"]
			self.setDirections(directions)
		else:
			directions = self.db.inner.idxfile.axis.strip().split()
			directions = {it: I for I, it in enumerate(directions)} if directions else  {'X':0,'Y':1,'Z':2}
			self.setDirections(directions)

		timestep_delta = scene["timestep-delta"] = int(scene.get("timestep-delta", 1))
		self.setTimestepDelta(timestep_delta)

		timestep = scene["timestep"] = int(scene.get("timestep", self.db.getTimesteps()[0]))
		self.setTimestep(timestep)

		viewdep=scene['view-dep'] = bool(scene.get('view-dep', True))
		self.setViewDependent(viewdep)

		resolution=int(scene.get("resolution", -6))
		if resolution<0: resolution=self.db.getMaxResolution()+resolution
		scene['resolution'] = resolution
		self.setResolution(resolution)

		field=scene["field"] = scene.get("field", self.db.getField().name)
		self.setField(field)

		num_refinements=scene['num-refinements'] = int(scene.get("num-refinements", 2))
		self.setNumberOfRefinements(num_refinements)

		direction=scene['direction'] = int(scene.get("direction", 2))
		self.setDirection(direction)

		default_offset, offset_range=self.guessOffset(int(scene['direction']))
		offset=scene["offset"] = float(scene.get("offset",default_offset))
		self.setOffsetRange(offset_range) 
		self.setOffset(offset)	

		play_sec=scene["play-sec"]=float(scene.get("play-sec",0.01))
		self.setPlaySec(play_sec)

		field = self.db.getField(scene["field"])
		low, high = [field.getDTypeRange().From, field.getDTypeRange().To]

		palette=scene["palette"]=scene.get("palette",DEFAULT_PALETTE)
		self.setPalette(palette)

		palette_metadata_range=scene["metadata-range"]=scene.get("metadata-range",[low, high])
		self.setMetadataRange(palette_metadata_range)

		range_mode=scene["range-mode"]=scene.get("range-mode","dynamic-acc")
		self.setRangeMode(range_mode)

		if self.getRangeMode()=="user":
			range_min=scene["range-min"]=scene.get("range-min",low)
			self.setRangeMin(range_min)

			range_max=scene["range-max"]=scene.get("range-max",high)
			self.setRangeMax(range_max)

		color_mapper_type=scene["color-mapper-type"]=scene.get("color-mapper-type","linear")
		self.setColorMapperType(color_mapper_type)	

		x1,x2,y1,y2=[scene.get(it,None) for it in ("x1","x2","y1","y2")]

		if x1 is not None:
			self.setViewport((x1,x2),(y1,y2))

		# children
		children=scene.get("children",[]) 
		for S,it in enumerate(self.slices):
			child=copy.deepcopy(scene)
			child.update(children[S] if S<len(children) else {})
			if "children" in child: del child["children"] 
			self.slices[S].setSceneBody({"scene" : child})

		if not self.parent:
			self.start()
			self.triggerOnChange('scene', None, name)

		logger.info(f"id={self.id} END")

	# getScene
	def getScene(self):
		return self.widgets.scene.value

	# setScene
	def setScene(self, name):
		if not name: return
		body=self.getDefaultScene(name)
		self.setSceneBody(body)

	# onEvalClick
	def onEvalClick(self,evt=None):
		body=json.loads(self.widgets.scene_body.value)
		self.setSceneBody(body)
		ShowInfoNotification('Eval done')

	# onLoadClick
	def onLoadClick(self,value):
		body=value.decode('ascii')
		self.widgets.scene_body.value.value=body
		self.setSceneBody(json.loads(body))
		ShowInfoNotification('Load done')

	# onSaveClick
	def onSaveClick(self,evt=None):
		sio = io.StringIO(self.widgets.scene_body.value)
		sio.seek(0)
		ShowInfoNotification('Save done')
		return sio

	# showLoadSave
	def showLoadSave(self):

		eval_button = Widgets.Button(name="Eval", callback=self.onEvalClick,align='end')
		load_button = Widgets.FileInput(name="Load", description="Load", accept=".json", callback=self.onLoadClick)
		save_button=Widgets.FileDownload(label="Save", filename='scene.json', callback=self.onSaveClick)

		self.showDialog(
			Column(
				self.widgets.scene_body,
				Row(eval_button, save_button,load_button, align='end'),
				sizing_mode="stretch_both",align="end"
			), 
			height=700,
			name="Load/Save")

	# showMetadata
	def showMetadata(self):

		logger.debug(f"Show metadata")
		metadata=self.getDefaultScene(self.getScene())["scene"].get("metadata", [])

		cards=[]
		for I, item in enumerate(metadata):

			type = item["type"]
			filename = item.get("filename",f"metadata_{I:02d}.bin")

			if type == "b64encode":
				# binary encoded in string
				body = base64.b64decode(item["encoded"]).decode("utf-8")
				body = io.StringIO(body)
				body.seek(0)
				internal_panel=HTML(f"<div><pre><code>{body}</code></pre></div>",sizing_mode="stretch_width",height=400)
			elif type=="json-object":
				obj=item["object"]
				file = io.StringIO(json.dumps(obj))
				file.seek(0)
				internal_panel=JSON(obj,name="Object",depth=3, sizing_mode="stretch_width",height=400) 
			else:
				continue

			cards.append(Card(
					internal_panel,
					Widgets.FileDownload(file, embed=True, filename=filename,align="end"),
					title=filename,
					collapsed=(I>0),
					sizing_mode="stretch_width"
				)
			)

		self.showDialog(*cards, name="Metadata")

	# showDialog
	def showDialog(self, *args,**kwargs):
		name=kwargs["name"]

		if not "position" in kwargs:
			kwargs["position"]="center"

		if not "width" in kwargs:
			kwargs["width"]=1024

		if not "height" in kwargs:
			kwargs["height"]=600

		if not "contained" in kwargs:
			kwargs["contained"]=False

		self.dialogs[name]=FloatPanel(*args, **kwargs)
		self.dialogs_placeholder[:]=[v for k,v in self.dialogs.items()]

	# getTimesteps
	def getTimesteps(self):
		try:
			return [int(value) for value in self.db.db.getTimesteps().asVector()]
		except:
			return []

	# setTimesteps
	def setTimesteps(self, value):
		logger.debug(f"id={self.id} start={value[0]} end={value[-1]}")
		for it in [self] + self.slices:
			widget=it.widgets.timestep
			with widget.disable_callbacks():
				widget.start = value[0]
				widget.end   = value[-1]
				widget.step  = 1

	# speedFromOption
	def speedFromOption(self, option):
		return (int(option[:-1]))

	# optionFromSpeed
	def optionFromSpeed(self, speed):
		return (str(speed) + "x")

	# getPlaySec
	def getPlaySec(self):
		return self.widgets.play_sec.value

	# setPlaySec
	def setPlaySec(self,value):
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			widget=it.widgets.play_sec
			with widget.disable_callbacks():
				widget.value=value

	# getTimestepDelta
	def getTimestepDelta(self):
		return self.speedFromOption(self.widgets.timestep_delta.value)

	# setTimestepDelta
	def setTimestepDelta(self, value):
		logger.debug(f"id={self.id} value={value}")

		option=self.optionFromSpeed(value)

		A = self.widgets.timestep.start
		B = self.widgets.timestep.end
		T = self.getTimestep()
		T = A + value * int((T - A) / value)
		T = min(B, max(A, T))
		
		for it in [self] + self.slices:
			widget=it.widgets.timestep_delta
			with widget.disable_callbacks():
				widget.value = option

			widget=it.widgets.timestep
			with widget.disable_callbacks():
				widget.step = value

		self.setTimestep(T)

	# getTimestep
	def getTimestep(self):
		return int(self.widgets.timestep.value)

	# setTimestep
	def setTimestep(self, value):
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			widget=it.widgets.timestep
			with widget.disable_callbacks():
				widget.value = value

		self.refresh()

	# getFields
	def getFields(self):
		return self.widgets.field.options

	# setFields
	def setFields(self, value):
		value=list(value)
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			widget=it.widgets.field
			with widget.disable_callbacks():
				widget.options = value

	# getField
	def getField(self):
		return str(self.widgets.field.value)

	# setField
	def setField(self, value):
		logger.debug(f"id={self.id} value={value}")
		if value is None: return
		for it in [self] + self.slices:
			widget=it.widgets.field
			with widget.disable_callbacks():
				widget.value = value
		self.refresh()

	# getPalette
	def getPalette(self):
		return self.widgets.palette.value_name 

	# setPalette
	def setPalette(self, value):
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			widget=it.widgets.palette
			with widget.disable_callbacks():
				widget.value_name = value
				it.color_bar=None
		self.refresh()

	# getMetadataRange
	def getMetadataRange(self):
		return self.metadata_range

	# setMetadataRange
	def setMetadataRange(self, value):
		vmin, vmax = value
		for it in [self] + self.slices:
			it.metadata_range = [vmin, vmax]
			it.color_map=None
		self.refresh()

	# getRangeMode
	def getRangeMode(self):
		return self.widgets.range_mode.value

	# setRangeMode
	def setRangeMode(self, mode):
		logger.debug(f"id={self.id} mode={mode} ")

		for it in [self] + self.slices:
			
			widget=it.widgets.range_mode
			with widget.disable_callbacks():
				widget.value = mode
			
			it.color_map=None

			widget = it.widgets.range_min
			with widget.disable_callbacks():
				if mode == "metadata":   widget.value = it.metadata_range[0]
				if mode == "dynamic-acc":widget.value = 0.0
				widget.disabled = False if mode == "user" else True

			widget = it.widgets.range_max
			with widget.disable_callbacks():
				if mode == "metadata":   widget.value = it.metadata_range[1]
				if mode == "dynamic-acc":widget.value = 0.0
				widget.disabled = False if mode == "user" else True

		self.refresh()


	# getRangeMin
	def getRangeMin(self):
		return cdouble(self.widgets.range_min.value)

	# getRangeMax
	def getRangeMax(self):
		return cdouble(self.widgets.range_max.value)

	# setRangeMin
	def setRangeMin(self, value):
		for it in [self] + self.slices:
			widget=it.widgets.range_min
			with widget.disable_callbacks(): 
				widget.value = vmin
			it.color_map=None
		self.refresh()

	# setRangeMin
	def setRangeMax(self, value):
		for it in [self] + self.slices:
			widget=it.widgets.range_max
			with widget.disable_callbacks(): 
				widget.value = vmin
			it.color_map=None
		self.refresh()			



	# getColorMapperType
	def getColorMapperType(self):
		return self.widgets.color_mapper_type.value

	# setColorMapperType
	def setColorMapperType(self, value):
		logger.debug(f"id={self.id} value={value}")
		palette = self.getPalette()
		for it in [self] + self.slices:
			widget=it.widgets.color_mapper_type
			with widget.disable_callbacks():
				widget.value = value
			it.color_bar=None # force reneration of color_mapper
		self.start()

	# getNumberOfRefinements
	def getNumberOfRefinements(self):
		return self.widgets.num_refinements.value

	# setNumberOfRefinements
	def setNumberOfRefinements(self, value):
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			widget=it.widgets.num_refinements
			with widget.disable_callbacks():
				widget.value = value
		self.refresh()

	# getResolution
	def getResolution(self):
		return self.widgets.resolution.value

	# getMaxResolution
	def getMaxResolution(self):
		return self.db.getMaxResolution()

	# setResolution
	def setResolution(self, value):
		logger.debug(f"id={self.id} value={value}")
		value = Clamp(value, 0, self.db.getMaxResolution())
		for it in [self]+self.slices:
			widget=it.widgets.resolution
			with widget.disable_callbacks():
				widget.start = self.start_resolution
				widget.end   = self.db.getMaxResolution()
				widget.value = value
		self.refresh()

	# isViewDependent
	def isViewDependent(self):
		return self.widgets.view_dep.value

	# setViewDependent
	def setViewDependent(self, value):
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			widget=it.widgets.view_dep
			with widget.disable_callbacks():
				widget.value = value
		self.refresh()

	# getDirections
	def getDirections(self):
		return self.widgets.direction.options

	# setDirections
	def setDirections(self, value):
		logger.debug(f"id={self.id} value={value}")
		for it in [self] + self.slices:
			it.widgets.direction.options = value

	# getDirection
	def getDirection(self):
		return int(self.widgets.direction.value)

	# setDirection
	def setDirection(self, value):
		logger.debug(f"id={self.id} value={value}")
		pdim = self.getPointDim()
		if pdim == 2: value = 2
		dims = [int(it) for it in self.db.getLogicSize()]

		for it in [self] + self.slices:
			widget=it.widgets.direction
			with widget.disable_callbacks():
				widget.value = value
			it.triggerOnChange('direction', None, value)

		# default behaviour is to guess the offset
		offset_value,offset_range=self.guessOffset(value)
		self.setOffsetRange(offset_range)  # both extrema included
		self.setOffset(offset_value)

		for it in [self] + self.slices:
			if it.canvas:
				it.setQueryLogicBox(([0]*pdim,dims))

		self.refresh()

	# getLogicAxis (depending on the projection XY is the slice plane Z is the orthogoal direction)
	def getLogicAxis(self):
		dir  = self.getDirection()
		directions = self.getDirections()
		# this is the projected slice
		XY = list(directions.values())
		if len(XY) == 3:
			del XY[dir]
		else:
			assert (len(XY) == 2)
		X, Y = XY
		# this is the cross dimension
		Z = dir if len(directions) == 3 else 2
		titles = list(directions.keys())
		return (X, Y, Z), (titles[X], titles[Y], titles[Z] if len(titles) == 3 else 'Z')

	# getOffsetRange
	def getOffsetRange(self):
		widget=self.widgets.offset
		start,end,step=widget.start, widget.end, widget.step
		if widget.editable and step==1e-16: step=0.0 # problem with editable slider and step==0
		return start,end,step

	# setOffsetRange
	def setOffsetRange(self, value):
		logger.debug(f"id={self.id} value={value}")
		A, B, step = value
		for it in [self] +  self.slices:
			widget=it.widgets.offset
			with widget.disable_callbacks():
				widget.start=A
				widget.end=B
				if widget.editable and step==0.0:
					widget.step=1e-16 #  problem with editable slider and step==0
				else:
					widget.step=step

	# getOffset (in physic domain)
	def getOffset(self):
		return self.widgets.offset.value

	# setOffset (3d only) (in physic domain)
	def setOffset(self, value):
		logger.debug(f"id={self.id} new-value={value} old-value={self.getOffset()}")

		# do not send float offset if it's all integer
		if all([int(it) == it for it in self.getOffsetRange()]):
			value = int(value)

		for it in [self] + self.slices:
			widget=it.widgets.offset
			with widget.disable_callbacks():
				widget.value = value
				assert(widget.value == value)
			it.triggerOnChange('offset', None, value)
		self.refresh()

	# guessOffset
	def guessOffset(self, dir):

		pdim = self.getPointDim()

		# 2d there is no direction
		if pdim == 2:
			assert dir == 2
			value = 0
			logger.debug(f"id={self.id} pdim==2 calling setOffset({value})")
			return value,[0, 0, 1]
		else:
			vt = [self.logic_to_physic[I][0] for I in range(pdim)]
			vs = [self.logic_to_physic[I][1] for I in range(pdim)]

			if all([it == 0 for it in vt]) and all([it == 1.0 for it in vs]):
				dims = [int(it) for it in self.db.getLogicSize()]
				value = dims[dir] // 2
				return value,[0, int(dims[dir]) - 1, 1]
			else:
				A, B = self.getPhysicBox()[dir]
				value = (A + B) / 2.0
				return value,[A, B, 0]

	# toPhysic
	def toPhysic(self, value):

		# is a box
		if hasattr(value[0], "__iter__"):
			p1, p2 = [self.toPhysic(p) for p in value]
			return [p1, p2]

		pdim = self.getPointDim()
		dir = self.getDirection()
		assert (pdim == len(value))

		vt = [self.logic_to_physic[I][0] for I in range(pdim)]
		vs = [self.logic_to_physic[I][1] for I in range(pdim)]

		# apply scaling and translating
		ret = [vs[I] * value[I] + vt[I] for I in range(pdim)]

		if pdim == 3:
			del ret[dir]  # project

		assert (len(ret) == 2)
		return ret

	# toLogic
	def toLogic(self, value):
		assert (len(value) == 2)
		pdim = self.getPointDim()
		dir = self.getDirection()

		# is a box?
		if hasattr(value[0], "__iter__"):
			p1, p2 = [self.toLogic(p) for p in value]
			if pdim == 3:
				p2[dir] += 1  # make full dimensional
			return [p1, p2]

		ret = list(value)

		# unproject
		if pdim == 3:
			ret.insert(dir, 0)

		assert (len(ret) == pdim)

		vt = [self.logic_to_physic[I][0] for I in range(pdim)]
		vs = [self.logic_to_physic[I][1] for I in range(pdim)]

		# scaling/translatation
		try:
			ret = [(ret[I] - vt[I]) / vs[I] for I in range(pdim)]
		except Exception as ex:
			logger.info(f"Exception {ex} with logic_to_physic={self.logic_to_physic}", self.logic_to_physic)
			raise

		# unproject
		if pdim == 3:
			offset = self.getOffset()  # this is in physic coordinates
			ret[dir] = int((offset - vt[dir]) / vs[dir])

		assert (len(ret) == pdim)
		return ret

	# togglePlay
	def togglePlay(self, evt=None):
		if self.play.is_playing:
			self.stopPlay()
		else:
			self.startPlay()

	# startPlay
	def startPlay(self):
		logger.info(f"id={self.id}::startPlay")
		self.play.is_playing = True
		self.play.t1 = time.time()
		self.play.wait_render_id = None
		self.play.num_refinements = self.getNumberOfRefinements()
		self.setNumberOfRefinements(1)
		self.setWidgetsDisabled(True)
		self.widgets.play_button.disabled = False
		self.widgets.play_button.label = "Stop"

	# stopPlay
	def stopPlay(self):
		logger.info(f"id={self.id}::stopPlay")
		self.play.is_playing = False
		self.play.wait_render_id = None
		self.setNumberOfRefinements(self.play.num_refinements)
		self.setWidgetsDisabled(False)
		self.widgets.play_button.disabled = False
		self.widgets.play_button.label = "Play"

	# playNextIfNeeded
	def playNextIfNeeded(self):

		if not self.play.is_playing:
			return

		# avoid playing too fast by waiting a minimum amount of time
		t2 = time.time()
		if (t2 - self.play.t1) < float(self.getPlaySec()):
			return

		render_id = [self.render_id] + [it.render_id for it in self.slices]

		if self.play.wait_render_id is not None:
			if any([a < b for (a, b) in zip(render_id, self.play.wait_render_id) if a is not None and b is not None]):
				# logger.debug(f"Waiting render {render_id} {self.play.wait_render_id}")
				return

		# advance
		T = self.getTimestep() + self.getTimestepDelta()

		# reached the end -> go to the beginning?
		if T >= self.widgets.timestep.end:
			T = self.timesteps.widgets.timestep.start

		logger.info(f"id={self.id}::playing timestep={T}")

		# I will wait for the resolution to be displayed
		self.play.wait_render_id = [(it + 1) if it is not None else None for it in render_id]
		self.play.t1 = time.time()
		self.setTimestep(T)

	# isLinked
	def isLinked(self):
		return self.linked

	# setLinked
	def setLinked(self, value):
		self.linked = value

	# onShowMetadataClick
	def onShowMetadataClick(self):
		self.widgets.metadata.visible = not self.widgets.metadata.visible

	# setWidgetsDisabled
	def setWidgetsDisabled(self, value):
		for it in [self] + self.slices:
			it.widgets.scene.disabled = value
			it.widgets.palette.disabled = value
			it.widgets.timestep.disabled = value
			it.widgets.timestep_delta.disabled = value
			it.widgets.field.disabled = value
			it.widgets.direction.disabled = value
			it.widgets.offset.disabled = value
			it.widgets.num_refinements.disabled = value
			it.widgets.resolution.disabled = value
			it.widgets.view_dep.disabled = value
			it.widgets.status_bar["request"].disabled = value
			it.widgets.status_bar["response"].disabled = value
			it.widgets.play_button.disabled = value
			it.widgets.play_sec.disabled = value

	# getPointDim
	def getPointDim(self):
		return self.db.getPointDim() if self.db else 2

	# updateSceneText
	def updateSceneText(self):
		if self.parent: return self.parent.updateSceneText()
		widget=self.widgets.scene_body
		if widget.visible:
			body=self.getSceneBody()
			body=json.dumps(body,indent=2)
			widget.value=body

	# refresh
	def refresh(self):
		for it in [self] + self.slices:
			if it.query_node:
				it.aborted.setTrue()
				it.new_job=True

		self.updateSceneText()

	# getQueryLogicBox
	def getQueryLogicBox(self):
		assert(self.canvas)
		(x1,x2),(y1,y2)=self.canvas.getViewport()
		return self.toLogic([(x1,y1),(x2,y2)])

	# getViewport
	def getViewport(self):
		return self.canvas.getViewPort()

	# setViewPort
	def setViewPort(self,value):

		(x1,x2),(y1,y2)=value

		# fix aspect ratio
		W=self.canvas.getWidth()
		H=self.canvas.getHeight()

		# fix aspect ratio: the viewport is in physic coordinates
		if W>0 and H>0:
			w,cx =(x2-x1),x1+0.5*(x2-x1)
			h,cy =(y2-y1),y1+0.5*(y2-y1)
			if (w/W) > (h/H): 
				h=(w/W)*H 
			else: 
				w=(h/H)*W
			x1,y1=cx-w/2,cy-h/2
			x2,y2=cx+w/2,cy+h/2
			self.canvas.setViewport([(x1,x2),(y1,y2)])
			
		self.refresh()

	# setQueryLogicBox
	def setQueryLogicBox(self,value):
		assert(self.canvas)
		logger.debug(f"id={self.id} value={value}")
		proj=self.toPhysic(value) 
		(x1,y1),(x2,y2)=proj[0],proj[1]
		self.setViewPort([(x1,x2),(y1,y2)])
  
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

  # gotoPoint
	def gotoPoint(self,point):
		logger.debug(f"id={self.id} point={point}")
		pdim=self.getPointDim()
		for it in [self] + self.slices:
			# TODO
			continue

			if pdim==3:
				dir=it.getDirection()
				it.setOffset(point[dir])
			
			# the point should be centered in p3d
			(p1,p2),dims=it.getQueryLogicBox(),it.getLogicSize()
			p1,p2=list(p1),list(p2)
			for I in range(pdim):
				p1[I],p2[I]=point[I]-dims[I]/2,point[I]+dims[I]/2
			it.setQueryLogicBox([p1,p2])
			it.canvas.renderPoints([it.toPhysic(point)]) # COMMENTED OUT
  
	# gotNewData
	def gotNewData(self, result):

		assert(self.parent and self.canvas)

		data=result['data']
		try:
			data_range=np.min(data),np.max(data)
		except:
			data_range=0.0,0.0

		logic_box=result['logic_box'] 

		# depending on the palette range mode, I need to use different color mapper low/high
		mode=self.getRangeMode()

		# show the user what is the current offset
		maxh=self.db.getMaxResolution()
		dir=self.getDirection()

		pdim=self.getPointDim()
		vt,vs=self.logic_to_physic[dir] if pdim==3 else (0.0,1.0)
		endh=result['H']

		user_physic_offset=self.getOffset()

		real_logic_offset=logic_box[0][dir] if pdim==3 else 0.0
		real_physic_offset=vs*real_logic_offset + vt 
		user_logic_offset=int((user_physic_offset-vt)/vs)

		self.widgets.offset.name=" ".join([
			f"Offset: {user_physic_offset:.3f}±{abs(user_physic_offset-real_physic_offset):.3f}",
			f"Pixel: {user_logic_offset}±{abs(user_logic_offset-real_logic_offset)}",
			f"Max Res: {endh}/{maxh}"
		])

		# refresh the range
		if True:

			# in dynamic mode, I need to use the data range
			if mode=="dynamic":
				self.widgets.range_min.value = data_range[0]
				self.widgets.range_max.value = data_range[1]
				
			# in data accumulation mode I am accumulating the range
			if mode=="dynamic-acc":
				if self.widgets.range_min.value==self.widgets.range_max.value:
					self.widgets.range_min.value=data_range[0]
					self.widgets.range_max.value=data_range[1]
				else:
					self.widgets.range_min.value = min(self.widgets.range_min.value, data_range[0])
					self.widgets.range_max.value = max(self.widgets.range_max.value, data_range[1])

			# update the color bar
			low =cdouble(self.widgets.range_min.value)
			high=cdouble(self.widgets.range_max.value)

		# regenerate colormap
		if self.color_bar is None:
			color_mapper_type=self.getColorMapperType()
			assert(color_mapper_type in ["linear","log"])
			is_log=color_mapper_type=="log"
			palette=self.widgets.palette.value
			mapper_low =max(self.epsilon, low ) if is_log else low
			mapper_high=max(self.epsilon, high) if is_log else high
			

			self.color_bar = ColorBar(color_mapper = 
				LogColorMapper   (palette=palette, low=mapper_low, high=mapper_high) if is_log else 
				LinearColorMapper(palette=palette, low=mapper_low, high=mapper_high)
			)

		logger.debug(f"id={self.id}::rendering result data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box} data-range={data_range} range={[low,high]}")

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

		self.triggerOnChange("data", None, data)
  
	# pushJobIfNeeded
	def pushJobIfNeeded(self):
		assert(self.query_node and self.canvas)
		canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
		query_logic_box=self.getQueryLogicBox()
		offset=self.getOffset()
		pdim=self.getPointDim()

		if not self.new_job and str(self.last_query_logic_box)==str(query_logic_box):
			return

		# abort the last one
		self.aborted.setTrue()
		self.query_node.waitIdle()
		num_refinements = self.getNumberOfRefinements()
		if num_refinements==0:
			num_refinements=3 if pdim==2 else 4
		self.aborted=Aborted()

		# do not push too many jobs
		if (time.time()-self.last_job_pushed)<0.2:
			return
		
		
		# I will use max_pixels to decide what resolution, I am using resolution just to add/remove a little the 'quality'
		if self.isViewDependent():
			endh=None 
			canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())

			# probably the UI is not ready yet
			if not canvas_w or not canvas_h:
				return
			
			max_pixels=canvas_w*canvas_h
			resolution=self.getResolution()
			delta=resolution-self.getMaxResolution()
			if resolution<self.getMaxResolution():
				max_pixels=int(max_pixels/pow(1.3,abs(delta))) # decrease 
			elif resolution>self.getMaxResolution():
				max_pixels=int(max_pixels*pow(1.3,abs(delta))) # increase 
		else:
			# I am not using the information about the pixel on screen
			max_pixels=None
			resolution=self.getResolution()
			endh=resolution
		
		self.updateSceneText()
		
		logger.debug(f"id={self.id} pushing new job query_logic_box={query_logic_box} max_pixels={max_pixels} endh={endh}..")

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
		
		self.last_job_pushed=time.time()
		self.last_query_logic_box=query_logic_box
		self.new_job=False

		# link views
		if self.isLinked() and self.parent:
			idx=self.parent.slices.index(self)
			for it in self.parent.slices:
				if it!=self: 
					it.setOffset(offset)
					it.setQueryLogicBox(query_logic_box)

		logger.debug(f"id={self.id} pushed new job query_logic_box={query_logic_box}")

	# onIdle
	def onIdle(self):

		

		for it in [self] + self.slices:

			if not it.db:
				continue

			if it.canvas and  it.canvas.getWidth()>0 and it.canvas.getHeight()>0:
				it.playNextIfNeeded()

			if it.query_node:
				result=it.query_node.popResult(last_only=True) 
				if result is not None: 
					it.gotNewData(result)
				it.pushJobIfNeeded()


# an alias for backward compatibility
Slices=Slice




