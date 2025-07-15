import os
import sys
import logging
import panel as pn
import base64
import json
import copy
from panel import pane
from panel.widgets import SpeechToText
from panel.widgets import Button, TextAreaInput

import bokeh
import bokeh.models
from bokeh.models import Button, CustomJS
import bokeh.events
import bokeh.plotting
import bokeh.models.callbacks


from openvisuspy import SetupLogger, Slice
from sync_link import SliceSynchronizer


#####################################################################

###############################
class ZoomSync2:
    def __init__(self, slice1, slice2, scale_factor, slice1_caption, slice2_caption):
        self.synchronizer = SliceSynchronizer(slice1, slice2, scale_factor)
        self.synchronizer.register_callback(self.on_zoom_update)
        
        # Store reference to captions for updates
        self.slice1_caption = slice1_caption
        self.slice2_caption = slice2_caption

    def update_caption(self, caption, label, zoom_level):
        """
        Helper method to update captions dynamically.
        """
        caption.object = f"""
        <div style="text-align: top; height: auto;">
            <h4> {label} &nbsp;&nbsp;&nbsp; Zoom Level: {round(zoom_level, 2)} %</h4>
        </div>
        """

    def on_zoom_update(self, zoom_level_fig1, zoom_level_fig2):
        """
        Callback function to update zoom levels in captions.
        """
        print(f"Updated Zoom Levels - Fig1: {zoom_level_fig1}, Fig2: {zoom_level_fig2}")
        self.update_caption(self.slice1_caption, slice1.image_type.value, zoom_level_fig1)
        self.update_caption(self.slice2_caption, slice2.image_type.value, zoom_level_fig2)

    def run(self):
        """
        Run the application.
        """
        print("Application is running...")

#########

if __name__.startswith('bokeh'):
    pn.extension(
        "ipywidgets",
        "floatpanel",
        "codeeditor",
        log_level="DEBUG",
        notifications=True,
    )

    query_params = {k: v for k, v in pn.state.location.query_params.items()}

    log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "/home/sampad/openvisuspy-dashboards.log")
    logger = SetupLogger(log_filename=log_filename, logging_level=logging.DEBUG)


    # Show options for both slices
    # "resolution" max , "view_dependent" is yes; set Default

    '''
    	show_options={
		"top": [
			[ "menu_button","scene", "timestep", "timestep_delta", "play_sec","play_button","palette", "color_mapper_type","view_dependent", "resolution", "num_refinements", "show_probe"],
			["field","direction", "offset", "range_mode", "range_min",  "range_max"]

		],
		"bottom": [
			["request","response", "zoom_level", "image_type"]
		]
	}

    '''
    
    show_options = {}

    # Add scrolling styles
    custom_css = """
    body {
        overflow-y: scroll; /* Enable vertical scrolling */
        height: 100%;
        margin: 0;
        padding: 0;
    }
    """
    pn.extension(raw_css=[custom_css])


    if len(sys.argv[1:]) == 2:
        # Load for Sync Slices view
        draw_source = bokeh.models.ColumnDataSource(data={"xs": [], "ys": []})  # Source for freehand drawings

        slice1 = Slice(ViewChoice="SYNC_VIEW", drawsource = draw_source)
        slice1.load(sys.argv[1])

        slice2 = Slice(ViewChoice="SYNC_VIEW", drawsource = draw_source)
        slice2.load(sys.argv[2])

        


        # Compute scale factor
        box1 = slice1.db.getPhysicBox()
        box2 = slice2.db.getPhysicBox()
        scale_factor = box2[0][1] / box1[0][1]  # Scaling based on x-axis

        slice1.image_type.value = "Super-Resolution Image from Grayscale Images"
        slice2.image_type.value = "Super-Resolution Image from Color Images"

        if scale_factor < 1:  # reverse both images
            slice1.image_type.value = "Super-Resolution Image from Grayscale Images"
            slice2.image_type.value = "Super-Resolution Image from Color Images"


        slice1.setShowOptions(show_options)
        slice2.setShowOptions(show_options)

        # Stretch both figures
        slice1.canvas.fig.sizing_mode = 'stretch_both'
        slice2.canvas.fig.sizing_mode = 'stretch_both'
       

        slice1_caption = pn.pane.HTML(
            f"""
            <div style="
                display: flex; 
                justify-content: top; 
                align-items: top; 
                text-align: top; 
                height: 5;">
                <h4>Original Image </h4>
            </div>
            """,
            sizing_mode="stretch_width",  # Ensures full width for centering
        )

        slice2_caption = pn.pane.HTML(
            f"""
            <div style="
                display: flex; 
                justify-content: top; 
                align-items: top; 
                text-align: top; 
                height: 5;">
                <h4>Super-Resolution Image </h4>
            </div>
            """,
            sizing_mode="stretch_width",  # Ensures full width for centering
        )
        
        # Initialize the main class
        main_app = ZoomSync2(slice1, slice2, scale_factor, slice1_caption,slice2_caption)

        # Run the application
        main_app.run()

        layout = pn.Column(
            pn.Row(
                pn.Column(
                    slice1.getMainLayout(),
                    sizing_mode="stretch_both",
                ),
                pn.Column(
                    slice2.getMainLayout(),
                    sizing_mode="stretch_both",
                ),
                sizing_mode="stretch_both",
            ),
            pn.Row(
                slice1_caption, slice2_caption,
                sizing_mode="stretch_both",
            )
        )
        layout.servable()
        
    else:
        # Single slice view
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

        #slice.setShowOptions(show_options)

        main_layout = slice.getMainLayout()
        main_layout.servable()