import os,sys,logging
import types

# //////////////////////////////////////////////////////////////////////////////////////
def ArgToList(v):
	if isinstance(v,str):
		return eval(v)
	else:
		assert(isinstance(v,tuple) or isinstance(v,list))
		return v


# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	# special case, NEXUS file (or whatever) containing most metadata

	import argparse
	parser = argparse.ArgumentParser(description="OpenVisus Dashboards")
	parser.add_argument("--dataset", type=str, required=False,default=["https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"], nargs='+', )
	parser.add_argument("--palette", type=str, required=False, default="Greys256")
	parser.add_argument("--palette-range", type=str, required=False, default=None) # in the format [vmin,vmax]
	parser.add_argument("--physic-box", type=str, required=False, default=None)  # in the format [(x1,x2),(y1,y2),(z1,z2)]
	parser.add_argument('--no-view-dep', action='store_true')
	parser.add_argument("--quality", type=int, required=False, default=0)
	parser.add_argument("--timestep", type=int, required=False, default=None)
	parser.add_argument("--timestep-delta", type=int, required=False, default=1)
	parser.add_argument("--field", type=str, required=False, default=None)
	parser.add_argument("--num-refinements", type=int, required=False, default=3)
	parser.add_argument("--axis", type=str, required=False, default=[('0','X'),('1','Y'),('2','Z')]) # axis value, axis name
	parser.add_argument('--num-views', type=int, required=False, default=1)
	parser.add_argument('--show-options', type=str, required=False, default=["num_views", "palette", "dataset", "timestep", "timestep-delta", "field", "viewdep", "quality", "num_refinements", "play-button", "play-sec","colormapper_type"])
	parser.add_argument('--slice-show-options', type=str, required=False, default=["direction", "offset", "viewdep", "status_bar"])
	parser.add_argument('--color-mapper', required=False, default="linear") # also "log" possible
	parser.add_argument('--multi',  action='store_true')
	parser.add_argument('--single', action='store_true')
	parser.add_argument('--py' , action='store_true') # experimental pure python backend
	parser.add_argument('--cpp', action='store_true')
	parser.add_argument('--probes', action='store_true') # if you want to try the experimental probe tool

	# to set default directions and offsets
	# e.g. --directions "..." --offset "..."
	parser.add_argument('--directions', type=str, required=False, default="[]")
	parser.add_argument('--offsets', type=str, required=False, default="[]")

	args = parser.parse_args(sys.argv[1:])

	# need to set it before importing OpenVisus or openvisuspy
	if args.py:  os.environ["VISUS_BACKEND"]="py"
	if args.cpp: os.environ["VISUS_BACKEND"]="cpp"

	# setup logger
	from openvisuspy import SetupLogger,IsPanelServe,GetBackend,Slice, Slices,cbool
	logger=SetupLogger()

	logger.info(f"GetBackend()={GetBackend()} args={args}")

	# ///////////////////////////////////////////////////////////////////////
	# is a streamable nexus, read most of the information from a streamable nexus (see CHESS convert-nexus-data jupyter notebook)
	if "streamable.nxs" in args.dataset[0]:

		from nexusformat import nexus 
		from nexusformat.nexus.tree import NX_CONFIG 
		NX_CONFIG['memory']=16000 # alllow data to be 16000MB (i.e. 16GB)

		def NexusTraverse(cur,nrec=0):
			yield (nrec,cur)
			for _k, child in (cur.entries.items() if hasattr(cur,"entries") else []): 
				yield from NexusTraverse(child,nrec+1)

		streamable=nexus.nxload(args.dataset[0])
		nxdata=[node for depth, node in NexusTraverse(streamable) if isinstance(node,nexus.NXdata) and "axes" in node.attrs and "signal" in node.attrs][0]

		axis  =[nxdata[it] for it in nxdata.attrs["axes"]]
		signal=nxdata[nxdata.attrs["signal"]]

		args.dataset=ArgToList(signal.attrs["openvisus"])
		args.axis=[(str(I), axis[2-I].nxname) for I in range(3)]
		args.physic_box=[(axis[2-I].nxdata[0], axis[2-I].nxdata[-1]) for I in range(3)]

	show_options=ArgToList(args.show_options) 
	slice_show_options=ArgToList(args.slice_show_options) 

	if args.single:
		view=Slice(show_options=show_options)
	else:
		view=Slices(show_options=show_options, slice_show_options=slice_show_options)
		view.setNumberOfViews(args.num_views)
	if args.dataset == ['chess']:
		urls = ['https://atlantis.sci.utah.edu/mod_visus?dataset=chess-zip&cached=1', 'http://atlantis.sci.utah.edu/mod_visus?dataset=rabbit&cached=1', 'http://atlantis.sci.utah.edu/mod_visus?dataset=foam-2022-01&cached=1']
	else:
		urls=args.dataset

	view.setDatasets([(url,str(I)) for I,url in enumerate(urls)],"Datasets")
	view.setDataset(urls[0])

	view.setQuality(args.quality)
	view.setNumberOfRefinements(args.num_refinements)
	view.setPalette(args.palette) 

	# palette range
	if args.palette_range:
		vmin,vmax=ArgToList(args.palette_range)
	else:
		dtype_range=view.db.getField().getDTypeRange()
		vmin,vmax=dtype_range.From,dtype_range.To
	if vmin>=vmax: vmin,vmax=[0.0,255.0]
	view.setPaletteRange([vmin,vmax])

	view.setTimestepDelta(args.timestep_delta)

	if args.timestep is not None:
		view.setTimestep(args.timestep)

	if args.field is not None:
		view.setField(args.field)

	# logic_to_physic, i.e. (transate,scale) for each axis XYZ 
	T=[(0.0,1.0)]*3 
	if args.physic_box is not None:
		box=ArgToList(args.physic_box)
		W,H,D=view.db.getLogicSize()
		x1,x2=box[0]
		y1,y2=box[1]
		z1,z2=box[2]

		def LinearMapping(a,b, A,B):
			# A + (B-A)*(coord-a)/(b-a)
			s=(B-A)/(b-a)
			return (A-a*s),s

		tx,sx = LinearMapping(0,W, x1,x2)
		ty,sy = LinearMapping(0,H, y1,y2)
		tz,sz = LinearMapping(0,D, z1,z2)
		T=[(tx,sx), (ty,sy), (tz,sz)]

	view.setLogicToPhysic(T)
	view.setViewDependent(False if args.no_view_dep else True) 

	# axis
	view.setDirections(ArgToList(args.axis))

	# linear or log
	if args.color_mapper:
		view.setColorMapperType(args.color_mapper)

	# default direction/offset 
	directions=ArgToList(args.directions)
	offsets=ArgToList(args.offsets)
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
	

