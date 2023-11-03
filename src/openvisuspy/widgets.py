import base64
import types

import colorcet
import requests
from bokeh.models import Select, LinearColorMapper, LogColorMapper, ColorBar, Slider, TextInput, Row
from bokeh.models import TabPanel, Tabs, Button, Column, Div, Spinner
from bokeh.models.callbacks import CustomJS
from requests.auth import HTTPBasicAuth

from .backend import LoadDataset
from .utils import *

logger = logging.getLogger(__name__)

PALETTES = [
			   "Greys256",
			   "Inferno256",
			   "Magma256",
			   "Plasma256",
			   "Viridis256",
			   "Cividis256",
			   "Turbo256"
		   ] + [
			   it for it in [
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
			   if hasattr(colorcet, it[9:])
		   ]


# //////////////////////////////////////////////////////////////////////////////////////
class EditableSlider:

	# constructor
	def __init__(self, title='', value=0, start=0, end=1024, step=1, sizing_mode='stretch_width'):
		self.slider = Slider(title=title, value=value, start=start, end=end, step=step, sizing_mode=sizing_mode)
		self.slider._check_missing_dimension = None
		self.spinner = Spinner(title="", value=value, low=start, high=end, step=step, width=80, format="0.00")
		self.spinner.format = "0.00"
		self.slider.on_change("value", self.onValueChange)
		self.spinner.on_change("value", self.onValueChange)
		self.__value = value
		self.__start = start
		self.__end = end
		self.__step = step
		self.on_value_change = None

	# getMainLayout
	def getMainLayout(self):
		return Row(
			self.slider,
			self.spinner,
			sizing_mode=self.slider.sizing_mode)

	# onValueChange
	def onValueChange(self, attr, old, new):
		self.value = new

	@property
	def value(self):
		return self.__value

	@value.setter
	def value(self, new):
		if hasattr(self, "__changing_value") and self.__changing_value:  return
		old = self.__value
		self.__changing_value = True
		if old != new:
			self.__value = new
			self.slider.value = new
			self.spinner.value = new
			if self.on_value_change:
				self.on_value_change("value", old, new)
		self.__changing_value = False

	# on_change
	def on_change(self, evt, fn):
		assert (evt == 'value')
		self.on_value_change = fn

	@property
	def start(self):
		return self.__start

	@start.setter
	def start(self, value):
		self.__start = value
		self.slider.start = value
		self.spinner.low = value

	@property
	def end(self):
		return self.__end

	@end.setter
	def end(self, value):
		self.__end = value
		self.slider.end = value
		self.spinner.high = value

	@property
	def step(self):
		return self.__step

	@step.setter
	def step(self, value):
		self.__step = value
		self.slider.step = value
		self.spinner.step = value if value else 0.01  # TODO

	@property
	def disabled(self):
		return self.slider.disabled

	@disabled.setter
	def disabled(self, value):
		self.slider.disabled = value
		self.spinner.disabled = value

	@property
	def show_value(self):
		return self.slider.show_value

	@show_value.setter
	def show_value(self, value):
		self.slider.show_value = value

	@property
	def title(self):
		return self.slider.title

	@title.setter
	def title(self, value):
		self.slider.title = value


# //////////////////////////////////////////////////////////////////////////////////////
class Widgets:
	ID = 0

	epsilon = 0.001

	start_resolution = 20

	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None):

		if doc is None and not is_panel:
			import bokeh.io
			doc = bokeh.io.curdoc()

		assert (not isinstance(doc, list))

		self.is_panel = is_panel
		self.doc = doc
		self.parent = parent

		self.id = f"{type(self).__name__}/{Widgets.ID}"
		Widgets.ID += 1
		self.config = None
		self.db = None
		self.access = None
		self.render_id = None  # by default I am not rendering
		self.logic_to_physic = [(0.0, 1.0)] * 3
		self.children = []
		self.linked = False

		self.first_row_layout = Row(sizing_mode="stretch_width")

		self.widgets = types.SimpleNamespace()

		# datasets
		self.widgets.datasets = Select(title="Dataset", options=[], width=60)
		self.widgets.datasets.on_change("value", lambda attr, old, new: self.setDataset(new, force=True))

		# palette
		self.palette = 'Viridis256'
		self.widgets.palette = Select(title='Palette', options=PALETTES, value=self.palette)
		self.widgets.palette.on_change("value", lambda attr, old, new: self.setPalette(new))

		# palette range
		self.metadata_palette_range = [0.0, 255.0]
		self.widgets.palette_range_mode = Select(title="Range", options=["metadata", "user", "dynamic", "dynamic-acc"], value="metadata", width=80)
		self.widgets.palette_range_vmin = TextInput(title="Min", width=80)
		self.widgets.palette_range_vmax = TextInput(title="Max", width=80)

		self.widgets.palette_range_mode.on_change("value", lambda attr, old, new: self.setPaletteRangeMode(new))
		self.widgets.palette_range_vmin.on_change("value", lambda attr, old, new: self.onPaletteRangeChange())
		self.widgets.palette_range_vmax.on_change("value", lambda attr, old, new: self.onPaletteRangeChange())

		# color_bar
		self.color_bar = ColorBar()  # ticker=BasicTicker(desired_num_ticks=10)
		self.color_bar.color_mapper = LinearColorMapper()
		self.color_bar.color_mapper.palette = self.palette
		self.color_bar.color_mapper.low, self.color_bar.color_mapper.high = self.getPaletteRange()

		# color_mapper type
		self.widgets.colormapper_type = Select(title="Colormap", options=["linear", "log"], value='linear')
		self.widgets.colormapper_type.on_change("value", lambda attr, old, new: self.setColorMapperType(new))

		# timestep
		self.widgets.timestep = Slider(title='Time', value=0, start=0, end=1, sizing_mode='stretch_width')
		self.widgets.timestep._check_missing_dimension = None

		def onTimestepChange(attr, old, new):
			if old == new: return
			self.setTimestep(int(new))

		self.widgets.timestep.on_change("value", onTimestepChange)

		# timestep delta
		speed_options = ["1x", "2x", "4x", "8x", "16x", "32x", "64x", "128x"]
		self.widgets.timestep_delta = Select(title="Speed", options=speed_options, value=speed_options[0], width=100)
		self.widgets.timestep_delta.on_change("value",
											  lambda attr, old, new: self.setTimestepDelta(self.speedFromOption(new)))

		# field
		self.widgets.field = Select(title='Field', options=[], value='data')
		self.widgets.field.on_change("value", lambda attr, old, new: self.setField(new))

		# direction
		self.widgets.direction = Select(title='Direction', options=[('0', 'X'), ('1', 'Y'), ('2', 'Z')], value='2')
		self.widgets.direction.on_change("value", lambda attr, old, new: self.setDirection(int(new)))

		# offset
		self.widgets.offset = EditableSlider(title='Offset', value=0, start=0, end=1024, sizing_mode='stretch_width')
		self.widgets.offset.on_change("value", self.onOffsetChange)

		# num_refimements (0==guess)
		self.widgets.num_refinements = Slider(title='#Ref', value=0, start=0, end=4, width=60)
		self.widgets.num_refinements.on_change("value", lambda attr, old, new: self.setNumberOfRefinements(int(new)))
		self.widgets.num_refinements._check_missing_dimension = None  # patch

		# resolution
		self.widgets.resolution = Slider(title='Res', value=21, start=self.start_resolution, end=99, width=80)
		self.widgets.resolution.on_change("value", lambda attr, old, new: self.setResolution(int(new)))
		self.widgets.resolution._check_missing_dimension = None  # patch

		# view_dep
		self.widgets.view_dep = Select(title="Auto Res", options=[('1', 'Enabled'), ('0', 'Disabled')], value="True",
									   width=100)
		self.widgets.view_dep.on_change("value", lambda attr, old, new: self.setViewDependent(int(new)))

		# status_bar
		self.widgets.status_bar = {}
		self.widgets.status_bar["request"] = TextInput(title="", sizing_mode='stretch_width')
		self.widgets.status_bar["response"] = TextInput(title="", sizing_mode='stretch_width')
		self.widgets.status_bar["request"].disabled = True
		self.widgets.status_bar["response"].disabled = True

		# play time
		self.play = types.SimpleNamespace()
		self.play.is_playing = False
		self.widgets.play_button = Button(label="Play", width=80, sizing_mode='stretch_height')
		self.widgets.play_button.on_click(self.togglePlay)
		self.widgets.play_sec = Select(title="Frame delay", options=["0.00", "0.01", "0.1", "0.2", "0.1", "1", "2"],
									   value="0.01", width=120)

		# metadata
		self.widgets.metadata = Column(width=640, sizing_mode='stretch_both')
		self.widgets.metadata.visible = False

		self.widgets.show_metadata = Button(label="Metadata", width=80, sizing_mode='stretch_height')
		self.widgets.show_metadata.on_click(self.onShowMetadataClick)

		self.widgets.logout = Button(label="Logout", width=80, sizing_mode="stretch_height")
		self.widgets.logout.js_on_event("button_click", CustomJS(code="""window.location=window.location.href + "/logout" """))

		self.panel_layout = None
		self.idle_callback = None

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
	def setConfig(self, value, skip_set_dataset=False):
		if value is None: 
			return
		logger.info(f"[{self.id}] setConfig value={str(value)[0:30]}...")

		#is an JSON url
		if not isinstance(value,dict):
			
			assert(isinstance(value,str) ) 
			url=value

			# remote file (maybe I need to setup credentials)
			if url.startswith("http"):
				username = os.environ.get("MODVISUS_USERNAME", "")
				password = os.environ.get("MODVISUS_PASSWORD", "")
				auth = None
				if username and password: auth = HTTPBasicAuth(username, password) if username else None
				response = requests.get(url, auth=auth)
				body = response.body.decode('utf-8') 
			else:
				with open(url, "r") as f: body=f.read()
			value = json.loads(body) if body else {}

		if not "datasets" in value:
			value["datasets"]=[]

		assert(isinstance(value,dict))
		self.config = value
		self.datasets = {it["name"]: it for it in value["datasets"]}
		ordered_names = [it["name"] for it in value["datasets"]]
		self.widgets.datasets.options = ordered_names

		# recursive
		for it in self.children:
			it.setConfig(value, skip_set_dataset=skip_set_dataset)

		if ordered_names and not skip_set_dataset:
			self.setDataset(ordered_names[0])

	# getLogicToPhysic
	def getLogicToPhysic(self):
		return self.logic_to_physic

	# setLogicToPhysic
	def setLogicToPhysic(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.logic_to_physic = value
		for it in self.children:
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

	# pdim = self.db.getPointDim()
	# physic_box=self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
	# physic_box=[(float(physic_box[I]),float(physic_box[I+1])) for I in range(0,pdim*2,2)]
	# return physic_box

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

		logger.info(f"[{self.id}] setDataset name={name} force={force} current_dataset={self.getDataset()} ")

		# useless call
		if not force and self.getDataset() == name:
			return

		# automatically create a config
		if not self.config or not name in self.datasets:
			self.setConfig({"datasets": [{"name": name, "url": name}]}, skip_set_dataset=True)

		config = self.datasets[name]
		self.widgets.datasets.value = name
		self.doc.title = f"ViSUS {name}"

		if db is None:
			url = config["url"]

			# special case, I want to force the dataset to be local (case when I have a local dashboards and remove dashboards)
			logger.info(f"config={config}")
			if "urls" in config and "--prefer" in sys.argv:
				prefer = sys.argv[sys.argv.index("--prefer") + 1]
				for it in config["urls"]:
					if it["id"] == prefer:
						url = it["url"]
						logger.info(f"Overriding url from {it}")
						break

			logger.info(f"Loading dataset url={url}")
			self.db = LoadDataset(url=url)
		else:
			self.db = db

		self.access = self.db.createAccess()

		# avoid reloading db multiple times by specifying db
		for it in self.children:
			it.setDataset(name, db=self.db)

		pdim = self.db.getPointDim()

		# timestep
		timesteps = self.db.getTimesteps()
		timestep_delta = int(config.get("timestep-delta", 1))
		timestep = int(config.get("timestep", timesteps[0]))
		self.setTimesteps(timesteps)
		self.setTimestepDelta(timestep_delta)
		self.setTimestep(timestep)

		# axis
		axis = self.db.inner.idxfile.axis.strip().split()
		if not axis:
			axis = ["X", "Y", "Z"][0:pdim]
		axis = [(str(I), name) for I, name in enumerate(axis)]
		self.setDirections(axis)

		# physic box
		physic_box = self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
		physic_box = [(float(physic_box[I]), float(physic_box[I + 1])) for I in range(0, pdim * 2, 2)]
		self.setPhysicBox(physic_box)

		# field
		fields = self.db.getFields()
		default_fieldname = self.db.getField().name
		fieldname = config.get("field", default_fieldname)
		field = self.db.getField(fieldname)
		self.setFields(fields)
		self.setField(field.name)

		# direction
		self.setDirection(2)
		for I, it in enumerate(self.children):
			it.setDirection((I % 3) if pdim == 3 else 2)

		# view dependent
		view_dep = bool(config.get('view-dep', True))
		self.setViewDependent(view_dep)

		# resolution
		maxh = self.db.getMaxResolution()
		resolution = int(config.get("resolution", maxh - 6))
		self.widgets.resolution.start = self.start_resolution
		self.widgets.resolution.end = maxh
		self.setResolution(resolution)

		# palette
		palette = config.get("palette", "Viridis256")
		palette_range = config.get("palette-range", None)
		dtype_range = field.getDTypeRange()
		self.setPalette(palette)
		vmin, vmax = dtype_range.From, dtype_range.To
		self.setMetadataPaletteRange([vmin, vmax])
		if palette_range is None:
			self.setPaletteRange([vmin, vmax])
			self.setPaletteRangeMode("dynamic")
		else:
			self.setPaletteRange(*palette_range)
			self.setPaletteRangeMode("user")

		# color mapper
		color_mapper_type = config.get("color-mapper-type", "linear")
		self.setColorMapperType(color_mapper_type)

		# num_refinements
		num_refinements = int(config.get("num-refinements", 2))
		self.setNumberOfRefinements(num_refinements)

		# metadata
		metadata = config.get("metadata", None)
		if metadata:
			tabs = []
			for T, item in enumerate(metadata):

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
				download_button = Button(label="download")
				download_button.js_on_click(CustomJS(args=dict(base64_s=base64_s, filename=filename), code="""
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

				panel = TabPanel(child=Column(
					Div(text=f"<b><pre><code>{filename}</code></pre></b>"),
					download_button,
					Div(text=f"<div><pre><code>{body_s}</code></pre></div>"),
				),
					title=f"{T}")

				tabs.append(panel)

			self.widgets.metadata.children = [Tabs(tabs=tabs)]

		self.refresh()

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

		for it in self.children:
			it.setTimestepDelta(value)

		self.refresh()

	# getTimestep
	def getTimestep(self):
		return int(self.widgets.timestep.value)

	# setTimestep
	def setTimestep(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.timestep.value = value
		for it in self.children:
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
		for it in self.children:
			it.setField(value)
		self.refresh()

	# getPalette
	def getPalette(self):
		return self.palette

	# setPalette
	def setPalette(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.palette = value
		self.widgets.palette.value = value
		self.color_bar.color_mapper.palette = getattr(colorcet, value[len("colorcet."):]) if value.startswith(
			"colorcet.") else value
		for it in self.children:
			it.setPalette(value)
		self.refresh()

	# getMetadataPaletteRange
	def getMetadataPaletteRange(self):
		return self.metadata_palette_range

	# setMetadataPaletteRange
	def setMetadataPaletteRange(self, value):
		vmin, vmax = value
		self.metadata_palette_range = [vmin, vmax]
		for it in self.children:
			it.setMetadataPaletteRange(value)

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
			wmin.value = str(self.metadata_palette_range[0])
			wmax.value = str(self.metadata_palette_range[1])

		if mode == "dynamic-acc":
			wmin.value = str(float('+inf'))
			wmax.value = str(float('-inf'))

		wmin.disabled = False if mode == "user" else True
		wmax.disabled = False if mode == "user" else True

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
	def setPaletteRange(self, value):
		vmin, vmax = value
		self.widgets.palette_range_vmin.value = str(vmin)
		self.widgets.palette_range_vmax.value = str(vmax)
		for it in self.children:
			it.setPaletteRange(value)
		self.refresh()

	# onPaletteRangeChange
	def onPaletteRangeChange(self):
		if self.getPaletteRangeMode() == "user":
			vmin, vmax = self.getPaletteRange()
			self.setPaletteRange([vmin, vmax])

	# getColorMapperType
	def getColorMapperType(self):
		return "log" if isinstance(self.color_bar.color_mapper, LogColorMapper) else "linear"

	# setColorMapperType
	def setColorMapperType(self, value):

		assert value == "linear" or value == "log"
		logger.info(f"[{self.id}] value={value}")
		palette = self.getPalette()
		vmin, vmax = self.getPaletteRange()
		self.widgets.colormapper_type.value = value

		if value == "log":
			self.color_bar = ColorBar()  # ticker=BasicTicker(desired_num_ticks=10)
			self.color_bar.color_mapper = LogColorMapper(palette=palette, low=max(self.epsilon, vmin),
														 high=max(self.epsilon, vmax))
			self.color_bar.color_mapper.palette = self.palette
			self.color_bar.color_mapper.low, self.color_bar.color_mapper.high = self.getPaletteRange()
		else:
			self.color_bar = ColorBar()  # ticker=BasicTicker(desired_num_ticks=10)
			self.color_bar.color_mapper = LinearColorMapper(palette=palette, low=vmin, high=vmax)
			self.color_bar.color_mapper.palette = self.palette
			self.color_bar.color_mapper.low, self.color_bar.color_mapper.high = self.getPaletteRange()

		for it in self.children:
			it.setColorMapperType(value)
		self.refresh()

	# getNumberOfRefinements
	def getNumberOfRefinements(self):
		return self.widgets.num_refinements.value

	# setNumberOfRefinements
	def setNumberOfRefinements(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.num_refinements.value = value
		for it in self.children:
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
		value = Clamp(value, 0, self.getMaxResolution())
		self.widgets.resolution.value = value
		for it in self.children:
			it.setResolution(value)
		self.refresh()

	# isViewDependent
	def isViewDependent(self):
		return cbool(self.widgets.view_dep.value)

	# setViewDependent
	def setViewDependent(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.view_dep.value = str(int(value))
		self.widgets.resolution.title = "Max Res" if value else "Res"

		for it in self.children:
			it.setViewDependent(value)
		self.refresh()

	# getDirections
	def getDirections(self):
		return self.widgets.direction.options

	# setDirections
	def setDirections(self, value):
		logger.info(f"[{self.id}] value={value}")
		self.widgets.direction.options = value
		for it in self.children:
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
		self.widgets.direction.value = str(value)

		# default behaviour is to guess the offset
		self.guessOffset()

		for it in self.children:
			it.setDirection(value)

		self.refresh()

	# getLogicAxis (depending on the projection XY is the slice plane Z is the orthogoal direction)
	def getLogicAxis(self):
		dir = self.getDirection()
		dirs = self.getDirections()
		titles = [it[1] for it in dirs]
		# print(dir,dirs,titles)

		# this is the projected slice
		XY = [int(it[0]) for it in dirs]

		if len(XY) == 3:
			del XY[dir]
		else:
			assert (len(XY) == 2)
		X, Y = XY

		# this is the cross dimension
		Z = 2
		if len(dirs) == 3:
			Z = int(dirs[dir][0])

		return (X, Y, Z), (titles[X], titles[Y], titles[Z] if len(titles) == 3 else 'Z')

	# getOffsetStartEnd
	def getOffsetStartEnd(self):
		return self.widgets.offset.start, self.widgets.offset.end, self.widgets.offset.step

	# setOffsetStartEnd
	def setOffsetStartEndStep(self, value):
		A, B, step = value
		logger.info(f"[{self.id}] value={value}")
		self.widgets.offset.start, self.widgets.offset.end, self.widgets.offset.step = A, B, step
		for it in self.children:
			it.setOffsetStartEndStep(value)

	# getOffset (in physic domain)
	def getOffset(self):
		return self.widgets.offset.value

	# setOffset (3d only) (in physic domain)
	def setOffset(self, value):
		logger.info(f"[{self.id}] new-value={value} old-value={self.getOffset()}")

		self.widgets.offset.value = value
		assert (self.widgets.offset.value == value)
		for it in self.children:
			logging.info(f"[{self.id}] recursively calling setOffset({value}) for children={it.id}")
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

		render_id = [self.render_id] + [it.render_id for it in self.children]

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
