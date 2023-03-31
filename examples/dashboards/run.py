import os,sys,logging

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

	from openvisuspy import SetupLogger,IsPanelServe,GetBackend,Slice, Slices,cbool
	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")

	# defaults
	logic_to_pixel=[(0.0,1.0), (0.0,1.0), (0.0,1.0)]
	view_dep=True
	quality=0
	timestep_delta=1
	num_refinements=3
	directions=[('0','X'),('1','Y'),('2','Z')]

	dataset="david_subsampled"

	if dataset=="david_subsampled":
		urls=["https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"]
		palette,palette_range="Greys256",(0,255)		

	if dataset=="2kbit1":
		urls=["https://atlantis.sci.utah.edu/mod_visus?dataset=2kbit1&cached=1"]
		palette,palette_range="Greys256",(0,255)

	if dataset=="chess-zip":
		urls=['https://atlantis.sci.utah.edu/mod_visus?dataset=chess-zip&cached=1']
		palette,palette_range="Viridis256",[-0.017141795,0.012004322]

	if dataset=="nasa":
		# this cannot work in py backend, no openvisus sever
		urls=[f"https://maritime.sealstorage.io/api/v0/s3/utah/nasa/dyamond/idx_arco/face{zone}/u_face_{zone}_depth_52_time_0_10269.idx?cached=1" for zone in range(6)]
		palette,palette_range="Turbo256",(-30,60)
		logic_to_pixel=[(0.0,1.0), (0.0,1.0), (0.0,10.0)]
		view_dep=False # important, there is aproblem in viewdep
		quality=-3
		timestep_delta=10
		directions=[('0','Long'),('1','Lat'),('2','Depth')]		

	if num_views<=1:
		view=Slice()
	else:
		view=Slices(num_views=num_views,
			show_options=["num_views","palette","dataset","timestep","timestep-delta","field","viewdep","quality","num_refinements","play-button", "play-sec"],
			slice_show_options=["direction","offset","viewdep","status_bar"])

	view.setDatasets([(url,str(I)) for I,url in enumerate(urls)],"Datasets")
	view.setDataset(urls[0])
	view.setQuality(quality)
	view.setNumberOfRefinements(num_refinements)
	view.setPalette(palette) 
	view.setPaletteRange(palette_range)
	view.setTimestepDelta(timestep_delta)
	# view.setTimestep(view.getTimestep())
	# view.setField(None)
	view.setLogicToPixel(logic_to_pixel)
	view.setViewDependent(view_dep) 
	view.setDirections(directions)

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
	


		

