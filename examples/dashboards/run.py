import os,sys,logging,base64,json,types
import urllib.request

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	from openvisuspy import SetupLogger,IsPanelServe,GetBackend,Slice, Slices,cbool
	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")

	if False:
		view=Slice(show_options=["num_views", "palette", "datasets", "timestep", "timestep-delta", "field", "viewdep", "quality", "num_refinements", "play-button", "play-sec","colormapper_type","show_metadata"])
	else:
		view=Slices(
			show_options=["num_views", "palette", "datasets", "timestep", "timestep-delta", "field", "viewdep", "quality", "num_refinements", "play-button", "play-sec","colormapper_type","show_metadata"], 
			slice_show_options=["direction", "offset", "viewdep", "status_bar","palette_range"]
		)

	# can load the config file from remote
	config_filename=sys.argv[1]
	config=json.load(
		urllib.request.urlopen(config_filename) if config_filename.startswith("http") else 
		open(sys.argv[1]))
	
	view.setConfig(config)
	
	#if args.probes:
	#	from openvisuspy.probes import ProbeTool
	#	central=ProbeTool(view)
	#else:
	central=view

	if IsPanelServe():
		from openvisuspy.app import GetPanelApp
		main_layout=central.getPanelLayout()
		app=GetPanelApp(main_layout)
		app.servable()
	else:
		import bokeh
		doc=bokeh.io.curdoc()
		main_layout=central.getBokehLayout(doc=doc)
		doc.add_root(main_layout)

	

