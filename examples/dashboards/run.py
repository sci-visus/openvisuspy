import os,sys,logging
import types

# //////////////////////////////////////////////////////////////////////////////////////
def StreamableNexus(url):

		from nexusformat import nexus 
		from nexusformat.nexus.tree import NX_CONFIG 
		NX_CONFIG['memory']=16000 # alllow data to be 16000MB (i.e. 16GB)

		def NexusTraverse(cur,nrec=0):
			yield (nrec,cur)
			for _k, child in (cur.entries.items() if hasattr(cur,"entries") else []): 
				yield from NexusTraverse(child,nrec+1)

		streamable=nexus.nxload(url)
		nxdata=[node for depth, node in NexusTraverse(streamable) if isinstance(node,nexus.NXdata) and "axes" in node.attrs and "signal" in node.attrs][0]

		axis=[nxdata[it] for it in nxdata.attrs["axes"]]
		signal=nxdata[nxdata.attrs["signal"]]

		idx_filename=eval(signal.attrs["openvisus"])[0] # get the first one assuming it's an array
		vmin=float(signal.attrs["vmin"])
		vmax=float(signal.attrs["vmax"])
		logger.info(f"idx_filename={idx_filename}")
		D,H,W=signal.shape
		dtype=signal.dtype

		x1,x2=axis[2].nxdata[0], axis[2].nxdata[-1]
		y1,y2=axis[1].nxdata[0], axis[1].nxdata[-1]
		z1,z2=axis[0].nxdata[0], axis[0].nxdata[-1]

		axis=str([
			('0',axis[2].nxname),
			('1',axis[1].nxname),
			('2',axis[0].nxname)
		])

		def LinearMapping(a,b, A,B):
			# A + (B-A)*(coord-a)/(b-a)
			s=(B-A)/(b-a)
			return (A-a*s),s

		tx,sx = LinearMapping(0,W, x1,x2)
		ty,sy = LinearMapping(0,H, y1,y2)
		tz,sz = LinearMapping(0,D, z1,z2)

		palette_range=str([vmin,vmax])
		logic_to_physic=str([
			(tx,sx), 
			(ty,sy), 
			(tz,sz)	
		])

		#logger.info(f"x1={x1} x2={x2} W={W}")
		#logger.info(f"y1={y1} y2={y2} H={H}")
		#logger.info(f"z1={z1} z2={z2} D={D}")
		#logger.info("axis" ,args.axis)
		#logger.info("palette_range" ,args.palette_range)
		#logger.info("logic_to_physic",args.logic_to_physic)

		ret=types.SimpleNamespace()
		ret.idx_filename=idx_filename
		ret.axis=axis
		ret.palette_range=palette_range
		ret.logic_to_physic=logic_to_physic
		return ret


# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	# special case, NEXUS file (or whatever) containing most metadata

	import argparse
	parser = argparse.ArgumentParser(description="OpenVisus Dashboards")
	parser.add_argument("--dataset", type=str, required=False,default=["https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"], nargs='+', )
	parser.add_argument("--palette", type=str, required=False, default="Greys256")
	parser.add_argument("--palette-range", type=str, required=False, default="[0.0,255.0]")
	parser.add_argument("--logic-to-pixel", type=str, required=False, default="[(0.0,1.0), (0.0,1.0), (0.0,1.0)]")
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
	parser.add_argument('--log-color-mapper', action='store_true')
	parser.add_argument('--py' , action='store_true')
	parser.add_argument('--cpp', action='store_true')
	parser.add_argument('--probes', action='store_true') # if you want to try the experimental probe tool

	# to set default directions and offsets
	# e.g. --directions "..." --offset "..."
	parser.add_argument('--directions', type=str, required=False, default="[]")
	parser.add_argument('--offsets', type=str, required=False, default="[]")
	args = parser.parse_args(sys.argv[1:])

	if args.multi:  args.num_views=3
	if args.single: args.num_views=1
	if args.py:  os.environ["VISUS_BACKEND"]="py"
	if args.cpp: os.environ["VISUS_BACKEND"]="cpp"	

	
	
	# setup logger
	from openvisuspy import SetupLogger,IsPanelServe,GetBackend,Slice, Slices,cbool
	logger=SetupLogger()

	logger.info(f"GetBackend()={GetBackend()} args={args}")

	if "streamable.nxs" in args.dataset[0]:

		# is a streamable nexus, read most of the information from a streamable nexus (see CHESS convert-nexus-data jupyter notebook)
		"""
		set PYTHONPATH=./src;C:\projects\OpenVisus\build\RelWithDebInfo
		python -m bokeh serve examples/dashboards/run.py --dev --args --dataset C:/visus_datasets/3scans_HKLI.streamable.nxs  --multi --log-color-mapper --palette Viridis256
		"""	

		sub=StreamableNexus(args.dataset[0])
		args.dataset=[sub.idx_filename]
		args.axis=sub.axis
		args.palette_range=sub.palette_range
		args.logic_to_physic=sub.logic_to_physic
	
	urls=args.dataset
	logic_to_physic=eval(args.logic_to_physic)
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

	view.setLogicToPhysic(logic_to_physic)
	view.setViewDependent(view_dep) 
	view.setDirections(axis)

	if args.log_color_mapper:
		view.setColorMapperType("log")

	for C,(dir,offset) in enumerate(zip(directions,offsets)):
		view.children[C].setDirection(dir)
		view.children[C].setOffset(offset)

	if args.probes:
		from openvisuspy.probes import ProbeTool
		central=ProbeTool(view)
	else:
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
	

