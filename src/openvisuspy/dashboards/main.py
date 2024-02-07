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
		template="fast",
		#theme="default"
	)

	log_filename=os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME","/tmp/openvisuspy-dashboards.log")
	logger=SetupLogger(log_filename=log_filename,logging_level=logging.DEBUG)

	view = Slice()
	view.setScenes(sys.argv[1], params=GetQueryParams())
	app = view.getMainLayout()
	app.servable()

