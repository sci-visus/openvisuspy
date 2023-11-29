import base64
import types
import logging
import copy

import requests
import os,sys,io,threading,time

from statistics import mean, median
import numpy as np
from requests.auth import HTTPBasicAuth

import bokeh
from bokeh.events import DoubleTap
from bokeh.plotting import figure

import panel as pn

from .utils import *
from .backend import Aborted,LoadDataset,ExecuteBoxQuery,QueryNode
from .canvas import Canvas

import colorcet
PALETTES = [name for name in bokeh.palettes.__palettes__ if name.endswith("256")]
PALETTES.extend(sorted([f"colorcet.{name}" for name in colorcet.palette]))

logger = logging.getLogger(__name__)

# //////////////////////////////////////////////////////////////////////////////////////
def ReplaceContent(layout, new_list):
	while len(layout): layout.pop(0)
	layout.extend(new_list)

# //////////////////////////////////////////////////////////////////////////////////////
def CreateCheckBox(callback=None,**kwargs):
	ret=pn.widgets.Checkbox(**kwargs)
	def onChange(evt):
		if evt.old == evt.new or not callback: return
		callback(evt.new)
	ret.param.watch(onChange,"value")
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateRadioButtonGroup(callback=None,**kwargs):
	ret=pn.widgets.RadioButtonGroup(**kwargs)
	def onChange(evt):
		if evt.old == evt.new or not callback: return
		callback(evt.new)
	ret.param.watch(onChange,"value")
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateButton(callback=None,**kwargs):
	ret = pn.widgets.Button(**kwargs)
	def onClick(evt):
		if callback: callback()
	ret.on_click(onClick)
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateTextInput(callback=None,**kwargs):
	ret = pn.widgets.TextInput(**kwargs)
	def onChange(evt):
		if evt.old == evt.new or not callback: return
		callback(evt.new)
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateIntInput(callback=None,**kwargs):
	ret = pn.widgets.IntInput(**kwargs)
	def onChange(evt):
		if evt.old == evt.new or not callback: return
		callback(evt.new)
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateFloatInput(callback=None,**kwargs):
	ret = pn.widgets.FloatInput(**kwargs)
	def onChange(evt):
		if evt.old == evt.new or not callback: return
		callback(evt.new)
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateSelect(callback=None, **kwargs):
	ret = pn.widgets.Select(**kwargs) 
	def onChange(evt):
		if evt.old == evt.new or not callback: return
		callback(evt.new)
	ret.param.watch(onChange,"value")
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateIntSlider(callback=None, parameter_name="value", editable=False, **kwargs):
	ret = pn.widgets.EditableIntSlider(**kwargs) if editable else pn.widgets.IntSlider(**kwargs)
	def onChange(evt):
		if evt.old == evt.new: return
		if callback: callback(evt.new)
	ret.param.watch(onChange,parameter_name)
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateFloatSlider(editable=False, format="0.001", callback=None, parameter_name="value", **kwargs):
	from bokeh.models.formatters import NumeralTickFormatter
	kwargs["format"]=NumeralTickFormatter(format=format)
	ret = pn.widgets.EditableFloatSlider(**kwargs) if editable else pn.widgets.FloatSlider
	def onChange(evt):
		if evt.old == evt.new: return
		if callback: callback(evt.new)
	ret.param.watch(onChange,parameter_name)
	return ret

# //////////////////////////////////////////////////////////////////////////////////////
def CreateFloatRangeSlider(editable=False, format="0.001", callback=None, parameter_name="value", **kwargs):
	from bokeh.models.formatters import NumeralTickFormatter
	kwargs["format"]=NumeralTickFormatter(format=format)
	ret = pn.widgets.EditableRangeSlider(**kwargs) if editable else pn.widgets.RangeSlider
	def onChange(evt):
		if evt.old == evt.new: return
		if callback: callback(evt.new)
	ret.param.watch(onChange,parameter_name)
	return ret


