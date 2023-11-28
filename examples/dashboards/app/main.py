import os, sys
import argparse,json

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	from openvisuspy import SetupLogger, IsPanelServe, GetBackend, Slices

	logger=SetupLogger(stream=True, log_filename=os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME","/tmp/openvisuspy-dashboards.log"))
	logger.info(f"GetBackend()={GetBackend()}")

	if "--dataset" in sys.argv:
		parser = argparse.ArgumentParser(description="Dashboard")
		parser.add_argument("--dataset", type=str, help="action name", required=True)	
		parser.add_argument("--name", type=str, default=None,help="name", required=False)
		parser.add_argument("--palette", type=str, default=None,help="palette", required=False)	
		parser.add_argument("--palette-range", type=str, default=None,help="palette range", required=False)	
		args = parser.parse_args(sys.argv[1:])

		config={
			"name" : args.name if args.name is not None else os.path.basename(args.dataset),
			"url" : args.dataset
		}

		if args.palette is not None:
			config["palette"]=args.palette

		if args.palette_range is not None:
			config["palette-range"]=eval(args.palette_range)

		config={"datasets" : [config]}

	else:
		# assuming is a json file
		config=sys.argv[1]



	is_panel = IsPanelServe()
	if is_panel:
		import panel as pn
		doc = None
		user_args={}
	else:
		import bokeh
		doc = bokeh.io.curdoc()
		doc.theme = 'light_minimal'
		user_args={k: v[0].decode('ascii') for k,v in bokeh.io.curdoc().session_context.request.arguments.items()}

	view = Slices(doc=doc, is_panel=is_panel)
	view.setShowOptions([
		["view_mode","datasets", "palette", "resolution", "view_dep", "num_refinements", "colormapper_type", "show_metadata", "logout"],
		["datasets", "direction", "offset", "colormapper_type", "palette_range_mode", "palette_range_vmin",
		 "palette_range_vmax", "show-probe"]
	])
	
	view.setConfig(config)

	datasets=view.getDatasets()
	dataset=user_args.get("dataset",None)
	if not dataset and len(datasets): 
		dataset=datasets[0]

	if dataset is not None:
		view.setDataset(dataset, force=True)

	if is_panel:
		main_layout = view.getMainLayout()
		use_template = True
		if use_template:
			template = pn.template.MaterialTemplate(title='NSDF Dashboard')
			template.main.append(main_layout)
			template.servable()
		else:
			main_layout.servable()
	else:

		main_layout = view.getMainLayout()
		doc.add_root(main_layout)
