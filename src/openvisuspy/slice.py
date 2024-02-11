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

import param

DEFAULT_START_RESOLUTION = 20
SLICE_ID=0
EPSILON = 0.001

DEFAULT_SHOW_OPTIONS={
	"top": [
		["open_button","save_button","info_button","copy_url_button", "logout_button", "scene", "timestep", "timestep_delta", "palette",  "color_mapper_type", "resolution", "view_dep", "num_refinements"],
		["field","direction", "offset", "range_mode", "range_min",  "range_max"]
	],
	"bottom": [
		["request","response"]
	]
}


# ////////////////////////////////////////////////////////////////////////////////////
class Slice(param.Parameterized):

	# widgets

	scene                  = Widgets.Select   (name="Scene", options=[], width=180, )
	timestep               = Widgets.Slider   (name="Time", type="float", value=0, start=0, end=1, step=1.0, editable=True,  sizing_mode="stretch_width")
	timestep_delta         = Widgets.Select   (name="Speed", options=["1x", "2x", "4x", "8x", "16x", "32x", "64x", "128x"], value="1x", width=60)
	field                  = Widgets.Select   (name='Field', options=[], value='data', width=80)
	palette                = Widgets.ColorMap (name="Palette", options=GetPalettes(), value_name=DEFAULT_PALETTE, ncols=5,  width=220)
	range_mode             = Widgets.Select   (name="Range", options=["metadata", "user", "dynamic", "dynamic-acc"], value="dynamic-acc", width=120)
	range_min              = Widgets.Input    (name="Min", type="float",width=80)
	range_max              = Widgets.Input    (name="Max", type="float",width=80)
	color_mapper_type      = Widgets.Select   (name="Mapper", options=["linear", "log", ],width=80)
	resolution             = Widgets.Slider   (name='Res', type="int", value=21, start=DEFAULT_START_RESOLUTION, editable=False, end=99,  sizing_mode="stretch_width")
	view_dep               = Widgets.Select   (name="ViewDep",options={"Yes":True,"No":False}, value=True,width=80)
	num_refinements        = Widgets.Slider   (name='#Ref', type="int", value=0, start=0, end=4, editable=False, width=80)
	direction              = Widgets.Select   (name='Direction', options={'X':0, 'Y':1, 'Z':2}, value=2, width=80)
	offset                 = Widgets.Slider   (name="Offset", type="float", start=0.0, end=1024.0, step=1.0, value=0.0, editable=True,  sizing_mode="stretch_width")
	play_button            = Widgets.Button   (name="Play", width=8)
	play_sec               = Widgets.Select   (name="Frame delay", options=["0.00", "0.01", "0.1", "0.2", "0.1", "1", "2"], value="0.01")
	request                = Widgets.Input    (name="", type="text", sizing_mode='stretch_width', disabled=False)
	response               = Widgets.Input    (name="", type="text", sizing_mode='stretch_width', disabled=False)

	info_button            = Widgets.Button   (icon="info-circle",width=20)
	open_button            = Widgets.Button   (icon="file-upload",width=20)
	save_button            = Widgets.Button   (icon="file-download",width=20)
	save_button_helper     = Widgets.Input    (visible=False)
	copy_url_button        = Widgets.Button   (icon="copy",width=20)
	copy_url_button_helper = Widgets.Input    (visible=False)
	logout_button          = Widgets.Button   (icon="logout",width=20)

	scene_body=Widgets.TextAreaInput(
		name='Current',
		sizing_mode="stretch_width",
		height=520,
		stylesheets=["""
			.bk-input {
				background-color: rgb(48, 48, 64);
				color: white;
				font-size: small;
			}
			"""])

	# constructor
	def __init__(self):

		self.on_change_callbacks={}

		self.num_hold=0
		global SLICE_ID
		self.id=SLICE_ID
		SLICE_ID += 1
		
		self.db = None
		self.access = None
		self.render_id = 0 

		# translate and scale for each dimension
		self.logic_to_physic        = [(0.0, 1.0)] * 3
		self.metadata_range         = [0.0, 255.0]
		self.scenes                 = {}

		self.createGui()

		self.scene.param.watch(lambda evt: self.setScene(evt.new),"value")
		self.timestep.param.watch(lambda evt:self.setTimestep(evt.new), "value")
		self.timestep_delta.param.watch(lambda evt: self.setTimestepDelta(self.speedFromOption(evt.new)),"value")
		self.field.param.watch(lambda evt: self.setField(evt.new),"value")

		self.palette.param.watch(lambda evt: self.setPalette(evt.new),"value_name")
		self.range_mode.param.watch(lambda evt: self.setRangeMode(evt.new),"value")
		self.range_min.param.watch(lambda evt: self.setRangeMin(evt.new) if self.getRangeMode() == "user" else None,"value")
		self.range_max.param.watch(lambda evt: self.setRangeMax(evt.new) if self.getRangeMode() == "user" else None,"value")
		self.color_mapper_type.param.watch(lambda evt: self.setColorMapperType(evt.new),"value")
		
		self.resolution.param.watch(lambda evt: self.setResolution(evt.new),"value")
		self.view_dep.param.watch(lambda evt: self.setViewDependent(evt.new),"value")
		self.num_refinements.param.watch(lambda evt: self.setNumberOfRefinements(evt.new),"value")
		self.direction.param.watch(lambda evt: self.setDirection(evt.new),"value")
		self.offset.param.watch(lambda evt: self.setOffset(evt.new),"value")

		self.info_button.on_click(lambda evt: self.showInfo())
		self.open_button.on_click(lambda evt: self.showOpen())
		self.save_button.on_click(lambda evt: self.save())
		self.copy_url_button.on_click(lambda evt: self.copyUrl())
		self.play_button.on_click(lambda evt: self.togglePlay())

		self.setShowOptions(DEFAULT_SHOW_OPTIONS)

		self.start()

	# open
	def showOpen(self):

		def onLoadClick(evt=None):
			body=value.decode('ascii')
			self.scene_body.value=body
			# self.setSceneBody(json.loads(body)) NOT SURE I WANT THIS
			ShowInfoNotification('Load done')

		file_input = Widgets.FileInput(name="Load", description="Load", accept=".json", callback=onLoadClick)

		# onEvalClick
		def onEvalClick(evt=None):
			body=json.loads(self.scene_body.value)
			self.setSceneBody(body)
			ShowInfoNotification('Eval done')

		eval_button = Widgets.Button(name="Eval", callback=onEvalClick, align='end')
		self.showDialog(
			Column(
				self.scene_body,
				Row(file_input, eval_button, align='end'),
				sizing_mode="stretch_both",align="end"
			), 
			width=600, height=700, name="Open")
	

	# save
	def save(self):
		body=json.dumps(self.getSceneBody(),indent=2)
		self.save_button_helper.value=body
		ShowInfoNotification('Save done')
		print(body)

	# copy url
	def copyUrl(self):
		self.copy_url_button_helper.value=self.getShareableUrl()
		ShowInfoNotification('Copy url done')


	# createGui
	def createGui(self):

		self.save_button.js_on_click(args={"source": self.save_button_helper}, code="""
			function jsSave() {
				console.log(source.value);
				const link = document.createElement("a");
				const file = new Blob([source.value], { type: 'text/plain' });
				link.href = URL.createObjectURL(file);
				link.download = "sample.txt";
				link.click();
				URL.revokeObjectURL(link.href);
			}
			setTimeout(jsSave,300);
		""")


		self.copy_url_button.js_on_click(args={"source": self.copy_url_button_helper}, code="""
			function jsCopyUrl() {
				console.log(source.value);
				navigator.clipboard.writeText(source.value);
			} 
			setTimeout(jsCopyUrl,300);
		""")

		self.logout_button = Widgets.Button(icon="logout",width=20)
		self.logout_button.js_on_click(args={"source": self.logout_button}, code="""
			console.log("logging out...")
			window.location=window.location.href + "/logout";
		""")

		# for icons see https://tabler.io/icons

		# play time
		self.play = types.SimpleNamespace()
		self.play.is_playing = False

		self.idle_callback = None
		self.color_bar     = None
		self.query_node    = None
		self.canvas        = None

		self.t1=time.time()
		self.aborted       = Aborted()
		self.new_job       = False
		self.current_img   = None
		self.last_job_pushed =time.time()
		self.query_node=QueryNode()
		self.canvas = Canvas(self.id)
		self.canvas.on_viewport_change=lambda: self.refresh()

		self.top_layout=Column(sizing_mode="stretch_width")

		self.middle_layout=Column(
			Row(self.canvas.main_layout, sizing_mode='stretch_both'),
			sizing_mode='stretch_both'
		)

		self.bottom_layout=Column(sizing_mode="stretch_width")

		self.dialogs=Column()
		self.dialogs.visible=False

		self.main_layout=Column(
			self.top_layout,
			self.middle_layout,
			self.bottom_layout, 

			self.dialogs,
			self.copy_url_button_helper,
			self.save_button_helper,

			sizing_mode="stretch_both"
		)

	# getShowOptions
	def getShowOptions(self):
		return self.show_options

	# setShowOptions
	def setShowOptions(self, value):
		self.show_options=value
		for layout, position in ((self.top_layout,"top"),(self.bottom_layout,"bottom")):
			layout.clear()
			for row in value.get(position,[[]]):
				v=[]
				for widget in row:
					if isinstance(widget,str):
						widget=getattr(self, widget.replace("-","_"),None)
					if widget:
						v.append(widget)
				if v: layout.append(Row(*v,sizing_mode="stretch_width"))

		# bottom

	# getShareableUrl
	def getShareableUrl(self):
		body=self.getSceneBody()
		load_s=base64.b64encode(json.dumps(body).encode('utf-8')).decode('ascii')
		current_url=GetCurrentUrl()
		o=urlparse(current_url)
		return o.scheme + "://" + o.netloc + o.path + '?' + urlencode({'load': load_s})		

	# stop
	def stop(self):
		self.aborted.setTrue()
		self.query_node.stop()

	# start
	def start(self):
		self.query_node.start()
		if not self.idle_callback:
			self.idle_callback = AddPeriodicCallback(self.onIdle, 1000 // 30)
		self.refresh()

	# getMainLayout
	def getMainLayout(self):
		return self.main_layout

	# getLogicToPhysic
	def getLogicToPhysic(self):
		return self.logic_to_physic

	# setLogicToPhysic
	def setLogicToPhysic(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.logic_to_physic = value
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
		(x1,x2),(y1,y2)=self.canvas.getViewport()
		return {
			"scene" : {
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
				"range-min": self.getRangeMin(),
				"x":(x1+x2)/2.0,
				"y":(y1+y2)/2.0,
				"w":x2-x1,
				"h":y2-y1	
			}
		}

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

		self.scenes={}
		for it in value[root]:
			if "name" in it:
				self.scenes[it["name"]]={"scene": it}

		self.scene.options = list(self.scenes)

		if self.scenes:
			self.setScene(list(self.scenes)[0])

	# setSceneBody
	def setSceneBody(self, scene):

		logger.info(f"# //////////////////////////////////////////#")
		logger.info(f"id={self.id} {scene} START")

		# TODO!
		# self.stop()

		assert(isinstance(scene,dict))
		assert(len(scene)==1 and list(scene.keys())==["scene"])

		# go one level inside
		scene=scene["scene"]

		# the url should come from first load (for security reasons)
		name=scene["name"]

		assert(name in self.scenes)
		default_scene=self.scenes[name]["scene"]
		url =default_scene["url"]
		urls=default_scene.get("urls",{})

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
		db=LoadDataset(url=url) 

		# update the GUI too
		self.db    =db
		self.access=db.createAccess()
		self.scene.value=name

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

		timestep_delta = int(scene.get("timestep-delta", 1))
		self.setTimestepDelta(timestep_delta)

		timestep = int(scene.get("timestep", self.db.getTimesteps()[0]))
		self.setTimestep(timestep)

		viewdep=bool(scene.get('view-dep', True))
		self.setViewDependent(viewdep)

		resolution=int(scene.get("resolution", -6))
		if resolution<0: resolution=self.db.getMaxResolution()+resolution
		self.setResolution(resolution)

		field=scene.get("field", self.db.getField().name)
		self.setField(field)

		num_refinements=int(scene.get("num-refinements", 2))
		self.setNumberOfRefinements(num_refinements)

		direction=int(scene.get("direction", 2))
		self.setDirection(direction)

		default_offset, offset_range=self.guessOffset(direction)
		offset=float(scene.get("offset",default_offset))
		self.setOffsetRange(offset_range) 
		self.setOffset(offset)	

		play_sec=float(scene.get("play-sec",0.01))
		self.setPlaySec(play_sec)

		palette=scene.get("palette",DEFAULT_PALETTE)
		self.setPalette(palette)

		db_field = self.db.getField(field)
		palette_metadata_range=scene.get("metadata-range",[db_field.getDTypeRange().From, db_field.getDTypeRange().To])
		self.setMetadataRange(palette_metadata_range)

		range_mode=scene.get("range-mode","dynamic-acc")
		self.setRangeMode(range_mode)

		if self.getRangeMode()=="user":
			range_min=scene.get("range-min",low)
			self.setRangeMin(range_min)

			range_max=scene.get("range-max",high)
			self.setRangeMax(range_max)

		color_mapper_type=scene.get("color-mapper-type","linear")
		self.setColorMapperType(color_mapper_type)	

		x=scene.get("x",None)
		y=scene.get("y",None)
		w=scene.get("w",None)
		h=scene.get("h",None)

		if x is not None:
			x1,x2=x-w/2.0, x+w/2.0
			y1,y2=y-h/2.0, y+h/2.0
			self.canvas.setViewport([(x1,x2),(y1,y2)])

		show_options=scene.get("show-options",DEFAULT_SHOW_OPTIONS)
		self.setShowOptions(show_options)

		self.start()

		logger.info(f"id={self.id} END\n")

	# getScene
	def getScene(self):
		return self.scene.value

	# setScene
	def setScene(self, name):
		self.setSceneBody(self.scenes[name])

	# showInfo
	def showInfo(self):

		logger.debug(f"Show info")
		body=self.scenes[self.getScene()]
		metadata=body["scene"].get("metadata", [])

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

		float_panel=FloatPanel(*args, **kwargs)
		self.dialogs.append(float_panel)

	# getTimesteps
	def getTimesteps(self):
		try:
			return [int(value) for value in self.db.db.getTimesteps().asVector()]
		except:
			return []

	# setTimesteps
	def setTimesteps(self, value):
		logger.debug(f"id={self.id} start={value[0]} end={value[-1]}")
		self.timestep.start = value[0]
		self.timestep.end   = value[-1]
		self.timestep.step  = 1

	# speedFromOption
	def speedFromOption(self, option):
		return (int(option[:-1]))

	# optionFromSpeed
	def optionFromSpeed(self, speed):
		return (str(speed) + "x")

	# getPlaySec
	def getPlaySec(self):
		return self.play_sec.value

	# setPlaySec
	def setPlaySec(self,value):
		logger.debug(f"id={self.id} value={value}")
		self.play_sec.value=value

	# getTimestepDelta
	def getTimestepDelta(self):
		return self.speedFromOption(self.timestep_delta.value)

	# setTimestepDelta
	def setTimestepDelta(self, value):
		logger.debug(f"id={self.id} value={value}")
		option=self.optionFromSpeed(value)

		A = self.timestep.start
		B = self.timestep.end
		T = self.getTimestep()
		T = A + value * int((T - A) / value)
		T = min(B, max(A, T))
		
		self.timestep_delta.value = option
		self.timestep.step = value

		self.setTimestep(T)

	# getTimestep
	def getTimestep(self):
		return int(self.timestep.value)

	# setTimestep
	def setTimestep(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.timestep.value = value
		self.refresh()

	# getFields
	def getFields(self):
		return self.field.options

	# setFields
	def setFields(self, value):
		value=list(value)
		logger.debug(f"id={self.id} value={value}")
		self.field.options = value

	# getField
	def getField(self):
		return str(self.field.value)

	# setField
	def setField(self, value):
		logger.debug(f"id={self.id} value={value}")
		if value is None: return
		self.field.value = value
		self.refresh()

	# getPalette
	def getPalette(self):
		return self.palette.value_name 

	# setPalette
	def setPalette(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.palette.value_name = value
		self.color_bar=None
		self.refresh()

	# getMetadataRange
	def getMetadataRange(self):
		return self.metadata_range

	# setMetadataRange
	def setMetadataRange(self, value):
		vmin, vmax = value
		self.metadata_range = [vmin, vmax]
		self.color_map=None
		self.refresh()

	# getRangeMode
	def getRangeMode(self):
		return self.range_mode.value

	# setRangeMode
	def setRangeMode(self, mode):
		logger.debug(f"id={self.id} mode={mode} ")

		self.range_mode.value = mode
		self.color_map=None

		if mode == "metadata":   self.range_min.value = it.metadata_range[0]
		if mode == "dynamic-acc":self.range_min.value = 0.0
		self.range_min.disabled = False if mode == "user" else True

		if mode == "metadata":   self.range_max.value = it.metadata_range[1]
		if mode == "dynamic-acc":self.range_max.value = 0.0
		self.range_max.disabled = False if mode == "user" else True

		self.refresh()

	# getRangeMin
	def getRangeMin(self):
		return cdouble(self.range_min.value)

	# getRangeMax
	def getRangeMax(self):
		return cdouble(self.range_max.value)

	# setRangeMin
	def setRangeMin(self, value):
		self.range_min.value = vmin
		self.color_map=None
		self.refresh()

	# setRangeMin
	def setRangeMax(self, value):
		self.range_max.value = vmin
		self.color_map=None
		self.refresh()

	# getColorMapperType
	def getColorMapperType(self):
		return self.color_mapper_type.value

	# setColorMapperType
	def setColorMapperType(self, value):
		logger.debug(f"id={self.id} value={value}")
		palette = self.getPalette()
		self.color_mapper_type.value = value
		self.color_bar=None # force reneration of color_mapper
		self.start()

	# getNumberOfRefinements
	def getNumberOfRefinements(self):
		return self.num_refinements.value

	# setNumberOfRefinements
	def setNumberOfRefinements(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.num_refinements.value = value
		self.refresh()

	# getResolution
	def getResolution(self):
		return self.resolution.value

	# getMaxResolution
	def getMaxResolution(self):
		return self.db.getMaxResolution()

	# setResolution
	def setResolution(self, value):
		logger.debug(f"id={self.id} value={value}")
		value = Clamp(value, 0, self.db.getMaxResolution())
		self.resolution.start = DEFAULT_START_RESOLUTION
		self.resolution.end   = self.db.getMaxResolution()
		self.resolution.value = value
		self.refresh()

	# isViewDependent
	def isViewDependent(self):
		return self.view_dep.value

	# setViewDependent
	def setViewDependent(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.view_dep.value = value
		self.refresh()

	# getDirections
	def getDirections(self):
		return self.direction.options

	# setDirections
	def setDirections(self, value):
		logger.debug(f"id={self.id} value={value}")
		self.direction.options = value

	# getDirection
	def getDirection(self):
		return int(self.direction.value)

	# setDirection
	def setDirection(self, value):
		logger.debug(f"id={self.id} value={value}")
		pdim = self.getPointDim()
		if pdim == 2: value = 2
		dims = [int(it) for it in self.db.getLogicSize()]
		self.direction.value = value

		# default behaviour is to guess the offset
		offset_value,offset_range=self.guessOffset(value)
		self.setOffsetRange(offset_range)  # both extrema included
		self.setOffset(offset_value)

		self.setQueryLogicBox(([0]*pdim,dims))

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
		widget=self.offset
		start,end,step=widget.start, widget.end, widget.step
		if widget.editable and step==1e-16: step=0.0 # problem with editable slider and step==0
		return start,end,step

	# setOffsetRange
	def setOffsetRange(self, value):
		logger.debug(f"id={self.id} value={value}")
		A, B, step = value
		self.offset.start=A
		self.offset.end=B
		if self.offset.editable and step==0.0:
			self.offset.step=1e-16 #  problem with editable slider and step==0
		else:
			self.offset.step=step

	# getOffset (in physic domain)
	def getOffset(self):
		return self.offset.value

	# setOffset (3d only) (in physic domain)
	def setOffset(self, value):
		logger.debug(f"id={self.id} new-value={value} old-value={self.getOffset()}")

		# do not send float offset if it's all integer
		if all([int(it) == it for it in self.getOffsetRange()]): value = int(value)
		self.offset.value = value
		assert(self.offset.value == value)
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
	def togglePlay(self):
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
		self.play_button.disabled = False
		self.play_button.label = "Stop"

	# stopPlay
	def stopPlay(self):
		logger.info(f"id={self.id}::stopPlay")
		self.play.is_playing = False
		self.play.wait_render_id = None
		self.setNumberOfRefinements(self.play.num_refinements)
		self.setWidgetsDisabled(False)
		self.play_button.disabled = False
		self.play_button.label = "Play"

	# playNextIfNeeded
	def playNextIfNeeded(self):

		if not self.play.is_playing:
			return

		# avoid playing too fast by waiting a minimum amount of time
		t2 = time.time()
		if (t2 - self.play.t1) < float(self.getPlaySec()):
			return

		# wait
		if self.play.wait_render_id is not None and self.render_id<self.play.wait_render_id:
			return

		# advance
		T = self.getTimestep() + self.getTimestepDelta()

		# reached the end -> go to the beginning?
		if T >= self.timestep.end:
			T = self.timesteps.timestep.start

		logger.info(f"id={self.id}::playing timestep={T}")

		# I will wait for the resolution to be displayed
		self.play.wait_render_id = self.render_id+1
		self.play.t1 = time.time()
		self.setTimestep(T)

	# onShowMetadataClick
	def onShowMetadataClick(self):
		self.metadata.visible = not self.metadata.visible

	# setWidgetsDisabled
	def setWidgetsDisabled(self, value):
		self.scene.disabled = value
		self.palette.disabled = value
		self.timestep.disabled = value
		self.timestep_delta.disabled = value
		self.field.disabled = value
		self.direction.disabled = value
		self.offset.disabled = value
		self.num_refinements.disabled = value
		self.resolution.disabled = value
		self.view_dep.disabled = value
		self.request.disabled = value
		self.response.disabled = value
		self.play_button.disabled = value
		self.play_sec.disabled = value

	# getPointDim
	def getPointDim(self):
		return self.db.getPointDim() if self.db else 2

	# updateSceneBodyText
	def updateSceneBodyText(self):
		body=json.dumps(self.getSceneBody(),indent=2)
		self.scene_body.value=body

	# refresh
	def refresh(self):
		self.aborted.setTrue()
		self.new_job=True
		self.updateSceneBodyText()

	# getQueryLogicBox
	def getQueryLogicBox(self):
		assert(self.canvas)
		(x1,x2),(y1,y2)=self.canvas.getViewport()
		return self.toLogic([(x1,y1),(x2,y2)])

	# setQueryLogicBox
	def setQueryLogicBox(self,value):
		assert(self.canvas)
		logger.debug(f"id={self.id} value={value}")
		proj=self.toPhysic(value) 
		(x1,y1),(x2,y2)=proj[0],proj[1]
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

  # gotoPoint
	def gotoPoint(self,point):
		return 
		logger.debug(f"id={self.id} point={point}")
		pdim=self.getPointDim()

		if pdim==3:
			dir=self.getDirection()
			self.setOffset(point[dir])
		
		# the point should be centered in p3d
		(p1,p2),dims=self.getQueryLogicBox(),self.getLogicSize()
		p1,p2=list(p1),list(p2)
		for I in range(pdim):
			p1[I],p2[I]=point[I]-dims[I]/2,point[I]+dims[I]/2
		self.setQueryLogicBox([p1,p2])
		self.canvas.renderPoints([self.toPhysic(point)]) # COMMENTED OUT
  
	# gotNewData
	def gotNewData(self, result):

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

		self.offset.name=" ".join([
			f"Offset: {user_physic_offset:.3f}±{abs(user_physic_offset-real_physic_offset):.3f}",
			f"Pixel: {user_logic_offset}±{abs(user_logic_offset-real_logic_offset)}",
			f"Max Res: {endh}/{maxh}"
		])

		# refresh the range
		if True:

			# in dynamic mode, I need to use the data range
			if mode=="dynamic":
				self.range_min.value = data_range[0]
				self.range_max.value = data_range[1]
				
			# in data accumulation mode I am accumulating the range
			if mode=="dynamic-acc":
				if self.range_min.value==self.range_max.value:
					self.range_min.value=data_range[0]
					self.range_max.value=data_range[1]
				else:
					self.range_min.value = min(self.range_min.value, data_range[0])
					self.range_max.value = max(self.range_max.value, data_range[1])

			# update the color bar
			low =cdouble(self.range_min.value)
			high=cdouble(self.range_max.value)

		# regenerate colormap
		if self.color_bar is None:
			color_mapper_type=self.getColorMapperType()
			assert(color_mapper_type in ["linear","log"])
			is_log=color_mapper_type=="log"
			palette=self.palette.value
			mapper_low =max(EPSILON, low ) if is_log else low
			mapper_high=max(EPSILON, high) if is_log else high
			

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
		self.response.value=" ".join([
			f"#{result['I']+1}",
			f"{str(logic_box).replace(' ','')}",
			f"{data.shape[0]}x{data.shape[1]}",
			f"Res={result['H']}/{maxh}",
			f"{result['msec']}msec",
			str(query_status)
		])
		self.render_id+=1 

		# self.triggerOnChange("data", None, data)
  

	# pushJobIfNeeded
	def pushJobIfNeeded(self):
		assert(self.query_node and self.canvas)
		canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
		query_logic_box=self.getQueryLogicBox()
		offset=self.getOffset()
		pdim=self.getPointDim()

		if not self.new_job:
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
		
		self.updateSceneBodyText()
		
		logger.debug(f"id={self.id} pushing new job query_logic_box={query_logic_box} max_pixels={max_pixels} endh={endh}..")

		timestep=self.getTimestep()
		field=self.getField()
		box_i=[[int(it) for it in jt] for jt in query_logic_box]
		self.request.value=f"t={timestep} b={str(box_i).replace(' ','')} {canvas_w}x{canvas_h}"
		self.response.value="Running..."

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
		self.new_job=False
		logger.debug(f"id={self.id} pushed new job query_logic_box={query_logic_box}")

	# onIdle
	def onIdle(self):

		if not self.db:
			return

		if self.canvas and  self.canvas.getWidth()>0 and self.canvas.getHeight()>0:
			self.playNextIfNeeded()

		if self.query_node:
			result=self.query_node.popResult(last_only=True) 
			if result is not None: 
				self.gotNewData(result)
			self.pushJobIfNeeded()






