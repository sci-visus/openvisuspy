import os
import sys
import logging
import base64
import json
import panel as pn

from openvisuspy import SetupLogger, Slice, ProbeTool,cbool


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

    # in case you want to enable the probe
    if False:
        if "--probe" in sys.argv or cbool(query_params.get("probe",False))==True:
            pass

    main_layout.servable()

