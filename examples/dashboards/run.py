import os,sys,logging

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	import argparse
	parser = argparse.ArgumentParser(description="OpenVisus Dashboards")
	parser.add_argument("--dataset", type=str, required=False,default=["https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"], nargs='+', )
	parser.add_argument("--palette", type=str, required=False, default="Greys256")
	parser.add_argument("--palette-range", type=str, required=False, default="[0.0,255.0]")
	parser.add_argument("--logic-to-pixel", type=str, required=False, default="[(0.0,1.0), (0.0,1.0), (0.0,10.0)]")
	parser.add_argument('--no-view-dep', action='store_true')
	parser.add_argument("--quality", type=int, required=False, default=0)
	parser.add_argument("--timestep", type=int, required=False, default=None)
	parser.add_argument("--timestep-delta", type=int, required=False, default=1)
	parser.add_argument("--field", type=str, required=False, default=None)
	parser.add_argument("--num-refinements", type=int, required=False, default=3)
	parser.add_argument("--axis", type=str, required=False, default="[('0','X'),('1','Y'),('2','Z')]")
	parser.add_argument('--num-views', type=int, required=False, default=1)
	parser.add_argument('--show-options', type=str, required=False, default="""["num_views", "palette", "dataset", "timestep", "timestep-delta", "field", "viewdep", "quality", "num_refinements", "play-button", "play-sec"]""")
	parser.add_argument('--slice-show-options', type=str, required=False, default="""["direction", "offset", "viewdep", "status_bar"]""")
	parser.add_argument('--multi',  action='store_true')
	parser.add_argument('--single', action='store_true')
	parser.add_argument('--py' , action='store_true')
	parser.add_argument('--cpp', action='store_true')
	parser.add_argument('--directions', type=str, required=False, default="[]")
	parser.add_argument('--offsets', type=str, required=False, default="[]")
	args = parser.parse_args(sys.argv[1:])		

	if args.multi:  args.num_views=3
	if args.single: args.num_views=1
	if args.py:  os.environ["VISUS_BACKEND"]="py"
	if args.cpp: os.environ["VISUS_BACKEND"]="cpp"	

	from openvisuspy import SetupLogger,IsPanelServe,GetBackend,Slice, Slices,cbool
	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")
	logger.info(f"args={args}")

	urls=args.dataset
	logic_to_pixel=eval(args.logic_to_pixel)
	view_dep=False if args.no_view_dep else True
	quality=args.quality
	timestep_delta=args.timestep_delta
	num_refinements=args.num_refinements
	timestep=args.timestep
	field=args.field
	axis=eval(args.axis)
	palette=args.palette
	palette_range=eval(args.palette_range)
	num_views=args.num_views
	show_options=eval(args.show_options)
	slice_show_options=eval(args.slice_show_options)
	directions=eval(args.directions)
	offsets=eval(args.offsets)

	if num_views<=1:
		view=Slice(show_options=show_options)
	else:
		view=Slices(num_views=num_views, show_options=show_options, slice_show_options=slice_show_options)

	view.setDatasets([(url,str(I)) for I,url in enumerate(urls)],"Datasets")
	view.setDataset(urls[0])
	view.setQuality(quality)
	view.setNumberOfRefinements(num_refinements)
	view.setPalette(palette) 
	view.setPaletteRange(palette_range)
	view.setTimestepDelta(timestep_delta)

	if timestep is not None:
		view.setTimestep(timestep)

	if field is not None:
		view.setField(field)

	view.setLogicToPixel(logic_to_pixel)
	view.setViewDependent(view_dep) 
	view.setDirections(axis)

	for C,(dir,offset) in enumerate(zip(directions,offsets)):
		view.children[C].setDirection(dir)
		view.children[C].setOffset(offset)

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
	

