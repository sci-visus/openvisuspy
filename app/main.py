import os
import sys
import logging
import panel as pn
from openvisuspy import SetupLogger, Slice
from bokeh.models import CustomJS
from threading import Timer


class SliceSynchronizer:
    def __init__(self, slice1, slice2, scale_factor=1):
        self.slice1 = slice1
        self.slice2 = slice2
        self.scale_factor = scale_factor
        self.debounce_timer = None  # Timer to debounce refresh calls
        self.debounce_delay = 0.1  # Delay in seconds for debounce

        # Link ranges with JavaScript callbacks
        self.link_ranges()

    def link_ranges(self):
        """Link the x_range and y_range of slice1 and slice2 using JavaScript callbacks."""
        fig1, fig2 = self.slice1.canvas.fig, self.slice2.canvas.fig

        # JavaScript for synchronizing slice2 based on slice1
        js_code_slice1_to_slice2 = """
            fig2.x_range.start = fig1.x_range.start * scale_factor;
            fig2.x_range.end = fig1.x_range.end * scale_factor;
            fig2.y_range.start = fig1.y_range.start * scale_factor;
            fig2.y_range.end = fig1.y_range.end * scale_factor;
        """

        # JavaScript for synchronizing slice1 based on slice2
        js_code_slice2_to_slice1 = """
            fig1.x_range.start = fig2.x_range.start / scale_factor;
            fig1.x_range.end = fig2.x_range.end / scale_factor;
            fig1.y_range.start = fig2.y_range.start / scale_factor;
            fig1.y_range.end = fig2.y_range.end / scale_factor;
        """

        # Create JavaScript callbacks
        callback_slice1_to_slice2 = CustomJS(
            args=dict(fig1=fig1, fig2=fig2, scale_factor=self.scale_factor),
            code=js_code_slice1_to_slice2
        )
        callback_slice2_to_slice1 = CustomJS(
            args=dict(fig1=fig1, fig2=fig2, scale_factor=self.scale_factor),
            code=js_code_slice2_to_slice1
        )

        # Attach JavaScript callbacks for x_range and y_range synchronization
        fig1.x_range.js_on_change('start', callback_slice1_to_slice2)
        fig1.x_range.js_on_change('end', callback_slice1_to_slice2)
        fig1.y_range.js_on_change('start', callback_slice1_to_slice2)
        fig1.y_range.js_on_change('end', callback_slice1_to_slice2)

        fig2.x_range.js_on_change('start', callback_slice2_to_slice1)
        fig2.x_range.js_on_change('end', callback_slice2_to_slice1)
        fig2.y_range.js_on_change('start', callback_slice2_to_slice1)
        fig2.y_range.js_on_change('end', callback_slice2_to_slice1)

        # Attach Python-side refresh using a timer for debouncing
        self.attach_refresh(fig1, fig2)

    def attach_refresh(self, fig1, fig2):
        """Attach Python-side refresh with debouncing."""
        def trigger_refresh():
            """Trigger refresh for both slices."""
            self.slice1.refresh("DebouncedSyncFromSlice2")
            self.slice2.refresh("DebouncedSyncFromSlice1")

        def debounce_refresh(attr, old, new):
            """Debounce refresh calls."""
            if self.debounce_timer:
                self.debounce_timer.cancel()

            # Schedule the refresh after the debounce delay
            self.debounce_timer = Timer(self.debounce_delay, trigger_refresh)
            self.debounce_timer.start()

        # Attach Python refresh debounce to all range changes
        fig1.x_range.on_change('start', debounce_refresh)
        fig1.x_range.on_change('end', debounce_refresh)
        fig1.y_range.on_change('start', debounce_refresh)
        fig1.y_range.on_change('end', debounce_refresh)

        fig2.x_range.on_change('start', debounce_refresh)
        fig2.x_range.on_change('end', debounce_refresh)
        fig2.y_range.on_change('start', debounce_refresh)
        fig2.y_range.on_change('end', debounce_refresh)


if __name__.startswith('bokeh'):
    pn.extension()

    log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "/tmp/openvisuspy-dashboards.log")
    logger = SetupLogger(log_filename=log_filename, logging_level=logging.DEBUG)

    if len(sys.argv[1:]) == 2:
        # Load slices
        slice1 = Slice()
        slice1.load(sys.argv[1])
        print("imhere1")
        slice2 = Slice()
        slice2.load(sys.argv[2])
        print("imhere2")

        # Print initial x_range of both slices
        fig1 = slice1.canvas.fig
        fig2 = slice2.canvas.fig
        print("imhere3")
        print(f"Initial_x_range_of_slice1: {fig1.x_range.start}, {fig1.x_range.end}")
        print(f"Initial x_range of slice2: {fig2.x_range.start}, {fig2.x_range.end}")

        # Compute scale factor
        box1 = slice1.db.getPhysicBox()
        box2 = slice2.db.getPhysicBox()
        scale_factor = box2[0][1] / box1[0][1]  # Scaling based on x-axis

        # Show options for both slices
        show_options = {
            "top": [["palette", "color_mapper_type", "resolution", "field", "range_mode", "range_min", "range_max"]],
            "bottom": [["request", "response", "view_dependent"]],
        }
        slice1.setShowOptions(show_options)
        slice2.setShowOptions(show_options)

        # Stretch both figures
        slice1.canvas.fig.sizing_mode = 'stretch_both'
        slice2.canvas.fig.sizing_mode = 'stretch_both'

        slice1_caption = pn.pane.HTML(
            f"""
            <div style="
                display: flex; 
                justify-content: center; 
                align-items: center; 
                text-align: center; 
                height: 100%; 
                font-size: 24px;">
                <h4>Original Image &nbsp;({int(box1[0][1])} x {int(box1[1][1])})</h4>
            </div>
            """,
            sizing_mode="stretch_width",  # Ensures full width for centering
        )

        slice2_caption = pn.pane.HTML(
            f"""
            <div style="
                display: flex; 
                justify-content: center; 
                align-items: center; 
                text-align: center; 
                height: 100%; 
                font-size: 24px;">
                <h4>Super-Resolution Image &nbsp;({int(box2[0][1])} x {int(box2[1][1])})&nbsp;&nbsp;&nbsp; Scale Factor: {scale_factor:.2f}</h4>
            </div>
            """,
            sizing_mode="stretch_width",  # Ensures full width for centering
        )

        # Synchronizer for slices
        synchronizer = SliceSynchronizer(slice1, slice2, scale_factor)


        # Add the buttons to the layout
        layout = pn.Row(
            pn.Column(
                slice1_caption,
                slice1.getMainLayout(),
                sizing_mode="stretch_both",
            ),
            pn.Column(
                slice2_caption,
                slice2.getMainLayout(),
                sizing_mode="stretch_both",
            ),
            sizing_mode="stretch_both",
        )
        layout.servable()
    else:
        # Single slice view
        slice = Slice()
        slice.load(sys.argv[1])

        layout = slice.getMainLayout()
        layout.sizing_mode = 'stretch_both'
        layout.servable()