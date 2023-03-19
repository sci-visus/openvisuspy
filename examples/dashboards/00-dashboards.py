import os,sys,logging





 
# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):
	logger=logging.getLogger("openvisuspy")
	logger.setLevel(logging.INFO)
	is_panel="--panel" in sys.argv
	num_views=1
	logger.info(f"sys.argv={sys.argv}")
	os.environ["VISUS_BACKEND"]="py" if "--py" in sys.argv else "cpp"
	
	from openvisuspy import Slice, Slices,cbool,ServeApp

	if num_views<=1:
		palette,palette_range="Greys256",(0,255)
		urls=["http://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"]
		view=Slice()
		view.setDataset(urls[0])
		view.setDirection(2)
		view.setNumberOfRefinements(3)
		view.setPalette(palette)
		view.setPaletteRange(palette_range)
		view.setTimestep(view.getTimestep())
		view.setField(view.getField())
	else:
		urls=[f"https://maritime.sealstorage.io/api/v0/s3/utah/nasa/dyamond/idx_arco/face{zone}/u_face_{zone}_depth_52_time_0_10269.idx?cached=1" for zone in range(6)]
		view=Slices(num_views=3,
			show_options=["num_views","palette","dataset","timestep","timestep-delta","field","viewdep","quality","num_refinements","play-button", "play-sec"],
			slice_show_options=["direction","offset","viewdep","status_bar"])
		view.setDatasets([(url,str(I)) for I,url in enumerate(urls)],"Zone")
		view.setDataset(urls[0])
		view.setQuality(-3)
		view.setNumberOfRefinements(3)
		view.setPalette("Turbo256") 
		view.setPaletteRange((-30,60))
		view.setTimestepDelta(10)
		view.setField(None)
		view.setLogicToPixel([(0.0,1.0), (0.0,1.0), (0.0,10.0)])
		view.setViewDependent(False) # important, there is aproblem in viewdep
		view.setDirections([('0','Long'),('1','Lat'),('2','Depth')])

	main_layout=view.getLayout(is_panel=is_panel)
	ServeApp(main_layout, is_panel=is_panel)



	
		 

