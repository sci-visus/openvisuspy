import os,sys,logging

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):
	logger=logging.getLogger("openvisuspy")
	logger.setLevel(logging.DEBUG)
	is_panel="--panel" in sys.argv
	logger.info(f"sys.argv={sys.argv}")
	
	from openvisuspy import Slice, Slices,cbool,ServeApp
	
	# defaults
	logic_to_pixel=[(0.0,1.0), (0.0,1.0), (0.0,1.0)]
	view_dep=True
	quality=0
	timestep_delta=1
	num_refinements=3
	directions=[('0','X'),('1','Y'),('2','Z')]

	
	num_views=2
	dataset="chess"

	if dataset=="david":
		urls=["http://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"]
		palette,palette_range="Greys256",(0,255)		

	if dataset=="2kbit1":
		urls=["http://atlantis.sci.utah.edu/mod_visus?dataset=2kbit1&cached=1"]
		palette,palette_range="Greys256",(0,255)

	if dataset=="chess":
		urls=['http://atlantis.sci.utah.edu:80/mod_visus?dataset=chess-zip&cached=1']
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

	main_layout=view.getLayout(is_panel=is_panel)
	ServeApp(main_layout, is_panel=is_panel)

		 

