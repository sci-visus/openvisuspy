import os
import sys
import logging
import base64
import json
import panel as pn
from openvisuspy import SetupLogger, Slice, ProbeTool, cbool
import time

class SliceSynchronizer:
    def __init__(self, slice1, slice2, throttle_delay=0.05):
        self.slice1 = slice1
        self.slice2 = slice2
        self.sync_in_progress = False
        self.last_sync_time = 0
        self.throttle_delay = throttle_delay

    def throttle(self, func, *args, **kwargs):
        """Throttle function calls to limit frequency."""
        current_time = time.time()
        if current_time - self.last_sync_time >= self.throttle_delay:
            self.last_sync_time = current_time
            func(*args, **kwargs)

    def sync_slices(self, box1=None, box2=None, is_reverse=False):
        """Synchronize viewports between two slices, with an option to reverse the direction."""
        if self.sync_in_progress:
            return
        self.sync_in_progress = True
        try:
            # Set default boxes if not provided
            if box1 is None:
                box1 = self.slice1.db.getPhysicBox()
            if box2 is None:
                box2 = self.slice2.db.getPhysicBox()

            # Determine source and target based on is_reverse flag
            if is_reverse:
                (src_box, tgt_box) = (box2, box1)
                (src_slice, tgt_slice) = (self.slice2, self.slice1)
            else:
                (src_box, tgt_box) = (box1, box2)
                (src_slice, tgt_slice) = (self.slice1, self.slice2)

            # Unpack source and target boxes
            (a, b), (c, d) = src_box
            (A, B), (C, D) = tgt_box

            # Get viewport from the source slice
            x, y, w, h = src_slice.canvas.getViewport()

            # Map coordinates from source to target
            x1, x2 = [A + ((value - a) / (b - a)) * (B - A) for value in [x, x + w]]
            y1, y2 = [C + ((value - c) / (d - c)) * (D - C) for value in [y, y + h]]

            # Set the target slice's viewport and refresh
            tgt_slice.canvas.setViewport([x1, y1, x2 - x1, y2 - y1])
            tgt_slice.refresh("SyncSlices")
        finally:
            self.sync_in_progress = False

    def update_slice2(self, attr, old, new):
        """Throttle and synchronize slice1 -> slice2."""
        self.throttle(self.sync_slices, is_reverse=False)

    def update_slice1(self, attr, old, new):
        """Throttle and synchronize slice2 -> slice1 (reverse direction)."""
        self.throttle(self.sync_slices, is_reverse=True)


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

        # Initialize the synchronizer
        synchronizer = SliceSynchronizer(slice1, slice2, throttle_delay = 0.05)

        # Watch for viewport changes in slice1 and slice2 using on_change
        slice1.canvas.fig.x_range.on_change('start', synchronizer.update_slice2)
        slice1.canvas.fig.x_range.on_change('end', synchronizer.update_slice2)
        slice1.canvas.fig.y_range.on_change('start', synchronizer.update_slice2)
        slice1.canvas.fig.y_range.on_change('end', synchronizer.update_slice2)

        slice2.canvas.fig.x_range.on_change('start', synchronizer.update_slice1)
        slice2.canvas.fig.x_range.on_change('end', synchronizer.update_slice1)
        slice2.canvas.fig.y_range.on_change('start', synchronizer.update_slice1)
        slice2.canvas.fig.y_range.on_change('end', synchronizer.update_slice1)

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
