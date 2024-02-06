import os, sys
import argparse,json
import panel as pn
import logging
import base64,json

pn.extension("floatpanel")
pn.config.notifications = True

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):


	from openvisuspy import SetupLogger, IsPanelServe, GetBackend, Slices

	logger=SetupLogger(stream=True, log_filename=os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME","/tmp/openvisuspy-dashboards.log"),logging_level=logging.DEBUG)
	logger.info(f"GetBackend()={GetBackend()}")

	# serving a single dataset
	if "--dataset" in sys.argv:

		parser = argparse.ArgumentParser(description="Dashboard")
		parser.add_argument("--dataset", type=str, help="action name", required=True)	
		parser.add_argument("--name", type=str, default=None,help="name", required=False)
		parser.add_argument("--palette", type=str, default=None,help="palette", required=False)	
		parser.add_argument("--palette-range", type=str, default=None,help="palette range", required=False)	
		args = parser.parse_args(sys.argv[1:])

		config={
	      "name": args.name if args.name is not None else os.path.basename(args.dataset),
	      "url": args.dataset,
				"palette": {
					"name": args.palette,
					"range": eval(args.palette_range) if args.palette_range else None,
				}}
		config={"datasets": [config]}

	else:
		# is a filename
		config=sys.argv[1]

	# coming from user
	query_params={k: v for k,v in pn.state.location.query_params.items()}

	view = Slices()

	view.setDashboardsConfig(config)
	datasets=view.getDatasets()

	# set a default dataset
	if True:
		if "load" in query_params:
			decoded=base64.b64decode(query_params['load']).decode("utf-8")
			scene=json.loads(decoded)
		else:
			dataset=query_params.get("dataset",datasets[0] if datasets else None)
			if dataset:
				scene=view.getDashboardsConfig(dataset)

	if scene is not None:
		#logger.info(f"Opening from {scene}")
		view.loadScene(scene)

	main_layout = view.getMainLayout()

	if False:
		template = pn.template.MaterialTemplate(
			title='NSDF Dashboard',
			theme="default", # dark
			site_url ="https://nationalsciencedatafabric.org/",
			header_background="#101020",
			logo ="https://www.sci.utah.edu/~pascucci/public/NSDF-smaller.PNG",)
		template.main.append(main_layout)
		main_layout=template

	main_layout.servable()

