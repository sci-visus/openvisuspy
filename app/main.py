import os
import sys
import logging
import base64
import json
import panel as pn

from openvisuspy import SetupLogger, Slice, ProbeTool, GetQueryParams

# /////////////////////////////////////////////////////////////////////////////////
class DashboardApp:

    # constructor
    def __init__(self, config):
        self.slice = Slice()
        self.slice.load(config)
        self.setup_logging()
        self.setup_layout()

    # setup_logging
    def setup_logging(self):
        log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "/tmp/openvisuspy-dashboards.log")
        self.logger = SetupLogger(log_filename=log_filename, logging_level=logging.DEBUG)

    # setup_layout
    def setup_layout(self):
        query_params = GetQueryParams()
        if "load" in query_params:
            body = json.loads(base64.b64decode(query_params['load']).decode("utf-8"))
            self.slice.setSceneBody(body)
        elif "dataset" in query_params:
            scene_name = query_params["dataset"]
            self.slice.scene.value = scene_name

        # in case you want to enable the probe
        if "--probe" in sys.argv:
            self.app = ProbeTool(self.slice).getMainLayout()
        else:
            self.app = self.slice.getMainLayout()

    def servable(self):
        return self.app

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
    config = sys.argv[1] 
    app_instance = DashboardApp(config)
    app_instance.servable().servable()
