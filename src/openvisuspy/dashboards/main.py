import os, sys
import argparse,json
import panel as pn
import logging
import base64,json

from openvisuspy import SetupLogger, Slice, ProbeTool, GetQueryParams

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

	slice = Slice()
	slice.load(sys.argv[1])
	
	query_params=GetQueryParams()
	if "load" in query_params:
		body=json.loads(base64.b64decode(query_params['load']).decode("utf-8"))
		slice.setSceneBody(body)
	elif "dataset" in query_params:
		slice.setScene(query_params["dataset"])

	if False:
		probe=ProbeTool(slice)
		app = probe.getMainLayout()
	else:
		app = slice.getMainLayout()


	# example 
	if True:

		def ShowDetails(geometry):

			x1,y1=float(geometry["x0"]),float(geometry["y0"])
			x2,y2=float(geometry["x1"]),float(geometry["y1"])
			logic_box=slice.toLogic([(x1,y1),(x2,y2)])

			from matplotlib.figure import Figure
			import openvisuspy as ovy
			import panel as pn
			data=list(ovy.ExecuteBoxQuery(slice.db, access=slice.db.createAccess(), logic_box=logic_box,num_refinements=1))[0]["data"]

			fig = Figure(figsize=(4, 3))
			ax = fig.subplots()
			im=ax.imshow(data)
			fig.colorbar(im, ax=ax)
			dialog = pn.pane.Matplotlib(fig)
			slice.showDialog(dialog, name="Example")

		from bokeh.events import SelectionGeometry
		slice.canvas.on_event(SelectionGeometry,ShowDetails)


	app.servable()