# //////////////////////////////////////////////////////////////////////////////////////
class Widgets:
	ID = 0

	epsilon = 0.001

	start_resolution = 20

	# constructor
	def __init__(self, parent=None):

		self.parent = parent

		self.main_layout=pn.Column(sizing_mode='stretch_both')

		self.id = f"{type(self).__name__}/{Widgets.ID}"
		Widgets.ID += 1
		self.config = {}
		self.db = None
		self.access = None
		self.render_id = None  # by default I am not rendering
		self.logic_to_physic = [(0.0, 1.0)] * 3
		self.slices = []
		self.linked = False

		self.widgets = types.SimpleNamespace()

		self.widgets.datasets = CreateSelect(name="Dataset", options=[], width=60, callback=lambda new: self.setDataset(new, force=True))
		self.widgets.palette = CreateSelect(name='Palette', options=PALETTES, value= 'Viridis256', callback=self.setPalette)

		# palette range
		self.metadata_palette_range = [0.0, 255.0]
		self.widgets.palette_range_mode = CreateSelect(name="Range", options=["metadata", "user", "dynamic", "dynamic-acc"], value="dynamic-acc", width=80, callback=self.setPaletteRangeMode)

		def onPaletteRangeChange(evt):
			if self.getPaletteRangeMode() == "user":
				self.setPaletteRange(self.getPaletteRange())

		self.widgets.palette_range_vmin = CreateFloatInput(name="Min", width=80, callback=onPaletteRangeChange)
		self.widgets.palette_range_vmax = CreateFloatInput(name="Max", width=80, callback=onPaletteRangeChange)

		self.widgets.log_colormapper = CreateCheckBox(name="Log", value=False, callback=self.setLogColorMapper)

		self.widgets.timestep = CreateFloatSlider(name='Time', value=0, start=0, end=1, step=1.0, editable=True, sizing_mode='stretch_width', callback=self.setTimestep)
		self.widgets.timestep_delta = CreateSelect(name="Speed", options=["1x", "2x", "4x", "8x", "16x", "32x", "64x", "128x"], value="1x", width=100, callback=lambda new: self.setTimestepDelta(self.speedFromOption(new)))
		self.widgets.field = CreateSelect(name='Field', options=[], value='data', callback=self.setField)
		self.widgets.direction = CreateSelect(name='Direction', options={'X':0, 'Y':1, 'Z':2}, value='Z', width=70, callback=lambda new: self.setDirection(new))
		self.widgets.offset = CreateFloatSlider(name="offset", start=0.0, end=1024.0, step=1.0, value=0.0, editable=True,  callback=self.setOffset, sizing_mode="stretch_width")
		self.widgets.num_refinements = CreateIntSlider(name='#Ref', value=0, start=0, end=4, editable=False, width=60, callback=self.setNumberOfRefinements)
		self.widgets.resolution = CreateIntSlider(name='Res', value=21, start=self.start_resolution, editable=False, end=99, width=80, callback=self.setResolution)
		self.widgets.view_dep = CreateCheckBox(name="Auto Res", value=True, callback=lambda new: self.setViewDependent(new))

		# status_bar
		self.widgets.status_bar = {}
		self.widgets.status_bar["request" ] = CreateTextInput(name="", sizing_mode='stretch_width', disabled=False)
		self.widgets.status_bar["response"] = CreateTextInput(name="", sizing_mode='stretch_width', disabled=False)

		# play time
		self.play = types.SimpleNamespace()
		self.play.is_playing = False
		self.widgets.play_button = CreateButton(name="Play", sizing_mode='stretch_height', callback=self.togglePlay)
		self.widgets.play_sec = CreateSelect(name="Frame delay", options=["0.00", "0.01", "0.1", "0.2", "0.1", "1", "2"], value="0.01", width=120)

		# metadata
		self.widgets.metadata = pn.Column(sizing_mode='stretch_both')
		self.widgets.metadata.visible = False

		self.widgets.show_metadata = CreateButton(name="Metadata", callback=self.onShowMetadataClick)

		self.widgets.logout = CreateButton(name="Logout")
		self.widgets.logout.js_on_click(code="""window.location=window.location.href + "/logout" """)

		self.idle_callback = None
		self.color_bar = None

	# onOffsetChange
	def onOffsetChange(self, attr, old, new):
		if old == new: return
		self.setOffset(new)

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
		self.widgets.datasets.disabled = value
		self.widgets.palette.disabled = value
		self.widgets.timestep.disabled = value
		self.widgets.timestep_delta.disabled = value
		self.widgets.field.disabled = value
		self.widgets.direction.disabled = value
		self.widgets.offset.disabled = value
		self.widgets.num_refinements.disabled = value
		self.widgets.resolution.disabled = value
		self.widgets.view_dep.disabled = value
		self.widgets.status_bar["request"].disabled = value
		self.widgets.status_bar["response"].disabled = value
		self.widgets.play_button.disabled = value
		self.widgets.play_sec.disabled = value

		for it in self.slices:
			it.setWidgetsDisabled(value)

		# refresh (to override if needed)

	def refresh(self):
		for it in self.slices:
			it.refresh()

	# getPointDim
	def getPointDim(self):
		return self.db.getPointDim() if self.db else 2

	# gotoPoint
	def gotoPoint(self, p):
		for it in self.slices:
			it.gotoPoint(p)

	# loadConfig
	def loadConfig(self, value):

		assert(isinstance(value,str) ) 
		url=value

		# remote file (maybe I need to setup credentials)
		if value.startswith("http"):
			url=value
			username = os.environ.get("MODVISUS_USERNAME", "")
			password = os.environ.get("MODVISUS_PASSWORD", "")
			auth = None
			if username and password: auth = HTTPBasicAuth(username, password) if username else None
			response = requests.get(url, auth=auth)
			body = response.body.decode('utf-8') 
		elif os.path.isfile(value):
			url=value
			with open(url, "r") as f: body=f.read()
		else:
			body=value

		return json.loads(body) if body else {}
		 
		
		# getConfig
	def getConfig(self):
		return self.config

	# setConfig
	def setConfig(self, value):
		if value is None:  return
		logger.info(f"[{self.id}] setConfig value={str(value)[0:80]}...")

		if not isinstance(value,dict):
			value=self.loadConfig(value)
	
		assert(isinstance(value,dict))
		self.config = value
		self.setDatasets([it["name"] for it in value.get("datasets",[])])

		for it in self.slices:
			it.setConfig(value)

	# setDatasets
	def setDatasets(self,value):
		self.widgets.datasets.options = value

	# getDatasets
	def getDatasets(self):
		return self.widgets.datasets.options

	# getLogicToPhysic
	def getLogicToPhysic(self):
		return self.logic_to_physic

	# setLogicToPhysic
	def setLogicToPhysic(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.logic_to_physic = value
		for it in self.slices:
			it.setLogicToPhysic(value)
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
	# getDataset
	def getDataset(self):
		return self.widgets.datasets.value

	# setDataset
	def setDataset(self, name, db=None, force=False):

		logger.info(f"[{self.id}] setDataset name={name} force={force}")

		# useless call
		if not force and self.getDataset() == name:
			return


		config=[it for it in self.config.get("datasets",[]) if it['name']==name]
		if len(config):
			config=config[0]
		else:
			config={"name": name, "url": name}

		self.widgets.datasets.value = name
		# self.doc.title = f"ViSUS {name}"

		self.db=self.loadDataset(config["url"], config) if db is None else db
		self.access = self.db.createAccess()
		for it in self.slices:
			it.setDataset(name, db=self.db)

		self.setStatus(config)


	# loadDataset
	def loadDataset(self, url, config={}):

		# special case, I want to force the dataset to be local (case when I have a local dashboards and remove dashboards)
		if "urls" in config and "--prefer" in sys.argv:
			prefer = sys.argv[sys.argv.index("--prefer") + 1]
			for it in config["urls"]:
				if it["id"] == prefer:
					url = it["url"]
					logger.info(f"Overriding url from {it}")
					break

		logger.info(f"Loading dataset url={url}")
		return LoadDataset(url=url)

	# getStatus
	def getStatus(self):

		return dict(
			timesteps=self.getTimesteps(),
			timestep_delta=self.getTimestepDelta(),
			timestep=self.getTimestep(),
			directions=self.getDirections(),
			physic_box=self.getPhysicBox(),
			fields=self.getFields(),
			field=self.getField(),
			direction=self.getDirection(),
			view_dep=self.getViewDependent(),
			resolution=self.getResolution(),
			palette=self.getPalette(),
			palette_range=self.getPaletteRange(),
			palette_medatadata_range=self.getMetadataPaletteRange(),
			palette_range_mode=self.getPaletteRangeMode(),
			log_colormapper=self.isLogColorMapper(),
			num_refinements=self.getNumberOfRefinements()
		)

	# guessInitialStatus
	def setStatus(self, config):

		# read the configuration and guess values if needed
		pdim = self.getPointDim()
		timesteps = self.db.getTimesteps()
		timestep_delta = int(config.get("timestep-delta", 1))
		timestep = int(config.get("timestep", timesteps[0]))
		physic_box = self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
		physic_box = [(float(physic_box[I]), float(physic_box[I + 1])) for I in range(0, pdim * 2, 2)]

		directions = self.db.inner.idxfile.axis.strip().split()
		if not directions: 
			directions = {'X':0,'Y':1,'Z':2}
		else:
			directions = {name: I for I, name in enumerate(directions)}

		view_dep = bool(config.get('view-dep', True))
		resolution = int(config.get("resolution", self.db.getMaxResolution() - 6))
		pdim = self.db.getPointDim()
		fields = self.db.getFields()
		field = self.db.getField(config.get("field", self.db.getField().name))
		dtype_range = field.getDTypeRange()
		dtype_vmin, dtype_vmax = dtype_range.From, dtype_range.To
		palette = config.get("palette", "Viridis256")
		palette_range = config.get("palette-range", None)
		palette_range,palette_range_mode=([dtype_vmin, dtype_vmax],"dynamic-acc") if palette_range is None else [palette_range,"user"]
		log_colormapper = config.get("log-colormapper", False)
		num_refinements = int(config.get("num-refinements", 2))
		metadata=config.get("metadata", None)
	
		# setting the status
		self.setTimesteps(timesteps)
		self.setTimestepDelta(timestep_delta)
		self.setTimestep(timestep)
		self.setDirections(directions)
		self.setPhysicBox(physic_box)
		self.setFields(fields)
		self.setField(field.name)
		self.setDirection(2)
		self.setViewDependent(view_dep)
		self.setResolution(resolution)
		self.setPalette(palette)
		self.setMetadataPaletteRange([dtype_vmin, dtype_vmax])
		self.setPaletteRange(palette_range)
		self.setPaletteRangeMode(palette_range_mode)
		self.setLogColorMapper(log_colormapper)
		self.setNumberOfRefinements(num_refinements)
		self.setMetadata(metadata)
		self.refresh()		

	# loadMetadata
	def setMetadata(self,value):

		if value is None:
			return

		tabs = pn.Tabs()
		for T, item in enumerate(value):

			type = item["type"]
			filename = item.get("filename",f"metadata_{T:02d}.bin")

			if type == "b64encode":
				# binary encoded in string
				base64_s = item["encoded"]

				try:
					body_s = base64.b64decode(base64_s).decode("utf-8")
				except:
					body_s = ""  # it's probably full binary
			else:
				# json
				body_s = json.dumps(item, indent=2)
				base64_s = base64.b64encode(bytes(body_s, 'utf-8')).decode('utf-8')

			base64_s = 'data:application/octet-stream;base64,' + base64_s

			# download button
			download_button = CreateButton(name="download")
			download_button.js_on_click(args=dict(base64_s=base64_s, filename=filename), code="""
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
					""")

			tabs.append([f"{T}",
				pn.Column(
					pn.pane.HTML(f"<b><pre><code>{filename}</code></pre></b>"),
					download_button,
					pn.pane.HTML(f"<div><pre><code>{body_s}</code></pre></div>")
				)
			])

		ReplaceContent(self.widgets.metadata,[tabs])


	# getTimesteps
	def getTimesteps(self):
		try:
			return [int(value) for value in self.db.db.getTimesteps().asVector()]
		except:
			return []

	# setTimesteps
	def setTimesteps(self, value):
		logger.info(f"[{self.id}] start={value[0]} end={value[-1]}")
		self.widgets.timestep.start = value[0]
		self.widgets.timestep.end = value[-1]
		self.widgets.timestep.step = 1

	# speedFromOption
	def speedFromOption(self, option):
		return (int(option[:-1]))

	# optionFromSpeed
	def optionFromSpeed(self, speed):
		return (str(speed) + "x")

	# getTimestepDelta
	def getTimestepDelta(self):
		return self.speedFromOption(self.widgets.timestep_delta.value)

	# setTimestepDelta
	def setTimestepDelta(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.timestep_delta.value = self.optionFromSpeed(value)
		self.widgets.timestep.step = value
		A = self.widgets.timestep.start
		B = self.widgets.timestep.end
		T = self.getTimestep()
		T = A + value * int((T - A) / value)
		T = min(B, max(A, T))
		self.setTimestep(T)

		for it in self.slices:
			it.setTimestepDelta(value)

		self.refresh()

	# getTimestep
	def getTimestep(self):
		return int(self.widgets.timestep.value)

	# setTimestep
	def setTimestep(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.timestep.value = value
		for it in self.slices:
			it.setTimestep(value)
		self.refresh()

	# getFields
	def getFields(self):
		return self.widgets.field.options

	# setFields
	def setFields(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.field.options = list(value)

	# getField
	def getField(self):
		return str(self.widgets.field.value)

	# setField
	def setField(self, value):
		logger.info(f"[{self.id}] value={value}")
		if value is None: return
		self.widgets.field.value = value
		for it in self.slices:
			it.setField(value)
		self.refresh()

	# getPalette
	def getPalette(self):
		return self.widgets.palette.value

	# setPalette
	def setPalette(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.palette.value = value
		for it in self.slices:
			it.setPalette(value)
		self.color_bar=None
		self.refresh()

	# getMetadataPaletteRange
	def getMetadataPaletteRange(self):
		return self.metadata_palette_range

	# setMetadataPaletteRange
	def setMetadataPaletteRange(self, value):
		vmin, vmax = value
		self.metadata_palette_range = [vmin, vmax]
		for it in self.slices:
			it.setMetadataPaletteRange(value)
		self.color_map=None
		self.refresh()

	# getPaletteRangeMode
	def getPaletteRangeMode(self):
		return self.widgets.palette_range_mode.value

	# setPaletteRangeMode
	def setPaletteRangeMode(self, mode):
		logger.info(f"[{self.id}] mode={mode} ")
		self.widgets.palette_range_mode.value = mode

		wmin = self.widgets.palette_range_vmin
		wmax = self.widgets.palette_range_vmax

		if mode == "metadata":
			wmin.value = self.metadata_palette_range[0]
			wmax.value = self.metadata_palette_range[1]

		if mode == "dynamic-acc":
			wmin.value = float('+inf')
			wmax.value = float('-inf')

		wmin.disabled = False if mode == "user" else True
		wmax.disabled = False if mode == "user" else True

		for it in self.slices:
			it.setPaletteRangeMode(mode)

		self.color_map=None
		self.refresh()

	# getPaletteRange
	def getPaletteRange(self):
		return [
			cdouble(self.widgets.palette_range_vmin.value),
			cdouble(self.widgets.palette_range_vmax.value),
		]

	# setPaletteRange (backward compatible)
	def setPaletteRange(self, value):
		vmin, vmax = value
		self.widgets.palette_range_vmin.value = vmin
		self.widgets.palette_range_vmax.value = vmax
		for it in self.slices:
			it.setPaletteRange(value)
		self.color_map=None
		self.refresh()

	# isLogColorMapper
	def isLogColorMapper(self):
		return self.widgets.log_colormapper

	# setLogColorMapper
	def setLogColorMapper(self, value):
		logger.info(f"[{self.id}] value={value}")
		palette = self.getPalette()
		vmin, vmax = self.getPaletteRange()
		self.widgets.log_colormapper.value = value
		for it in self.slices:
			it.setLogColorMapper(value)
		self.color_bar=None # force refresh
		self.refresh()

	# getNumberOfRefinements
	def getNumberOfRefinements(self):
		return self.widgets.num_refinements.value

	# setNumberOfRefinements
	def setNumberOfRefinements(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.num_refinements.value = value
		for it in self.slices:
			it.setNumberOfRefinements(value)
		self.refresh()

	# getResolution
	def getResolution(self):
		return self.widgets.resolution.value

	# getMaxResolution
	def getMaxResolution(self):
		return self.db.getMaxResolution()

	# setResolution
	def setResolution(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.resolution.start = self.start_resolution
		self.widgets.resolution.end   = self.db.getMaxResolution()
		value = Clamp(value, 0, self.widgets.resolution.end)
		self.widgets.resolution.value = value
		for it in self.slices:
			it.setResolution(value)
		self.refresh()

	# isViewDependent
	def isViewDependent(self):
		return self.widgets.view_dep.value

	# setViewDependent
	def setViewDependent(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.view_dep.value = value
		self.widgets.resolution.name = "Max Res" if value else "Res"
		for it in self.slices:
			it.setViewDependent(value)
		self.refresh()

	# getDirections
	def getDirections(self):
		return self.widgets.direction.options

	# setDirections
	def setDirections(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.direction.options = value
		for it in self.slices:
			it.setDirections(value)

	# getDirection
	def getDirection(self):
		return int(self.widgets.direction.value)

	# setDirection
	def setDirection(self, value):
		logger.info(f"[{self.id}] value={value}")
		pdim = self.getPointDim()
		if pdim == 2: value = 2
		dims = [int(it) for it in self.db.getLogicSize()]
		self.widgets.direction.value = value

		# default behaviour is to guess the offset
		self.guessOffset()

		for it in self.slices:
			it.setDirection(value)

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

	# getOffsetStartEnd
	def getOffsetStartEnd(self):
		return self.widgets.offset.start, self.widgets.offset.end, self.widgets.offset.step

	# setOffsetStartEnd
	def setOffsetStartEndStep(self, value):
		A, B, step = value
		logger.info(f"[{self.id}] value={value}")
		self.widgets.offset.start, self.widgets.offset.end, self.widgets.offset.step = A, B, step
		for it in self.slices:
			it.setOffsetStartEndStep(value)

	# getOffset (in physic domain)
	def getOffset(self):
		return self.widgets.offset.value

	# setOffset (3d only) (in physic domain)
	def setOffset(self, value):
		logger.info(f"[{self.id}] new-value={value} old-value={self.getOffset()}")

		self.widgets.offset.value = value
		assert (self.widgets.offset.value == value)
		for it in self.slices:
			logging.info(f"[{self.id}] recursively calling setOffset({value}) for slice={it.id}")
			it.setOffset(value)
		self.refresh()

	# guessOffset
	def guessOffset(self):

		pdim = self.getPointDim()
		dir = self.getDirection()

		# 2d there is no direction
		if pdim == 2:
			assert dir == 2
			value = 0
			logging.info(f"[{self.id}] pdim==2 calling setOffset({value})")
			self.setOffsetStartEndStep([0, 0, 1])  # both extrema included
			self.setOffset(value)
		else:
			vt = [self.logic_to_physic[I][0] for I in range(pdim)]
			vs = [self.logic_to_physic[I][1] for I in range(pdim)]

			if all([it == 0 for it in vt]) and all([it == 1.0 for it in vs]):
				dims = [int(it) for it in self.db.getLogicSize()]
				value = dims[dir] // 2
				self.setOffsetStartEndStep([0, int(dims[dir]) - 1, 1])
				self.setOffset(value)
			else:
				A, B = self.getPhysicBox()[dir]
				value = (A + B) / 2.0
				self.setOffsetStartEndStep([A, B, 0])
				self.setOffset(value)

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
		logger.info(f"[{self.id}]::startPlay")
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
		logger.info(f"[{self.id}]::stopPlay")
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
		if (t2 - self.play.t1) < float(self.widgets.play_sec.value):
			return

		render_id = [self.render_id] + [it.render_id for it in self.slices]

		if self.play.wait_render_id is not None:
			if any([a < b for (a, b) in zip(render_id, self.play.wait_render_id) if a is not None and b is not None]):
				# logger.info(f"Waiting render {render_id} {self.play.wait_render_id}")
				return

		# advance
		T = self.getTimestep() + self.getTimestepDelta()

		# reached the end -> go to the beginning?
		if T >= self.widgets.timestep.end:
			T = self.timesteps.widgets.timestep.start

		logger.info(f"[{self.id}]::playing timestep={T}")

		# I will wait for the resolution to be displayed
		self.play.wait_render_id = [(it + 1) if it is not None else None for it in render_id]
		self.play.t1 = time.time()
		self.setTimestep(T)

# ////////////////////////////////////////////////////////////////////////////////////
class Slice(Widgets):
	
	# constructor
	def __init__(self, parent=None):

		super().__init__(parent=parent)
		self.show_options  = ["palette","timestep","field","direction","offset","view_dep","resolution"]

		# create Gui
		self.t1=time.time()
		self.render_id     = 0
		self.aborted       = Aborted()
		self.new_job       = False
		self.current_img   = None
		self.last_query_logic_box = None
		self.query_node=QueryNode()
		self.canvas = Canvas(self.id)
		self.canvas.on_resize=self.onCanvasResize
		self.canvas.enableDoubleTap(self.onDoubleTap)


	# getShowOptions
	def getShowOptions(self):
		return self.show_options

	# setShowOptions
	def setShowOptions(self,value):
		self.show_options=value
		self.createGui()

	# createGui 
	def createGui(self):

		while len(self.main_layout):
			self.main_layout.pop(0)

		self.main_layout.append(pn.Column(
			pn.Row(
				*[getattr(self.widgets,it.replace("-","_")) for it in self.show_options ],
					sizing_mode="stretch_width"),
			pn.Row(
				self.canvas.main_layout, 
				self.widgets.metadata, 
				sizing_mode='stretch_both'),
			pn.Row(
				self.widgets.status_bar["request"],
				self.widgets.status_bar["response"], 
				sizing_mode='stretch_width'
			),
			sizing_mode="stretch_both"))

	# onDoubleTap (NOTE: x,y are in physic coords)
	def onDoubleTap(self,x,y):
		if False: 
			self.gotoPoint([x,y])

	# onCanvasResize
	def onCanvasResize(self):
		if not self.db: return
		dir=self.getDirection()
		offset=self.getOffset()
		self.setDirection(dir)
		self.setOffset(offset)

	# refresh
	def refresh(self):
		super().refresh()
		self.aborted.setTrue()
		self.new_job=True
  
	# getQueryLogicBox
	def getQueryLogicBox(self):
		(x1,x2),(y1,y2)=self.canvas.getViewport()
		return self.toLogic([(x1,y1),(x2,y2)])

	# setQueryLogicBox (NOTE: it ignores the coordinates on the direction)
	def setQueryLogicBox(self,value,):
		logger.info(f"[{self.id}] value={value}")
		proj=self.toPhysic(value) 
		x1,y1=proj[0]
		x2,y2=proj[1]
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

	# setDirection
	def setDirection(self,dir):
		super().setDirection(dir)
		dims=[int(it) for it in self.db.getLogicSize()]
		self.setQueryLogicBox(([0]*self.getPointDim(),dims))
		self.refresh()
  

	# setAccess
	def setAccess(self, value):
		self.access=value
		self.refresh()

  # gotoPoint
	def gotoPoint(self,point):
		assert(False) # not sure if point is in physic or logic corrdinates (I think physic)
		logger.info(f"[{self.id}] point={point}")
		pdim=self.getPointDim()
		# go to the slice
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

		logger.info(f"[{self.id}] ENTER")

		data=result['data']
		try:
			data_range=np.min(data),np.max(data)
		except:
			data_range=0.0,0.0

		logic_box=result['logic_box'] 

		# depending on the palette range mode, I need to use different color mapper low/high
		mode=self.getPaletteRangeMode()

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
				self.widgets.palette_range_vmin.value = data_range[0]
				self.widgets.palette_range_vmax.value = data_range[1]
				
			# in data accumulation mode I am accumulating the range
			if mode=="dynamic-acc":
				self.widgets.palette_range_vmin.value = min(self.widgets.palette_range_vmin.value, data_range[0])
				self.widgets.palette_range_vmax.value = max(self.widgets.palette_range_vmax.value, data_range[1])

			# update the color bar
			low =cdouble(self.widgets.palette_range_vmin.value)
			high=cdouble(self.widgets.palette_range_vmax.value)

		# regenerate colormap
		if self.color_bar is None:
			is_log=self.isLogColorMapper()
			palette=self.getPalette()
			palette = getattr(colorcet.palette, palette[len("colorcet."):]) if palette.startswith("colorcet.") else palette
			mapper_low =max(self.epsilon, low ) if is_log else low
			mapper_high=max(self.epsilon, high) if is_log else high
			from bokeh.models import LinearColorMapper, LogColorMapper, ColorBar
			self.color_bar = ColorBar(color_mapper = 
				LogColorMapper   (palette=palette, low=mapper_low, high=mapper_high) if is_log else 
				LinearColorMapper(palette=palette, low=mapper_low, high=mapper_high)
			)

			if hasattr(self,"probe_fig"):
				self.probe_fig.y_range.start = mapper_low
				self.probe_fig.y_range.end   = mapper_high

		logger.info(f"[{self.id}]::rendering result data.shape={data.shape} data.dtype={data.dtype} logic_box={logic_box} data-range={data_range} palette-range={[low,high]}")

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
		
		logger.info(f"[{self.id}] EXIT")
  
	# pushJobIfNeeded
	def pushJobIfNeeded(self):

		canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
		query_logic_box=self.getQueryLogicBox()
		offset=self.getOffset()
		pdim=self.getPointDim()
		if not self.new_job and str(self.last_query_logic_box)==str(query_logic_box):
			return

		logger.info(f"[{self.id}] pushing new job query_logic_box={query_logic_box}...")

		# abort the last one
		self.aborted.setTrue()
		self.query_node.waitIdle()
		num_refinements = self.getNumberOfRefinements()
		if num_refinements==0:
			num_refinements=3 if pdim==2 else 4
		self.aborted=Aborted()

		resolution=self.getResolution()
		
		# I will use max_pixels to decide what resolution, I am using resolution just to add/remove a little the 'quality'
		if self.isViewDependent():
			endh=None 
			canvas_w,canvas_h=(self.canvas.getWidth(),self.canvas.getHeight())
			max_pixels=canvas_w*canvas_h
			delta=resolution-self.getMaxResolution()
			if resolution<self.getMaxResolution():
				max_pixels=int(max_pixels/pow(1.3,abs(delta))) # decrease 
			elif resolution>self.getMaxResolution():
				max_pixels=int(max_pixels*pow(1.3,abs(delta))) # increase 
		else:
			# I am not using the information about the pixel on screen
			max_pixels=None
			endh=resolution
		
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
		self.last_query_logic_box=query_logic_box
		self.new_job=False

		logger.info(f"[{self.id}] pushed new job query_logic_box={query_logic_box}")

		# link views
		if self.isLinked() and self.parent:
			idx=self.parent.slices.index(self)
			for it in self.parent.slices:
				if it==self: continue
				it.setQueryLogicBox(query_logic_box)
				it.setOffset(offset)




# //s////////////////////////////////////////////////////////////////////////////////////
class Probe:

	# constructor
	def __init__(self):
		self.pos = None
		self.enabled = True

# //////////////////////////////////////////////////////////////////////////////////////
class ProbeTool(Slice):
	colors = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"]

	# constructor
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.show_options.append("show-probe")

		N = len(self.colors)

		self.probes = {}
		self.renderers = {
			"offset": None
		}
		for dir in range(3):
			self.probes[dir] = []
			for I in range(N):
				probe = Probe()
				self.probes[dir].append(probe)
				self.renderers[probe] = {
					"canvas": [],
					"fig": []
				}

		self.slot = None
		self.button_css = [None] * N

		# create buttons
		self.buttons = []
		for slot, color in enumerate(self.colors):
			self.buttons.append(CreateButton(name=color, sizing_mode="stretch_width", callback=lambda slot=slot:self.onButtonClick(slot)))

		vmin, vmax = self.getPaletteRange()

		self.widgets.show_probe = CreateButton(name="Probe", callback=self.toggleProbeVisibility)

		self.probe_fig = bokeh.plotting.figure(
			title=None,
			x_axis_label="Z", x_axis_type="linear",
			y_axis_label="f", y_axis_type="log" if self.isLogColorMapper() else "linear",
			x_range=[0.0, 1.0],
			y_range=[0.0, 1.0],
			sizing_mode="stretch_both",
			active_scroll="wheel_zoom",
			toolbar_location=None,
		)

		# change the offset on the proble plot (NOTE evt.x in is physic domain)
		self.probe_fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))

		self.probe_fig_col = pn.Column(
			pn.pane.Bokeh(self.probe_fig), 
			sizing_mode='stretch_both')

		# probe XY space
		if True:
			# where the center of the probe (can be set by double click or using this)
			self.slider_x_pos = CreateFloatSlider(name="X coordinate", value=0.0, start=0.0, end=1.0, step=1.0, editable=True, sizing_mode="stretch_width", 
																								 callback=lambda new: self.onProbeXYChange(), 
																								 parameter_name="value_throttled")

			self.slider_y_pos = CreateFloatSlider(name="Y coordinate",value=0, start=0, end=1, step=1, editable=True, sizing_mode="stretch_width", 
																								 callback=lambda new: self.onProbeXYChange(), 
																								 parameter_name="value_throttled")

			self.slider_num_points_x = CreateIntSlider(name="#x", start=1, end=8, step=1, value=2, editable=False, width=60, callback=self.recompute, parameter_name='value_throttled')
			self.slider_num_points_y = CreateIntSlider(name="#y", start=1, end=8, step=1, value=2, editable=False, width=60, callback=self.recompute, parameter_name='value_throttled')

		# probe Z space
			self.slider_z_range = CreateFloatRangeSlider(name="Range", start=0.0, end=1.0, value=(0.0, 1.0), editable=True, sizing_mode="stretch_width", callback=self.recompute)

		# probe z res
		self.slider_z_res = CreateIntSlider(name="Res", start=self.start_resolution, end=99, step=1, value=24, editable=False, width=80, callback=self.recompute, parameter_name='value_throttled')

		# Z op
		self.slider_z_op = CreateRadioButtonGroup(name="", options=["avg", "mM", "med", "*"], value=0, callback=self.recompute)

		self.probe_layout = pn.Column(
			pn.Row(
				self.slider_x_pos,
				self.slider_y_pos,
				self.slider_z_range,
				self.slider_z_op,
				self.slider_z_res,
				self.slider_num_points_x,
				self.slider_num_points_y,
				sizing_mode="stretch_width"
			),
			pn.Row(*[button for button in self.buttons], sizing_mode="stretch_width"),
			self.probe_fig_col,
			sizing_mode="stretch_both"
		)
		self.probe_layout.visible = False

	# removeRenderer
	def removeRenderer(self, target, value):
		if value in target.renderers:
			target.renderers.remove(value)

	# setLogColorMapper
	def setLogColorMapper(self, value):
		super().setLogColorMapper(value)

		# need to recomute to create a brand new figure (because Bokeh cannot change the type of Y axis)
		old_probe_fig = self.probe_fig
		self.probe_fig = bokeh.plotting.figure(
			title=None,
			x_axis_label="Z",
			y_axis_label="f", y_axis_type="log" if value else "linear",
			x_range=[0.0, 1.0],
			y_range=[0.0, 1.0],
			sizing_mode="stretch_both",
			active_scroll="wheel_zoom",
			toolbar_location=None,
		)
		self.probe_fig.on_event(DoubleTap, lambda evt: self.setOffset(evt.x))
		ReplaceContent(self.probe_fig_col,[self.probe_fig])
		self.recompute()

	# onProbeXYChange
	def onProbeXYChange(self):
		dir = self.getDirection()
		slot = self.slot
		if slot is None: return
		probe = self.probes[dir][slot]
		probe.pos = (self.slider_x_pos.value, self.slider_y_pos.value)
		self.addProbe(probe)

	# isProbeVisible
	def isProbeVisible(self):
		return self.probe_layout.visible

	# setProbeVisible
	def setProbeVisible(self, value):
		self.probe_layout.visible = value

	# toggleProbeVisibility
	def toggleProbeVisibility(self):
		value = not self.isProbeVisible()
		self.setProbeVisible(value)
		self.recompute()

	# onDoubleTap
	def onDoubleTap(self, x, y):
		logger.info(f"[{self.id}] x={x} y={y}")
		dir = self.getDirection()
		slot = self.slot
		if slot is None: slot = 0
		probe = self.probes[dir][slot]
		probe.pos = [x, y]
		self.addProbe(probe)

	# setDataset
	def setDataset(self, name, db=None, force=False):
		super().setDataset(name, db=db, force=force)
		if self.db:
			self.slider_z_res.end = self.db.getMaxResolution()

	# createGui
	def createGui(self):
		super().createGui()
		self.main_layout.append(self.probe_layout)

	# setDirection
	def setDirection(self, dir):
		super().setDirection(dir)

		pbox = self.getPhysicBox()
		pdim=self.getPointDim()
		logger.info(f"[{self.id}] physic-box={pbox} pdim={pdim}")
	
		(X, Y, Z), titles = self.getLogicAxis()

		X1,X2=(pbox[X][0],pbox[X][1])
		Y1,Y2=(pbox[Y][0],pbox[Y][1])
		Z1,Z2=(pbox[Z][0],pbox[Z][1]) if pdim==3 else (0,1)

		self.slider_x_pos.name = titles[0]
		self.slider_x_pos.start = X1
		self.slider_x_pos.end   = X2
		self.slider_x_pos.step  = (X2 - X1) / 10000
		self.slider_x_pos.value  = X1

		self.slider_y_pos.name = titles[1]
		self.slider_y_pos.start = Y1
		self.slider_y_pos.end   = Y2
		self.slider_y_pos.step  = (Y2 - Y1) / 10000
		self.slider_y_pos.value = Y1

		self.slider_z_range.name = titles[2]
		self.slider_z_range.start = Z1 
		self.slider_z_range.end   = Z2
		self.slider_z_range.step  = (Z2 - Z1) / 10000
		self.slider_z_range.value = (Z1, Z2)

		self.guessOffset()
		self.recompute()
		self.slot = None

	# setOffset
	def setOffset(self, value):

		# do not send float offset if it's all integer
		if all([int(it) == it for it in self.getOffsetStartEnd()]):
			value = int(value)

		super().setOffset(value)
		self.refreshProbe()

	# onButtonClick
	def onButtonClick(self, slot):
		dir = self.getDirection()
		probe = self.probes[dir][slot]
		logger.info(
			f"[{self.id}] slot={slot} self.slot={self.slot} probe.pos={probe.pos} probe.enabled={probe.enabled}")

		# when I click on the same slot, I am disabling the probe
		if self.slot == slot:
			self.removeProbe(probe)
			self.slot = None
		else:
			# when I click on a new slot..
			self.slot = slot

			# automatically enable a disabled probe
			if not probe.enabled and probe.pos is not None:
				self.addProbe(probe)

		self.refreshProbe()

	# findProbe
	def findProbe(self, probe):
		for dir in range(3):
			for slot in range(len(self.colors)):
				if self.probes[dir][slot] == probe:
					return dir, slot
		return None

	# addProbe
	def addProbe(self, probe):
		dir, slot = self.findProbe(probe)
		logger.info(f"[{self.id}] dir={dir} slot={slot} probe.pos={probe.pos}")
		self.removeProbe(probe)
		probe.enabled = True

		vt = [self.logic_to_physic[I][0] for I in range(3)]
		vs = [self.logic_to_physic[I][1] for I in range(3)]

		def LogicToPhysic(P):
			ret = [vt[I] + vs[I] * P[I] for I in range(3)]
			last = ret[dir]
			del ret[dir]
			ret.append(last)
			return ret

		def PhysicToLogic(p):
			ret = [it for it in p]
			last = ret[2]
			del ret[2]
			ret.insert(dir, last)
			return [(ret[I] - vt[I]) / vs[I] for I in range(3)]

		# __________________________________________________________
		# here is all in physical coordinates
		assert (probe.pos is not None)
		x, y = probe.pos
		z1, z2 = self.slider_z_range.value
		p1 = (x, y, z1)
		p2 = (x, y, z2)

		# logger.info(f"Add Probe vs={vs} vt={vt} p1={p1} p2={p2}")

		# automatically update the XY slider values
		self.slider_x_pos.value = x
		self.slider_y_pos.value = y

		# keep the status for later

		# __________________________________________________________
		# here is all in logical coordinates
		# compute x1,y1,x2,y2 but eigther extrema included (NOTE: it's working at full-res)

		# compute delta
		Delta = [1, 1, 1]
		endh = self.slider_z_res.value
		maxh = self.db.getMaxResolution()
		bitmask = self.db.getBitmask()
		for K in range(maxh, endh, -1):
			Delta[ord(bitmask[K]) - ord('0')] *= 2

		P1 = PhysicToLogic(p1)
		P2 = PhysicToLogic(p2)
		# print(P1,P2)

		# align to the bitmask
		(X, Y, Z), titles = self.getLogicAxis()

		def Align(idx, p):
			return int(Delta[idx] * (p[idx] // Delta[idx]))

		P1[X] = Align(X, P1)
		P2[X] = Align(X, P2) + (self.slider_num_points_x.value) * Delta[X]

		P1[Y] = Align(Y, P1)
		P2[Y] = Align(Y, P2) + (self.slider_num_points_y.value) * Delta[Y]

		P1[Z] = Align(Z, P1)
		P2[Z] = Align(Z, P2) + Delta[Z]

		logger.info(f"Add Probe aligned is P1={P1} P2={P2}")

		# invalid query
		if not all([P1[I] < P2[I] for I in range(3)]):
			return

		color = self.colors[slot]

		# for debugging draw points
		if True:
			xs, ys = [[], []]
			for _Z in range(P1[2], P2[2], Delta[2]) if dir != 2 else (P1[2],):
				for _Y in range(P1[1], P2[1], Delta[1]) if dir != 1 else (P1[1],):
					for _X in range(P1[0], P2[0], Delta[0]) if dir != 0 else (P1[0],):
						x, y, z = LogicToPhysic([_X, _Y, _Z])
						xs.append(x)
						ys.append(y)

			x1, x2 = min(xs), max(xs);
			cx = (x1 + x2) / 2.0
			y1, y2 = min(ys), max(ys);
			cy = (y1 + y2) / 2.0

			fig = self.canvas.getFigure()
			self.renderers[probe]["canvas"] = [
				fig.scatter(xs, ys, color=color),
				fig.line([x1, x2, x2, x1, x1], [y2, y2, y1, y1, y2], line_width=1, color=color),
				fig.line(self.getPhysicBox()[X], [cy, cy], line_width=1, color=color),
				fig.line([cx, cx], self.getPhysicBox()[Y], line_width=1, color=color),
			]

		# execute the query
		access = self.db.createAccess()
		logger.info(f"ExecuteBoxQuery logic_box={[P1, P2]} endh={endh} num_refinements={1} full_dim={True}")
		multi = ExecuteBoxQuery(self.db, access=access, logic_box=[P1, P2], endh=endh, num_refinements=1,
								full_dim=True)  # full_dim means I am not quering a slice
		data = list(multi)[0]['data']

		# render probe
		if dir == 2:
			xs = list(np.linspace(z1, z2, num=data.shape[0]))
			ys = []
			for Y in range(data.shape[1]):
				for X in range(data.shape[2]):
					ys.append(list(data[:, Y, X]))

		elif dir == 1:
			xs = list(np.linspace(z1, z2, num=data.shape[1]))
			ys = []
			for Z in range(data.shape[0]):
				for X in range(data.shape[2]):
					ys.append(list(data[Z, :, X]))

		else:
			xs = list(np.linspace(z1, z2, num=data.shape[2]))
			ys = []
			for Z in range(data.shape[0]):
				for Y in range(data.shape[1]):
					ys.append(list(data[Z, Y, :]))

		if True:
			op = self.slider_z_op.value

			if op == "avg":
				ys = [[mean(p) for p in zip(*ys)]]

			if op == "mM":
				ys = [
					[min(p) for p in zip(*ys)],
					[max(p) for p in zip(*ys)]
				]

			if op == "med":
				ys = [[median(p) for p in zip(*ys)]]

			if op == "*":
				ys = [it for it in ys]

			for it in ys:
				if self.isLogColorMapper():
					it = [max(self.epsilon, value) for value in it]
				self.renderers[probe]["fig"].append(
					self.probe_fig.line(xs, it, line_width=2, legend_label=color, line_color=color))

		self.refreshProbe()

	# removeProbe
	def removeProbe(self, probe):
		fig = self.canvas.getFigure()
		for r in self.renderers[probe]["canvas"]:
			self.removeRenderer(fig, r)
		self.renderers[probe]["canvas"] = []

		for r in self.renderers[probe]["fig"]:
			self.removeRenderer(self.probe_fig, r)
		self.renderers[probe]["fig"] = []

		probe.enabled = False
		self.refreshProbe()

	# refreshProbe
	def refreshProbe(self):

		dir = self.getDirection()

		# buttons
		if True:

			for slot, button in enumerate(self.buttons):
				color = self.colors[slot]
				probe = self.probes[dir][slot]

				css = [".bk-btn-default {"]

				if slot == self.slot:
					css.append("font-weight: bold;")
					css.append("border: 2px solid black;")

				if slot == self.slot or (probe.pos is not None and probe.enabled):
					css.append("background-color: " + color + " !important;")

				css.append("}")
				css = " ".join(css)

				if self.button_css[slot] != css:
					self.button_css[slot] = css
					button.stylesheets = [css]

			# X axis
		if True:
			z1, z2 = self.slider_z_range.value
			self.probe_fig.xaxis.axis_label = self.slider_z_range.name
			self.probe_fig.x_range.start = z1
			self.probe_fig.x_range.end = z2

		# draw figure line for offset
		if True:
			offset = self.getOffset()
			self.removeRenderer(self.probe_fig, self.renderers["offset"])
			self.renderers["offset"] = self.probe_fig.line(
				[offset, offset],
				[self.probe_fig.y_range.start, self.probe_fig.y_range.end],
				line_width=1, color="black")

	# recompute
	def recompute(self, evt=None):

		self.refreshProbe()

		# remove all old probes
		was_enabled = {}
		for dir in range(3):
			for probe in self.probes[dir]:
				was_enabled[probe] = probe.enabled
				self.removeProbe(probe)

		# restore enabled
		for dir in range(3):
			for probe in self.probes[dir]:
				probe.enabled = was_enabled[probe]

		# add the probes only if sibile
		if self.isProbeVisible():
			dir = self.getDirection()
			for slot, probe in enumerate(self.probes[dir]):
				if probe.pos is not None and probe.enabled:
					self.addProbe(probe)

	# gotNewData
	def gotNewData(self, result):
		super().gotNewData(result)
		self.refreshProbe()


# //////////////////////////////////////////////////////////////////////////////////////
class Slices(Slice):

	# constructor
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.show_options = ["palette", "timestep", "field", "view_dep", "resolution"]
		self.slice_show_options = ["direction", "offset", "view_dep"]
		self.widgets.view_mode = CreateSelect(name="view_mode", value="1",options=["1", "probe", "2", "2-linked", "4", "4-linked"],callback=self.setViewMode)

	# getShowOptions
	def getShowOptions(self):
		return [self.show_options, self.slice_show_options]

	# setShowOptions
	def setShowOptions(self, value):
		if isinstance(value, tuple) or isinstance(value, list):
			self.show_options, self.slice_show_options = value
		else:
			self.show_otions, self.slice_show_options = value, None


	# onIdle
	def onIdle(self):

		# not ready for jobs
		if not self.db:
			return

		try:
			for it in self.slices:
				# problem in pyodide, I will not get pixel size until I resize the window (remember)
				it.canvas.checkFigureResize()
				if it.canvas.getWidth()>0 and it.canvas.getHeight()>0:
					it.playNextIfNeeded()
					result=it.query_node.popResult(last_only=True) 
					if result is not None: 
						it.gotNewData(result)
					it.pushJobIfNeeded()

		except Exception as ex:
			logger.info(f"ERROR ex={ex}")

	# getMainLayout
	def createGui(self):

		for it in self.slices:
			it.aborted.setTrue()
			it.query_node.stop()	

		viewmode=self.getViewMode()
		if viewmode=="probe": viewmode="1-probe"
		nviews=int(viewmode[0:1])

		while len(self.main_layout):
			self.main_layout.pop(0)

		# remove all inner slices
		for it in self.slices:  del it
		self.slices=[]

		for I in range(nviews):
			options=[it for it in self.slice_show_options if nviews>1 or it not in ["datasets", "log_colormapper"]]
			slice = ProbeTool(parent=self)
			slice.setShowOptions(options)
			slice.config=self.getConfig()
			slice.setDatasets(self.getDatasets())
			slice.setDataset(self.getDataset(),force=True)
			slice.setLinked(I==0 and "linked" in viewmode)
			self.slices.append(slice)

		# TODO self.widgets.metadata

		self.main_layout.append(
				pn.Column(
					pn.Row(
						*[getattr(self.widgets, it.replace("-", "_")) for it in self.show_options],
						sizing_mode="stretch_width"
					), 
					pn.GridBox(
						*[it.main_layout for it in self.slices ], ncols=2 if nviews>1 else 1, 
						sizing_mode="stretch_both"), 
					sizing_mode='stretch_both' 
				))

		if IsPyodide():
			self.idle_callback = AddAsyncLoop(f"{self}::idle_callback", self.onIdle, 1000 // 30)
		else:
			self.idle_callback = pn.state.add_periodic_callback(self.onIdle, period=1000 // 30)

		for it in self.slices:
			it.query_node.start()

	# getViewMode
	def getViewMode(self):
		return self.widgets.view_mode.value

	# setViewMode
	def setViewMode(self, value):
		value=str(value).lower().strip()
		logger.info(f"[{self.id}] value={value}")
		self.createGui()

	# getMainLayout
	def getMainLayout(self):
		self.createGui()
		return self.main_layout

	# setNumberOfViews (backward compatible)
	def setNumberOfViews(self, value):
		self.setViewMode(str(value))
