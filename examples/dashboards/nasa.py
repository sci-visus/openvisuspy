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

	view=Slices(
		show_options=["palette","timestep","timestep-delta","field","quality","play-button", "play-sec"],
		slice_show_options=["direction","offset","status_bar"])

	view.setNumberOfViews(num_views)  
	view.setDataset("https://maritime.sealstorage.io/api/v0/s3/utah/nasa/dyamond/mit_output/llc2160_arco/visus.idx?&access_key=any&secret_key=any&endpoint_url=https://maritime.sealstorage.io/api/v0/s3&cached=idx")
	view.setPalette("colorcet.coolwarm")
	view.setPaletteRange([-0.25256651639938354, 0.3600933849811554])
	view.setTimestepDelta(10)
	view.setTimestep(2015)
	view.setField(view.getField())
	view.setQuality(-6)
	view.setLogicToPixel([(0.0,1.0), (0.0,1.0), (0.0,30.0)])

	view.children[0].setDirection(2)
	view.children[0].setOffset(0)

	if IsPanelServe():
		from openvisuspy.app import GetPanelApp
		main_layout=view.getPanelLayout()
		app=GetPanelApp(main_layout)
		app.servable()
	else:
		import bokeh
		doc=bokeh.io.curdoc()
		main_layout=view.getBokehLayout(doc=doc)
		doc.add_root(main_layout)		






