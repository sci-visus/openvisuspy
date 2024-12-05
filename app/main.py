import os
import sys
import logging
import panel as pn
import base64
import json
from urllib.parse import parse_qs, unquote


from openvisuspy import SetupLogger, Slice
from sync_link import SliceSynchronizer


#####################################################################

def get_file_path():
    # Check URL parameters first
    query = parse_qs(pn.state.location.search)
    logger.info(f"URL Query Parameters: {query}")

    if '?args' in query:
        # Clean the path: remove quotes and handle spaces
        path = unquote(query['?args'][0])
        path = path.replace("'", "") 
        path = path.replace('"', "")  
        logger.info(f"Args from URL (cleaned): {path}")
        if '|' in path:
            return path.split('|')
        else:
            return [path]
    
    # If no URL parameter, check command line args
    cmd_args = sys.argv[1:]
    logger.info(f"Command Line Args: {cmd_args}")
    return cmd_args

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


    # Show options for both slices
    # "resolution" max , "view_dependent" is yes; set Default
    
    show_options = {
            "top": [["scene", "resolution","view_dependent"]], # color_mapper_type, Pallete, field, range mode max min are removed
            "bottom": [["request", "response"]],
        }
    
    args = get_file_path()
    logger.info(f"Final Args Being Used: {args}")
        
    if len(args) == 2:
        logger.info(f"Using two-file sync view mode with files: {args[0]} and {args[1]}")
        # Load for Sync Slices view
        slice1 = Slice(ViewChoice="SYNC_VIEW")
        slice1.load(args[0])

        slice2 = Slice(ViewChoice="SYNC_VIEW")
        slice2.load(args[1])


        # Compute scale factor
        box1 = slice1.db.getPhysicBox()
        box2 = slice2.db.getPhysicBox()
        scale_factor = box2[0][1] / box1[0][1]  # Scaling based on x-axis

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
        logger.info(f"Using single-file mode with file: {args[0]}")
        slice = Slice()
        slice.load(args[0])

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