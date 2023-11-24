import copy
import logging

from bokeh.layouts import grid as Grid
from bokeh.models import Row
from bokeh.models import TabPanel, Tabs, Column

from .slice import Slice
from .utils import IsPyodide
from .widgets import Widgets

logger = logging.getLogger(__name__)


# //////////////////////////////////////////////////////////////////////////////////////
class Slices(Widgets):

	# constructor
	def __init__(self, doc=None, is_panel=False, parent=None, cls=Slice):
		super().__init__(doc=doc, is_panel=is_panel, parent=parent)
		self.cls = cls
		self.show_options = ["palette", "timestep", "field", "view_dep", "resolution"]
		self.slice_show_options = ["direction", "offset", "view_dep"]

		# view_mode
		self.widgets.view_mode = Tabs(tabs=[
			TabPanel(child=Column(sizing_mode="stretch_both"), title="Explore Data", name="1"), # equivalent to 1 view
			TabPanel(child=Column(sizing_mode="stretch_both"), title="Probe"       , name="probe"),
			TabPanel(child=Column(sizing_mode="stretch_both"), title="2"           , name="2"),
			TabPanel(child=Column(sizing_mode="stretch_both"), title="2-Linked"    , name="2-linked"),
			TabPanel(child=Column(sizing_mode="stretch_both"), title="4"           , name="4"),
			TabPanel(child=Column(sizing_mode="stretch_both"), title="4-Linked"    , name="4-linked"),
		],sizing_mode="stretch_both")
		self.widgets.view_mode.on_change("active", lambda attr, old, new: self.setViewMode(self.getViewMode()))

	# getShowOptions
	def getShowOptions(self):
		return [self.show_options, self.slice_show_options]

	# setShowOptions
	def setShowOptions(self, value):
		if isinstance(value, tuple) or isinstance(value, list):
			self.show_options, self.slice_show_options = value
		else:
			self.show_otions, self.slice_show_options = value, None
		self.first_row_layout.children = [getattr(self.widgets, it.replace("-", "_")) for it in self.show_options]

	# getMainLayout
	def getMainLayout(self):

		options = [it.replace("-", "_") for it in self.show_options]
		self.first_row_layout.children = [getattr(self.widgets, it) for it in options]

		if IsPyodide():
			self.idle_callbackAddAsyncLoop(f"{self}::onIdle (bokeh)", self.onIdle, 1000 // 30)

		elif self.is_panel:
			import panel as pn
			self.idle_callback = pn.state.add_periodic_callback(self.onIdle, period=1000 // 30)
			if self.parent is None:
				self.panel_layout = pn.pane.Bokeh(ret, sizing_mode='stretch_both')
				ret = self.panel_layout

		else:
			self.idle_callback = self.doc.add_periodic_callback(self.onIdle, 1000 // 30)

		self.start()

		# this will fill out the layout
		self.setViewMode(self.getViewMode())
		return self.widgets.view_mode


	# getViewMode
	def getViewMode(self):
		return self.widgets.view_mode.tabs[self.widgets.view_mode.active].name

	# createChild
	def createChild(self, options):
		ret = self.cls(doc=self.doc, is_panel=self.is_panel, parent=self)
		if options is not None:
			ret.setShowOptions(options)
		ret.config=self.getConfig()
		ret.setDatasets(self.getDatasets())
		ret.setDataset(self.getDataset(),force=True)
		return ret

	# clearTabLayout
	def clearTabLayout(self):

		v = self.children
		logger.info(f"[{self.id}] deleting old children {[it.id for it in v]}")
		for it in v: del it

		# empty all tabs
		for tab in self.widgets.view_mode.tabs:
			tab.child.children = []

	# createTabLayout
	def createTabLayout(self, mode):

		def RemoveOptions(v, values):
			ret = copy.copy(v)
			for it in values:
				if it in v: ret.remove(it)
			return ret

		options = self.slice_show_options

		if mode=="1":
			self.children = [
				self.createChild(RemoveOptions(options, ["datasets", "colormapper_type", "colormapper-type"]))]
			central = Row(self.children[0].getMainLayout(), sizing_mode="stretch_both")

		elif mode=="probe":
			child = self.createChild(RemoveOptions(options, ["datasets", "colormapper_type", "colormapper-type"]))
			child.setProbeVisible(True)
			self.children = [child]
			central = Row(self.children[0].getMainLayout(), sizing_mode="stretch_both")

		elif mode == "2" or mode == "2-linked":
			self.children = [self.createChild(options) for I in range(2)]
			central = Row(children=[child.getMainLayout() for child in self.children], sizing_mode="stretch_both")

		elif mode == "4" or mode == "4-linked":
			self.children = [self.createChild(options) for I in range(4)]
			central = Grid(children=[child.getMainLayout() for child in self.children], nrows=2, ncols=2,sizing_mode="stretch_both")

		else:
			raise Exception(f"problem here with setViewMode({value})")
			return 

		if "linked" in mode:
			self.children[0].setLinked(True)

		return  Row(
				Column(self.first_row_layout, central, sizing_mode='stretch_both' ),
				self.widgets.metadata,
				sizing_mode='stretch_both')

	# getTabByName
	def getTabByName(self, value):
		for I, tab in enumerate(self.widgets.view_mode.tabs):
			if tab.name == value:
				self.widgets.view_mode.active = I
				return tab
		return None

	# setViewMode
	def setViewMode(self, value):
		value=value.lower().strip()
		logger.info(f"[{self.id}] value={value}")
		tab = self.getTabByName(value)
		if not tab: return
		self.hold()
		super().stop()
		self.clearTabLayout()
		tab.child.children = [self.createTabLayout(value)]
		super().start()
		self.unhold()

	# setNumberOfViews (backward compatible)
	def setNumberOfViews(self, value):
		self.setViewMode(str(value))
