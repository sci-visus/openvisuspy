import os
import sys
import logging
import base64
import json
import panel as pn
from openvisuspy import SetupLogger, Slice, ProbeTool, cbool
import time

# Global synchronization lock and throttle variables
sync_in_progress = False
last_sync_time = 0
throttle_delay = 0.1  # Throttle delay in seconds

# ////////////////////////////////////////////////////////////////////////////

def throttle(func, *args, **kwargs):
    """Throttle function calls to limit frequency."""
    global last_sync_time
    current_time = time.time()
    if current_time - last_sync_time >= throttle_delay:
        last_sync_time = current_time
        func(*args, **kwargs)

def SyncSlices(slice1, slice2, box1=None, box2=None):
    """Synchronize from slice1 (original) to slice2 (super-resolution)"""
    global sync_in_progress
    if sync_in_progress:
        return  # Prevent re-entrant synchronization

    sync_in_progress = True
    try:
        if box1 is None: 
            box1 = slice1.db.getPhysicBox()
        if box2 is None:
            box2 = slice2.db.getPhysicBox()

        # Map box1 to box2
        (a, b), (c, d) = box1
        (A, B), (C, D) = box2

        x, y, w, h = slice1.canvas.getViewport()

        x1, x2 = [A + ((value - a) / (b - a)) * (B - A) for value in [x, x + w]]
        y1, y2 = [C + ((value - c) / (d - c)) * (D - C) for value in [y, y + h]]
        slice2.canvas.setViewport([x1, y1, x2 - x1, y2 - y1])
        slice2.refresh("SyncSlices")
    finally:
        sync_in_progress = False

def SyncSlicesReverse(slice2, slice1, box1=None, box2=None):
    """Synchronize from slice2 (super-resolution) to slice1 (original)"""
    global sync_in_progress
    if sync_in_progress:
        return  # Prevent re-entrant synchronization

    sync_in_progress = True
    try:
        if box1 is None: 
            box1 = slice1.db.getPhysicBox()
        if box2 is None:
            box2 = slice2.db.getPhysicBox()

        # Map box2 to box1
        (A, B), (C, D) = box2
        (a, b), (c, d) = box1

        x, y, w, h = slice2.canvas.getViewport()

        x1, x2 = [a + ((value - A) / (B - A)) * (b - a) for value in [x, x + w]]
        y1, y2 = [c + ((value - C) / (D - C)) * (d - c) for value in [y, y + h]]
        slice1.canvas.setViewport([x1, y1, x2 - x1, y2 - y1])
        slice1.refresh("SyncSlicesReverse")
    finally:
        sync_in_progress = False

# ////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

    pn.extension(
        "ipywidgets",
        "floatpanel",
        "codeeditor",
        log_level="DEBUG",
        notifications=True,
    )

    query_params = {k: v for k, v in pn.state.location.query_params.items()}

    log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "/tmp/openvisuspy-dashboards.log")
    logger = SetupLogger(log_filename=log_filename, logging_level=logging.DEBUG)

    # Sync view
    if len(sys.argv[1:]) == 2:

        slice1 = Slice()
        slice1.load(sys.argv[1])
        slice2 = Slice()
        slice2.load(sys.argv[2])

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
        }
        slice1.setShowOptions(show_options)
        slice2.setShowOptions(show_options)

        # Define update functions with throttling
        def update_slice2(attr, old, new):
            throttle(SyncSlices, slice1, slice2)

        def update_slice1(attr, old, new):
            throttle(SyncSlicesReverse, slice2, slice1)

        # Watch for viewport changes in slice1 and slice2 using on_change
        slice1.canvas.fig.x_range.on_change('start', update_slice2)
        slice1.canvas.fig.x_range.on_change('end', update_slice2)
        slice1.canvas.fig.y_range.on_change('start', update_slice2)
        slice1.canvas.fig.y_range.on_change('end', update_slice2)

        slice2.canvas.fig.x_range.on_change('start', update_slice1)
        slice2.canvas.fig.x_range.on_change('end', update_slice1)
        slice2.canvas.fig.y_range.on_change('start', update_slice1)
        slice2.canvas.fig.y_range.on_change('end', update_slice1)

        # Layout for both slices
        main_layout = pn.Row(slice1.getMainLayout(), slice2.getMainLayout())
        main_layout.servable()

    else:
        slice = Slice()
        slice.load(sys.argv[1])

        # Load a whole scene
        if "load" in query_params:
            body = json.loads(base64.b64decode(query_params['load']).decode("utf-8"))
            slice.setBody(body)

        # Select from list of choices
        elif "dataset" in query_params:
            scene_name = query_params["dataset"]
            slice.scene.value = scene_name

        main_layout = slice.getMainLayout()
        main_layout.servable()
