import os,sys,logging,types
import bokeh
from bokeh.models import Row,Select,TextInput,BasicTicker,Slider, ColorBar, LinearColorMapper, Column

from openvisuspy import SetupLogger,IsPanelServe,GetBackend,Slice, Slices,cbool

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):
	
	"""
	python -m bokeh serve examples\tutorials\run.py --dev 
	"""

	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")

	doc=bokeh.io.curdoc()
	doc.theme = 'light_minimal'

	# change as needed
	config={
		"datasets": [
			{"name":"example1","url":r"C:\big\visus_datasets\chess\example-near-field\visus.idx"},
			{"name":"example2","url":r"C:\big\visus_datasets\chess\example-near-field\visus.idx"},
		]
	}	

	# bokeh widgets
	datasets = Select(title="Dataset", options=[it["name"] for it in config["datasets"]]) 
	palette = Select(title='Palette', options=["Greys256", "Inferno256",  "Magma256", "Plasma256", "Viridis256", "Cividis256", "Turbo256"])
	palette_range_mode = Select(title="range",options=["metadata","user","dynamic","dynamic-acc"], value="metadata")
	palette_range_vmin = TextInput(title="vmin")
	palette_range_vmax = TextInput(title="vmax")	
	colormapper_type=Select(title='colormap',  options=["linear","log"], value="log")
	timestep = Slider(title='Time', start=0, end=1, sizing_mode='stretch_width')
	field = Select(title='Field',  options=[])
	direction = Select(title='Direction', options=[('0','X'), ('1','Y'), ('2','Z')])
	offset = Slider(title='Offset', start=0, end=1024, sizing_mode='stretch_width')
	num_refinements=Slider(title='#Ref', start=0, end=4, value=2)
	resolution = Slider(title='Resolution', start=0, end=99, value=21)
	vie_wdep = Select(title="Auto Res",options=[str(True),str(False)])	

	view=Slice()
	view.setShowOptions([])
	view.setConfig(config)

	def SetDataset(value):

		view.setDataset(value)
		view.setResolution(resolution.value)
		view.setNumberOfRefinements(num_refinements.value)
		view.setViewDependent(bool(view_dep.value))
		view.setColorMapperType(colormapper_type.value)
		view.setPaletteRangeMode(palette_range_mode.value)

		db=view.db

		datasets.value=value
		
		palette.value=view.getPalette()
		vmin,vmax=view.getPaletteRange()
		palette_range_vmin.value=str(vmin)
		palette_range_vmax.value=str(vmax)

		timesteps =db.getTimesteps()
		timestep.start=timesteps[ 0]
		timestep.end  =timesteps[-1]
		timestep.value=view.getTimestep()

		field.options=[fieldname for fieldname in view.getFields()]
		field.value=view.getField()
		
		direction.value=str(view.getDirection())
		
		offset.value=view.getOffset()

	def onDatasetChange(attr, old, new):
		SetDataset(new)

	def onPaletteChange(attr, old, new):
		view.setPalette(new)
	
	def onPaletteRangeModeChange(attr, old, new):
		view.setPaletteRangeMode(new)
	
	def onPaletteRangeChange(attr, old, new):
		view.setPaletteRange([palette_range_vmin.value, palette_range_vmax.value])	

	def onColorMapperTypeChange(attr, old, new):
		view.setColorMapperType(new)
	
	def onTimestepChange(attr, old, new):
		view.setTimestep(new)
	
	def onFieldChange(attr, old, new):
		view.setField(new)
	
	def onDirectionChange(attr, old, new):
		view.setDirection(new)
	
	def onOffsetChange(attr, old, new):
		view.setOffset(new)
	
	def onNumberOfRefinementsChange(attr, old, new):
		view.setNumberOfRefinements(new)

	def onResolutionChange(attr, old, new):
		view.setResolution(new)
	
	def onViewDependentChange(attr, old, new):
		view.setViewDependent(bool(new))

	datasets.on_change("value",onDatasetChange)  
	palette.on_change("value",onPaletteChange)  
	palette_range_mode.on_change("value",onPaletteRangeModeChange)
	palette_range_vmin.on_change("value",onPaletteRangeChange)
	palette_range_vmax.on_change("value",onPaletteRangeChange)
	colormapper_type.on_change("value",onColorMapperTypeChange) 
	timestep.on_change("value",onTimestepChange)
	field.on_change("value",onFieldChange)  
	direction.on_change ("value",onDirectionChange)  
	offset.on_change ("value",onOffsetChange)
	num_refinements.on_change("value",onNumberOfRefinementsChange)
	resolution.on_change("value",onResolutionChange)  
	view_dep.on_change("value",onViewDependentChange)  

	SetDataset("example1")

	doc.add_root(Column(
		Row(
			datasets,
			palette,
			palette_range_mode,
			palette_range_vmin,
			palette_range_vmax,
			colormapper_type,
			timestep,
			field,
			direction,
			offset,
			num_refinements,
			resolution,
			view_dep,
			sizing_mode='stretch_width',
		),
		view.getMainLayout(),
		sizing_mode='stretch_both',
	))
	

