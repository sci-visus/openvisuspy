import os, sys
import argparse,json
import panel as pn
import logging
import base64,json

from openvisuspy import SetupLogger, Slice, GetQueryParams

# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	# https://github.com/holoviz/panel/issues/3404
	# https://panel.holoviz.org/api/config.html
	pn.extension(
		'bokeh',
		"floatpanel",
		log_level ="DEBUG",
		notifications=True, 
		sizing_mode="stretch_width",
		# template="fast",
		#theme="default",
	)

	log_filename=os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME","/tmp/openvisuspy-dashboards.log")
	logger=SetupLogger(log_filename=log_filename,logging_level=logging.DEBUG)

	view = Slice()
	view.load(sys.argv[1])
	
	query_params=GetQueryParams()
	if "load" in query_params:
		body=json.loads(base64.b64decode(query_params['load']).decode("utf-8"))
		view.setSceneBody(body)
	elif "dataset" in query_params:
		view.setScene(query_params["dataset"])

	app = view.getMainLayout()
	app.servable()

