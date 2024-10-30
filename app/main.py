import os
import sys
import logging
import base64
import json
import panel as pn

from openvisuspy import SetupLogger, Slice, ProbeTool,cbool

# ////////////////////////////////////////////////////////////////////////////
def SyncSlices(slice1, slice2, box1=None, box2=None):

	if box1 is None: 
		box1=slice1.db.getPhysicBox()

	if box2 is None:
		box2=slice2.db.getPhysicBox()

	# map box1 to box2
	(a, b), (c, d)=box1
	(A, B), (C, D)=box2

	x, y, w, h = slice1.canvas.getViewport()
	x1, x2 = [A + ((value - a) / (b - a)) * (B - A) for value in [x, x + w]]
	y1, y2 = [C + ((value - c) / (d - c)) * (D - C) for value in [y, y + h]]
	slice2.canvas.setViewport([x1, y1, x2 - x1, y2 - y1])
	slice2.refresh("SyncSlices")

# ////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	pn.extension(
		"ipywidgets",
		"floatpanel",
		"codeeditor",
		log_level="DEBUG",
		notifications=True,
		sizing_mode="stretch_width"
	)

	query_params = {k: v for k,v in pn.state.location.query_params.items()}

	log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "/tmp/openvisuspy-dashboards.log")
	logger = SetupLogger(log_filename=log_filename, logging_level=logging.DEBUG)

	# sync view
	if len(sys.argv[1:])==2:

		from openvisuspy.utils import SafeCallback
		from panel import Column, Row

		slice1 = Slice();slice1.load(sys.argv[1])
		slice2 = Slice();slice2.load(sys.argv[2])
		
		show_options = {
			"top": [
				[
					"palette",
					"color_mapper_type",
					"resolution",
					"num_refinements",
					"field", 
					"range_mode", 
					"range_min", 
					"range_max"
				],
			],
			# "bottom": [["request", "response"]],
		}
		slice1.setShowOptions(show_options)
		slice2.setShowOptions(show_options)
		slice1.scene_body.param.watch( SafeCallback(lambda evt: SyncSlices(slice1,slice2)), "value", onlychanged=True, queued=True)
		main_layout = pn.Row(slice1.getMainLayout(), slice2.getMainLayout())
		main_layout.servable()

	else:

		slice = Slice()
		slice.load(sys.argv[1])

		# load a whole scene
		if "load" in query_params:
			body = json.loads(base64.b64decode(query_params['load']).decode("utf-8"))
			slice.setBody(body)

		# select from list of choices
		elif "dataset" in query_params:
			scene_name = query_params["dataset"]
			slice.scene.value = scene_name

		main_layout = slice.getMainLayout()
		main_layout.servable()

