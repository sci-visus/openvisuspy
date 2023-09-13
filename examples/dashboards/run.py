import os,sys,logging,base64,json
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

	parser.add_argument('--show-options', type=str, required=False, 
										 default=["num_views", "palette", "dataset", "timestep", "timestep-delta", "field", "viewdep", "quality", "num_refinements", 
										"play-button", "play-sec",
										"colormapper_type",
										"show_metadata"
										])
	
	parser.add_argument('--slice-show-options', type=str, required=False, 
										 default=["direction", "offset", "viewdep", "status_bar","palette_range"
										])
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

	dtype_range=view.db.getField().getDTypeRange()
	vmin,vmax=dtype_range.From,dtype_range.To
	view.setMetadataPaletteRange([vmin,vmax])

	# palette range
	if args.palette_range:
		vmin,vmax=ArgToList(args.palette_range)
	view.setPaletteRange([vmin,vmax])

	view.setPaletteRangeMode("dynamic")

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

	# metadata
	# /////////////////////////////////////////////////////
		# https://plainenglish.io/blog/how-to-download-a-file-using-javascript-fec4685c0a22
		# https://stackoverflow.com/questions/69077169/serve-a-file-from-a-memory-stream-to-a-bokeh-app
	from bokeh.models import Select,LinearColorMapper,LogColorMapper,ColorBar,Button,Slider,TextInput,Row,Column,Div,TabPanel, Tabs

	metadata="""
	{
	  "metadata": [
	    {
	      "type": "json-object",
	      "filename": "generated-nsdf-convert.json",
	      "object": {
	        "id": "1",
	        "name": "scrgiorgio-near-field-20230912-01",
	        "src": "/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif",
	        "dst": "/mnt/data1/nsdf/tmp/scrgiorgio-near-field-20230912-01/visus.idx",
	        "compression": "zip",
	        "arco": "1mb",
	        "insert_time": "2023-09-12 10:26:33.617513",
	        "conversion_start": "2023-09-12 10:26:33.848359",
	        "conversion_end": "2023-09-12 10:27:24.200120"
	      }
	    },
	    {
	      "type": "json-object",
	      "filename": "/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json",
	      "object": {
	        "0": "date",
	        "1": "time",
	        "2": "epoch",
	        "3": "SCAN_N",
	        "4": "junkstart",
	        "5": "goodstart",
	        "6": "ramsx",
	        "7": "ramsz",
	        "8": "initial_load_volts",
	        "9": "initial_load_newtons",
	        "10": "initial_screw",
	        "11": "final_load_volts",
	        "12": "final_load_newtons",
	        "13": "final_screw",
	        "14": "ome_start_req",
	        "15": "ome_end_req",
	        "16": "nframes_req",
	        "17": "ome_start_real",
	        "18": "ome_end_real",
	        "19": "nframes_real",
	        "20": "step_real",
	        "21": "count_time",
	        "22": "load_step",
	        "23": "MECHTEST_CYCLE_NUM",
	        "24": "foil_in",
	        "25": "det"
	      }
	    },
	    {
	      "type": "b64encode",
	      "filename": "/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par",
	      "encoded": "CjIwMjMwNTMxIDIyMDIzMyAxNjg1NTg0OTUzIDIxIDE2MTEgMTYxNSAwIC0wLjQwNSAtMSA0LjQwODc3IC0xNC42NjEzIC0xIDAuOTYyMzYgLTE0LjY2MTMgMCA5MCAzNjAgLTAuMDAwNjM1NTkzIDg5LjkyMzEgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNTMxIDIyMDkwOSAxNjg1NTg1MzQ5IDIyIDE5NzcgMTk4MSAwIC0wLjQwNSAtMSAxLjI3NTY3IC0xNC42NjEzIC0xIC0wLjYwNDE5IC0xNC42NjEzIDkwIDE4MCAzNjAgODkuOTk5NCAxNzkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDUzMSAyMjE1NDUgMTY4NTU4NTc0NSAyMyAyMzQzIDIzNDcgMCAtMC40MDUgLTEgLTAuNjA0MTkgLTE0LjY2MTMgLTEgNC4wOTU0NiAtMTQuNjYxMyAxODAgMjcwIDM2MCAxNzkuOTk5IDI2OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNTMxIDIyMjIyMSAxNjg1NTg2MTQxIDI0IDI3MDkgMjcxMyAwIC0wLjQwNSAtMSA0LjA5NTQ2IC0xNC42NjEzIC0xIDUuMzQ4NyAtMTQuNjYxMyAyNzAgMzYwIDM2MCAyNjkuOTk5IDM1OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNTMxIDIyMzAxMSAxNjg1NTg2NjExIDI1IDMwNzUgMzA3OSAwIC0wLjMxNSAtMSA1LjY2MjAxIC0xNC42NjEzIC0xIDEuNTg4OTggLTE0LjY2MTMgMCA5MCAzNjAgLTAuMDAwNjM1NTkzIDg5LjkyMzEgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNTMxIDIyMzY0NyAxNjg1NTg3MDA3IDI2IDM0NDEgMzQ0NSAwIC0wLjMxNSAtMSAxLjI3NTY3IC0xNC42NjEzIC0xIDAuMzM1NzQgLTE0LjY2MTMgOTAgMTgwIDM2MCA4OS45OTk0IDE3OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNTMxIDIyNDMyMyAxNjg1NTg3NDAzIDI3IDM4MDcgMzgxMSAwIC0wLjMxNSAtMSAwLjMzNTc0IC0xNC42NjEzIC0xIDQuNzIyMDggLTE0LjY2MTMgMTgwIDI3MCAzNjAgMTc5Ljk5OSAyNjkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDUzMSAyMjQ5NTkgMTY4NTU4Nzc5OSAyOCA0MTczIDQxNzcgMCAtMC4zMTUgLTEgNC40MDg3NyAtMTQuNjYxMyAtMSA1LjY2MjAxIC0xNC42NjEzIDI3MCAzNjAgMzYwIDI2OS45OTkgMzU5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA1MzEgMjI1NzQ5IDE2ODU1ODgyNjkgMjkgNDUzOSA0NTQzIDAgLTAuMjI1IC0xIDUuNjYyMDEgLTE0LjY2MTMgLTEgMS41ODg5OCAtMTQuNjYxMyAwIDkwIDM2MCAtMC4wMDA2MzU1OTMgODkuOTIzMSAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA1MzEgMjMwNDI1IDE2ODU1ODg2NjUgMzAgNDkwNSA0OTA5IDAgLTAuMjI1IC0xIDEuNTg4OTggLTE0LjY2MTMgLTEgMC4zMzU3NCAtMTQuNjYxMyA5MCAxODAgMzYwIDg5Ljk5OTQgMTc5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA1MzEgMjMxMTAyIDE2ODU1ODkwNjIgMzEgNTI3MSA1Mjc1IDAgLTAuMjI1IC0xIC0wLjI5MDg4IC0xNC42NjEzIC0xIDQuNDA4NzcgLTE0LjY2MTMgMTgwIDI3MCAzNjAgMTc5Ljk5OSAyNjkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDUzMSAyMzE3MzggMTY4NTU4OTQ1OCAzMiA1NjM3IDU2NDEgMCAtMC4yMjUgLTEgNC4wOTU0NiAtMTQuNjYxMyAtMSA1LjY2MjAxIC0xNC42NjEzIDI3MCAzNjAgMzYwIDI2OS45OTkgMzU5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA1MzEgMjMyNTI4IDE2ODU1ODk5MjggMzMgNjAwMyA2MDA3IDAgLTAuMTM1IC0xIDUuOTc1MzIgLTE0LjY2MTMgLTEgMS41ODg5OCAtMTQuNjYxMyAwIDkwIDM2MCAtMC4wMDA2MzU1OTMgODkuOTIzMSAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA1MzEgMjMzMjA0IDE2ODU1OTAzMjQgMzQgNjM2OSA2MzczIDAgLTAuMTM1IC0xIDEuNTg4OTggLTE0LjY2MTMgLTEgMC4zMzU3NCAtMTQuNjYxMyA5MCAxODAgMzYwIDg5Ljk5OTQgMTc5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA1MzEgMjMzODQwIDE2ODU1OTA3MjAgMzUgNjczNSA2NzM5IDAgLTAuMTM1IC0xIDAuMDIyNDMgLTE0LjY2MTMgLTEgNC40MDg3NyAtMTQuNjYxMyAxODAgMjcwIDM2MCAxNzkuOTk5IDI2OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNTMxIDIzNDUxNiAxNjg1NTkxMTE2IDM2IDcxMDEgNzEwNSAwIC0wLjEzNSAtMSA0LjcyMjA4IC0xNC42NjEzIC0xIDUuOTc1MzIgLTE0LjY2MTMgMjcwIDM2MCAzNjAgMjY5Ljk5OSAzNTkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDUzMSAyMzUzMDYgMTY4NTU5MTU4NiAzNyA3NDY3IDc0NzEgMCAtMC4wNDUgLTEgNS42NjIwMSAtMTQuNjYxMyAtMSAxLjI3NTY3IC0xNC42NjEzIDAgOTAgMzYwIC0wLjAwMDYzNTU5MyA4OS45MjMxIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDUzMSAyMzU5NDIgMTY4NTU5MTk4MiAzOCA3ODMzIDc4MzcgMCAtMC4wNDUgLTEgMS4yNzU2NyAtMTQuNjYxMyAtMSAwLjMzNTc0IC0xNC42NjEzIDkwIDE4MCAzNjAgODkuOTk5NCAxNzkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMDA2MTggMTY4NTU5MjM3OCAzOSA4MTk5IDgyMDMgMCAtMC4wNDUgLTEgMC4zMzU3NCAtMTQuNjYxMyAtMSA0LjA5NTQ2IC0xNC42NjEzIDE4MCAyNzAgMzYwIDE3OS45OTkgMjY5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA2MDEgMDAxMjU0IDE2ODU1OTI3NzQgNDAgODU2NSA4NTY5IDAgLTAuMDQ1IC0xIDQuNDA4NzcgLTE0LjY2MTMgLTEgNS42NjIwMSAtMTQuNjYxMyAyNzAgMzYwIDM2MCAyNjkuOTk5IDM1OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNjAxIDAwMjA0NCAxNjg1NTkzMjQ0IDQxIDg5MzEgODkzNSAwIDAuMDQ1IC0xIDUuMzQ4NyAtMTQuNjYxMyAtMSAxLjI3NTY3IC0xNC42NjEzIDAgOTAgMzYwIC0wLjAwMDYzNTU5MyA4OS45MjMxIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMDI3MjAgMTY4NTU5MzY0MCA0MiA5Mjk3IDkzMDEgMCAwLjA0NSAtMSAxLjI3NTY3IC0xNC42NjEzIC0xIDAuMDIyNDMgLTE0LjY2MTMgOTAgMTgwIDM2MCA4OS45OTk0IDE3OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNjAxIDAwMzM1NiAxNjg1NTk0MDM2IDQzIDk2NjMgOTY2NyAwIDAuMDQ1IC0xIDAuMDIyNDMgLTE0LjY2MTMgLTEgNC40MDg3NyAtMTQuNjYxMyAxODAgMjcwIDM2MCAxNzkuOTk5IDI2OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNjAxIDAwNDAzMiAxNjg1NTk0NDMyIDQ0IDEwMDI5IDEwMDMzIDAgMC4wNDUgLTEgNC4wOTU0NiAtMTQuNjYxMyAtMSA1LjY2MjAxIC0xNC42NjEzIDI3MCAzNjAgMzYwIDI2OS45OTkgMzU5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA2MDEgMDA0ODIyIDE2ODU1OTQ5MDIgNDUgMTAzOTUgMTAzOTkgMCAwLjEzNSAtMSA1LjY2MjAxIC0xNC42NjEzIC0xIDEuMjc1NjcgLTE0LjY2MTMgMCA5MCAzNjAgLTAuMDAwNjM1NTkzIDg5LjkyMzEgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNjAxIDAwNTQ1OCAxNjg1NTk1Mjk4IDQ2IDEwNzYxIDEwNzY1IDAgMC4xMzUgLTEgMS4yNzU2NyAtMTQuNjYxMyAtMSAwLjMzNTc0IC0xNC42NjEzIDkwIDE4MCAzNjAgODkuOTk5NCAxNzkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMTAxMzQgMTY4NTU5NTY5NCA0NyAxMTEyNyAxMTEzMSAwIDAuMTM1IC0xIDAuMDIyNDMgLTE0LjY2MTMgLTEgMy43ODIxNSAtMTQuNjYxMyAxODAgMjcwIDM2MCAxNzkuOTk5IDI2OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNjAxIDAxMDgxMCAxNjg1NTk2MDkwIDQ4IDExNDkzIDExNDk3IDAgMC4xMzUgLTEgNC4wOTU0NiAtMTQuNjYxMyAtMSA1LjY2MjAxIC0xNC42NjEzIDI3MCAzNjAgMzYwIDI2OS45OTkgMzU5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA2MDEgMDExNjAwIDE2ODU1OTY1NjAgNDkgMTE4NTkgMTE4NjMgMCAwLjIyNSAtMSA1LjM0ODcgLTE0LjY2MTMgLTEgMS4yNzU2NyAtMTQuNjYxMyAwIDkwIDM2MCAtMC4wMDA2MzU1OTMgODkuOTIzMSAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA2MDEgMDEyMjM2IDE2ODU1OTY5NTYgNTAgMTIyMjUgMTIyMjkgMCAwLjIyNSAtMSAwLjk2MjM2IC0xNC42NjEzIC0xIC0wLjI5MDg4IC0xNC42NjEzIDkwIDE4MCAzNjAgODkuOTk5NCAxNzkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMTI5MTMgMTY4NTU5NzM1MyA1MSAxMjU5MSAxMjU5NSAwIDAuMjI1IC0xIC0wLjI5MDg4IC0xNC42NjEzIC0xIDMuNzgyMTUgLTE0LjY2MTMgMTgwIDI3MCAzNjAgMTc5Ljk5OSAyNjkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMTM1NDkgMTY4NTU5Nzc0OSA1MiAxMjk1NyAxMjk2MSAwIDAuMjI1IC0xIDQuMDk1NDYgLTE0LjY2MTMgLTEgNS4zNDg3IC0xNC42NjEzIDI3MCAzNjAgMzYwIDI2OS45OTkgMzU5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA2MDEgMDE0MzM5IDE2ODU1OTgyMTkgNTMgMTMzMjMgMTMzMjcgMCAwLjMxNSAtMSA1LjY2MjAxIC0xNC42NjEzIC0xIDEuMjc1NjcgLTE0LjY2MTMgMCA5MCAzNjAgLTAuMDAwNjM1NTkzIDg5LjkyMzEgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNjAxIDAxNTAxNSAxNjg1NTk4NjE1IDU0IDEzNjg5IDEzNjkzIDAgMC4zMTUgLTEgMC45NjIzNiAtMTQuNjYxMyAtMSAwLjAyMjQzIC0xNC42NjEzIDkwIDE4MCAzNjAgODkuOTk5NCAxNzkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMTU2NTIgMTY4NTU5OTAxMiA1NSAxNDA1NSAxNDA1OSAwIDAuMzE1IC0xIC0wLjI5MDg4IC0xNC42NjEzIC0xIDQuMDk1NDYgLTE0LjY2MTMgMTgwIDI3MCAzNjAgMTc5Ljk5OSAyNjkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMjAzMjcgMTY4NTU5OTQwNyA1NiAxNDQyMSAxNDQyNSAwIDAuMzE1IC0xIDQuMDk1NDYgLTE0LjY2MTMgLTEgNS42NjIwMSAtMTQuNjYxMyAyNzAgMzYwIDM2MCAyNjkuOTk5IDM1OS45MjMgMzYwIDAuMjQ5Nzg4IDEgMCAxIDAgcmV0aWdhCjIwMjMwNjAxIDAyMTExNyAxNjg1NTk5ODc3IDU3IDE0Nzg3IDE0NzkxIDAgMC40MDUgLTEgNS45NzUzMiAtMTQuNjYxMyAtMSAxLjU4ODk4IC0xNC42NjEzIDAgOTAgMzYwIC0wLjAwMDYzNTU5MyA4OS45MjMxIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMjE3NTMgMTY4NTYwMDI3MyA1OCAxNTE1MyAxNTE1NyAwIDAuNDA1IC0xIDEuMjc1NjcgLTE0LjY2MTMgLTEgMC4wMjI0MyAtMTQuNjYxMyA5MCAxODAgMzYwIDg5Ljk5OTQgMTc5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2EKMjAyMzA2MDEgMDIyNDI5IDE2ODU2MDA2NjkgNTkgMTU1MTkgMTU1MjMgMCAwLjQwNSAtMSAwLjMzNTc0IC0xNC42NjEzIC0xIDQuMDk1NDYgLTE0LjY2MTMgMTgwIDI3MCAzNjAgMTc5Ljk5OSAyNjkuOTIzIDM2MCAwLjI0OTc4OCAxIDAgMSAwIHJldGlnYQoyMDIzMDYwMSAwMjMxMDUgMTY4NTYwMTA2NSA2MCAxNTg4NSAxNTg4OSAwIDAuNDA1IC0xIDQuMDk1NDYgLTE0LjY2MTMgLTEgNS4zNDg3IC0xNC42NjEzIDI3MCAzNjAgMzYwIDI2OS45OTkgMzU5LjkyMyAzNjAgMC4yNDk3ODggMSAwIDEgMCByZXRpZ2E="
	    }
	  ]
	} 
	"""



	tabs=[]
	for item in json.loads(metadata)["metadata"]:
			
			type=item["type"]
			filename=item["filename"]
			if type=="b64encode":
				# binary
				import base64
				base64_s=item["encoded"]
				body=base64.b64decode(base64_s).decode("utf-8")
			else:
				# json
				body=json.dumps(item,indent=2)
				base64_s = base64.b64encode(bytes(body, 'utf-8')).decode('utf-8') 


			base64_s='data:application/octet-stream;base64,' + base64_s

			from bokeh.models.callbacks import CustomJS
			download_button=Button(label="download")
			download_button.js_on_click(CustomJS(args=dict(base64_s=base64_s,filename=filename), code="""
				fetch(base64_s, {cache: "no-store"}).then(response => response.blob())
				    .then(blob => {
				        if (navigator.msSaveBlob) {
				            navigator.msSaveBlob(blob, filename);
				        }
				        else {
				            const link = document.createElement('a')
				            link.href = URL.createObjectURL(blob)
				            link.download = filename
				            link.target = '_blank'
				            link.style.visibility = 'hidden'
				            link.dispatchEvent(new MouseEvent('click'))
				        }
				        return response.text();
				    });
				"""))
			
			panel=TabPanel(child=Column(download_button,Div(text=f"<div><pre><code>{body}</code></pre></div>")), title=os.path.basename(filename))
			tabs.append(panel)

	view.metadata.children=[Tabs(tabs=tabs)]
	
	# /////////////////////////////////////////////

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

	

