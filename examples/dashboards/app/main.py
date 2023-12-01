import os, sys
import argparse,json
import panel as pn
import logging
pn.extension("floatpanel")

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	if False:

		w=pn.Column(pn.widgets.Button(name="hello"),styles={"background": "blue"}, sizing_mode="stretch_both",width_policy='max',height_policy ="max", )
		app = pn.FloatPanel(
			w,
			name="Settings",
			contained=False,
			width=1024,height=800,
			width_policy='max',height_policy ="max", )

		app.servable()
	else:

		from openvisuspy import SetupLogger, IsPanelServe, GetBackend, Slices

		logger=SetupLogger(stream=True, log_filename=os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME","/tmp/openvisuspy-dashboards.log"),logging_level=logging.INFO)
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

			query_params={k: v for k,v in pn.state.location.query_params.items()}

			view = Slices()
			view.setShowOptions([
				["view_mode","datasets", "palette", "resolution", "view_dep", "num_refinements", "log_colormapper", "show_metadata", "logout"],
				["datasets", "direction", "offset", "log_colormapper", "palette_range_mode", "palette_range_vmin",  "palette_range_vmax"]
			])
			
			view.setConfig(config)

			datasets=view.getDatasets()
			dataset=query_params.get("dataset",None)
			if not dataset and len(datasets): 
				dataset=datasets[0]

			if dataset is not None:
				view.setDataset(dataset, force=True)


			main_layout = view.getMainLayout()
			use_template = False
			if use_template:
				template = pn.template.MaterialTemplate(title='NSDF Dashboard')
				template.main.append(main_layout)
				template.servable()
			else:
				main_layout.servable()
