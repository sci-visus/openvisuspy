import os,sys,logging,time

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	if "--multi" in sys.argv:
		num_views=3
	elif "--single" in sys.argv:
		num_views=1
	else:
		num_views=1

	if "--py" in sys.argv:
		backend="py"
		os.environ["VISUS_BACKEND"]=backend
	
	if "--cpp" in sys.argv:
		backend="cpp"
		os.environ["VISUS_BACKEND"]=backend

	from openvisuspy import SetupLogger, IsPanelServe, GetBackend, Slice, Slices
	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")

	is_panel=IsPanelServe()
	if is_panel:
		import panel as pn
		doc=None
	else:
		import bokeh
		doc=bokeh.io.curdoc()
		doc.theme = 'light_minimal'

	view=Slices(doc=doc, is_panel=is_panel)
	view.setShowOptions([
		["palette","timestep","timestep-delta","field","quality","play-button", "play-sec"],
		["direction","offset"]
	])

	view.setNumberOfViews(num_views)  

	timestep_delta=4

	view.setDataset(f"https://maritime.sealstorage.io/api/v0/s3/utah/nasa/dyamond/mit_output/llc2160_arco/visus.idx?&access_key=any&secret_key=any&endpoint_url=https://maritime.sealstorage.io/api/v0/s3&cached=idx")
	view.setPalette("colorcet.coolwarm")
	view.setPaletteRange([-0.25256651639938354, 0.3600933849811554])
	view.setTimestepDelta(timestep_delta)
	view.setTimestep((2015//timestep_delta)*timestep_delta)
	view.setField(view.getField())
	view.setQuality(-6)
	view.setLogicToPhysic([(0.0,1.0), (0.0,1.0), (0.0,30.0)])

	view.children[0].setDirection(2)
	view.children[0].guessOffset()

	main_layout=view.getMainLayout()

	if is_panel:
		main_layout.servable()
	else:
		doc.add_root(main_layout)







