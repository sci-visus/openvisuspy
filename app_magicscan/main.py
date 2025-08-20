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
<<<<<<< Updated upstream

=======
from sync_link import MultiSliceSynchronizer
import math
from pathlib import Path
from .slice_dl import Slice as SliceDL
>>>>>>> Stashed changes

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

    log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", str(Path.home() / "openvisuspy-dashboards.log"))
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
<<<<<<< Updated upstream
        main_layout.servable()
=======
        main_layout.servable()



########################################


pn.extension()

custom_css = """
.bk-checkbox-group label {
    font-size: 12px !important;
    font-weight: bold !important;
}

.bk-btn-group .bk-btn {
    font-size: 18px !important;
    text-align: left !important;
}

h1, h2, h3, h4, h5 {
    font-size: 18px !important;
    font-weight: bold !important;
}
"""
pn.extension(raw_css=[custom_css])





class SliceSelectorApp:
    def __init__(self, idx_files):
        self.idx_files = idx_files
        
        # Display friendly names like Image1, Image2, etc.
        self.display_names = [f"Image{i+1}" for i in range(len(idx_files))]

        self.file_map = dict(zip(self.display_names, self.idx_files))

        self.checkboxes = pn.widgets.CheckButtonGroup(
            name='Select Here (just click any number of images)',
            options=self.display_names,
            value=[],
            button_type='default',
            orientation='vertical',  # ← makes the buttons stack vertically
            sizing_mode='stretch_width'
        )


        self.load_button = pn.widgets.Button(name='Load Selected Slices', button_type='primary')
        self.load_button.on_click(self.load_slices)

        # Add this inside the __init__ method of your SliceSelectorApp class
        self.images_description_button = pn.widgets.Button(
            name='Images Descriptions', button_type='success'
        )
        self.images_description_button.js_on_click(code="""
            window.open('https://docs.google.com/spreadsheets/d/1siqOce5rvImSj-EIxtUM2K_iVluouEw833bOl50VKLM/edit?usp=sharing', '_blank')
        """)

        self.selection_page = pn.Column(
            pn.Spacer(height=100),
            pn.Row(
                pn.layout.HSpacer(),
                pn.Column(
                    "# 🔹 <span style='font-size:28px;'>Select Here <span style='font-size:20px;'>( click any number of images)</span></span>",
                    self.checkboxes,
                    pn.Spacer(height=20),
                    pn.Row(
                        self.load_button,
                        self.images_description_button,
                        align='center'
                    ),
                    align='center',
                    width=800,
                    sizing_mode='stretch_height',
                ),
                pn.layout.HSpacer(),
                sizing_mode='stretch_both',
            ),
            pn.Spacer(height=20),
            sizing_mode='stretch_both',
        )

        self.main_panel = pn.Column(self.selection_page, sizing_mode='stretch_height')

    def compute_scale_factors(self, slices):
        ref_box = slices[0].db.getPhysicBox()
        ref_size = ref_box[0][1] - ref_box[0][0]

        scale_factors = []
        for slc in slices:
            box = slc.db.getPhysicBox()
            size = box[0][1] - box[0][0]
            scale_factors.append(size / ref_size)
        return scale_factors
    

    def load_slices(self, event):
        selected_display_names = self.checkboxes.value
        if not selected_display_names:
            self.main_panel.append(pn.pane.Markdown("**⚠️ Please select at least one slice.**"))
            return

        selected_files = [self.file_map[name] for name in selected_display_names]

        n = len(selected_files)
        print("loaded slices: ",n)
        draw_source = bokeh.models.ColumnDataSource(data={"xs": [], "ys": []})

        # Choose class: your SliceDL for single view; Slice for multi
        SliceClass = SliceDL if n == 1 else Slice

        slices = [SliceClass(ViewChoice="SYNC_VIEW", drawsource=draw_source) for _ in selected_files]

        for slc, path in zip(slices, selected_files):
            slc.load(path)

        scale_factors = self.compute_scale_factors(slices)

        for display_name, slc in zip(selected_display_names, slices):
            slc.image_type.value = display_name
            slc.setShowOptions({})
            slc.canvas.fig.sizing_mode = 'stretch_both'

        captions = [
            pn.pane.HTML(f"<h4>{name} - Zoom Level:</h4>", sizing_mode="stretch_width")
            for name in selected_display_names
        ]

        # Initialize synchronization ONLY with real slices (no placeholders)
        self.multi_slice_sync_app = MultiSliceSyncApp(slices, captions, scale_factors)
        self.multi_slice_sync_app.run()

        self.main_panel.clear()

        back_button = pn.widgets.Button(name="⬅️ Back", button_type="warning", width=100)
        back_button.on_click(self.back_to_selection)

        n = len(slices)
        print("loaded slices2: ",n)
        if n == 1:
            slc = slices[0]
            slc.setShowOptions({
                "top": [["resolution","view_dependent","box_edit_button","x0_input","y0_input","set_bbox_btn"]],
            })
            # Derive case/type from the path so your callbacks have context
            p = Path(selected_files[0])
            print("Case: ",p)
            case = "1177_Panel1"
            sub  = "input" if "/input/" in selected_files[0] else "sr"
            # Only set if your SliceDL uses these
            setattr(slc, "current_case", case)
            setattr(slc, "current_type", sub)

            # Left: main viewer; Right: your info/options/image panels
            left_layout  = slc.getMainLayout().clone(width_policy='max', sizing_mode='stretch_both')
            right_layout = pn.Column(
                getattr(slc, "right_options", pn.Spacer()),
                getattr(slc, "right_image", pn.Spacer()),
                sizing_mode="stretch_both",
            )

            slices_layout = pn.Column(
                pn.Row(
                    pn.Spacer(width=24),
                    left_layout,
                    pn.Spacer(width=16),
                    right_layout,
                    pn.Spacer(width=24),
                    sizing_mode="stretch_both"
                ),
                pn.Row(
                    pn.layout.HSpacer(),
                    captions[0],
                    pn.layout.HSpacer(),
                    sizing_mode="stretch_both"
                ),
                sizing_mode="stretch_both"
            )
        
        elif n == 2:
            slices_layout = pn.Column(
                pn.Row(
                    slices[0].getMainLayout(),
                    slices[1].getMainLayout(),
                    sizing_mode="stretch_both",
                ),
                pn.Row(
                    captions[0],
                    captions[1],
                    sizing_mode="stretch_width",
                ),
                sizing_mode="stretch_both",
            )
        else:
            display_slices = slices.copy()
            display_captions = captions.copy()

            if n % 2 != 0 and n > 1:
                # Only for display: Add placeholders for visual balance
                placeholder = pn.Spacer(sizing_mode="stretch_both")
                placeholder_caption = pn.Spacer(sizing_mode="stretch_width")
                display_slices.append(placeholder)
                display_captions.append(placeholder_caption)
                n_display = n + 1
            else:
                n_display = n

            half_n = n_display // 2

            layout_top_slices = [
                display_slices[i].getMainLayout() if isinstance(display_slices[i], Slice) else display_slices[i]
                for i in range(half_n)
            ]
            layout_top_captions = [display_captions[i] for i in range(half_n)]

            layout_bottom_slices = [
                display_slices[i].getMainLayout() if isinstance(display_slices[i], Slice) else display_slices[i]
                for i in range(half_n, n_display)
            ]
            layout_bottom_captions = [display_captions[i] for i in range(half_n, n_display)]

            slices_layout = pn.Column(
                pn.Row(*layout_top_slices, sizing_mode="stretch_both"),
                pn.Row(*layout_top_captions, sizing_mode="stretch_width"),
                pn.Row(*layout_bottom_slices, sizing_mode="stretch_both"),
                pn.Row(*layout_bottom_captions, sizing_mode="stretch_width"),
                sizing_mode="stretch_both",
            )

        self.main_panel.append(
            pn.Column(
                back_button,
                slices_layout,
                sizing_mode='stretch_both'
            )
        )


    def back_to_selection(self, event):
        self.main_panel.clear()
        self.main_panel.append(self.selection_page)


app = SliceSelectorApp(sys.argv[1:])
app.main_panel.servable()
>>>>>>> Stashed changes
