import os
import sys
import logging
import panel as pn
import base64
import json

from panel import pane
from panel.widgets import SpeechToText
from panel.widgets import Button, TextAreaInput
import threading

import bokeh
import bokeh.models
from bokeh.models import Button, CustomJS
import bokeh.events
import bokeh.plotting
import bokeh.models.callbacks

from openvisuspy import SetupLogger, Slice
from sync_link import SliceSynchronizer
from sync_link import MultiSliceSynchronizer
import math
from pathlib import Path
from slice_dl import Slice as SliceDL
import requests



##################################


class MultiSliceSyncApp:
    def __init__(self, slices, captions, scale_factors, scale_bar1):
        self.slices = slices
        self.captions = captions
        self.scale_bar1 = scale_bar1
        self.mm_x_1 = 0.0006559980709556726  # mm/pixel
        self.fixed_pixel_length = 200

        self.synchronizer = MultiSliceSynchronizer(slices, scale_factors)
        self.synchronizer.register_callback(self.on_zoom_update)

    def update_caption(self, caption, label, zoom_level):
        #caption.object = f"<h4>{label} - Zoom Level: {round(zoom_level, 2)}%</h4>"
        caption.object = f"""
        <div style="text-align: start; width: 100%; padding-top: 10px;">
            <h4 style="margin: 0;font-size: 20px">{label}</h4>
        </div>
        """


    def update_scale_bar(self, bar, mm_per_pixel, zoom_level):
        effective_mm_per_screen_pixel = mm_per_pixel / (zoom_level / 100)
        length_mm = self.fixed_pixel_length * effective_mm_per_screen_pixel
        bar.object = f"""
        <div style="text-align: center; width: 100%; padding-top: 10px;">
            <svg height="20" width="{self.fixed_pixel_length}px">
              <line x1="0" y1="10" x2="{self.fixed_pixel_length}" y2="10" style="stroke:black;stroke-width:3" />
            </svg>
            <div style="font-size:20px; padding-top:2px;">{length_mm:.5f} mm</div>
        </div>
        """

    def on_zoom_update(self, *zooms):
        for idx, zoom in enumerate(zooms):
            label = self.slices[idx].image_type.value
            self.update_caption(self.captions[idx], label, zoom)
            self.update_scale_bar(self.scale_bar1, self.mm_x_1, zoom)

    def run(self):
        print("MultiSliceSyncApp running with full synchronization & scale factors...")



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
        <div style="text-align: down; height: auto;">
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

#################


#######################################



class SliceSelectorApp:
    def __init__(self, idx_files):
        self.idx_files = idx_files
        
        # Display friendly names like Image1, Image2, etc.
        #self.display_names = [f"Image{i+1}" for i in range(len(idx_files))]
        self.display_names = [Path(f).parent.name for f in idx_files]
        self.bbx=["Select Boundary Box (Only for single image)"]



        self.file_map = dict(zip(self.display_names, self.idx_files))

        self.checkboxes = pn.widgets.CheckButtonGroup(
            name='Select Here (just click any number of images)',
            options=self.display_names,
            value=[],
            button_type='default',
            orientation='vertical',  # ← makes the buttons stack vertically
            sizing_mode='stretch_width'
        )

        self.checkbox2 = pn.widgets.CheckButtonGroup(
            name='Select Boundary Box',
            options=self.bbx,
            value=[],
            button_type='default',
            orientation='vertical',  # ← makes the buttons stack vertically
            sizing_mode='stretch_width'
        )


        self.load_button = pn.widgets.Button(name='Load Selected Slices', button_type='primary')
        self.load_button.on_click(self.load_slices)

        self.selection_page = pn.Column(
            pn.Spacer(height=100),
            pn.Row(
                pn.layout.HSpacer(),
                pn.Column(
                    "# 🔹 <span style='font-size:28px;'>Select Here <span style='font-size:20px;'>( click any number of images)</span></span>",
                    self.checkboxes,
                    pn.Spacer(height=20),
                    self.checkbox2,
                    pn.Spacer(height=20),
                    pn.Row(
                        self.load_button,
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

        if self.checkbox2.value:
            SliceClass = SliceDL 
        else:
            SliceClass = Slice

        slices = [SliceClass(ViewChoice="SYNC_VIEW", drawsource=draw_source) for _ in selected_files]

        for slc, path in zip(slices, selected_files):
            slc.load(path)

        scale_factors = self.compute_scale_factors(slices)

        for display_name, slc in zip(selected_display_names, slices):
            slc.image_type.value = display_name
            slc.setShowOptions({})
            slc.canvas.fig.sizing_mode = 'stretch_both'

        captions = [
            #pn.pane.HTML(f"<h4>{name} - Zoom Level:</h4>", sizing_mode="stretch_width")
            pn.pane.HTML(f"<h4>{name}", sizing_mode="stretch_width")
            for name in selected_display_names
        ]

        scale_bar1 = pn.pane.HTML(sizing_mode="stretch_width")

        # Initialize synchronization ONLY with real slices (no placeholders)
        self.multi_slice_sync_app = MultiSliceSyncApp(slices, captions, scale_factors, scale_bar1= scale_bar1)
        self.multi_slice_sync_app.run()

        self.main_panel.clear()

        back_button = pn.widgets.Button(name="⬅️ Back", button_type="warning", width=100)
        back_button.on_click(self.back_to_selection)

        n = len(slices)
        print("loaded slices2: ",n)
        if n == 1:
            if self.checkbox2.value:
                slc = slices[0]
                slc.setShowOptions({
                    "top": [["resolution","view_dependent","box_edit_button","x0_input","y0_input","set_bbox_btn"]],
                })
                # Derive case/type from the path so your callbacks have context
                p = Path(selected_files[0])
                print("Case: ",p)
                case = "1177_Panel1"
                sub  = "input"
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
                        pn.Spacer(),
                        pn.Column(captions[0], sizing_mode="stretch_width"),
                        pn.Column(scale_bar1, width=150),
                        pn.Spacer(),),
                        align="start",
                    sizing_mode="stretch_width",
                )
            else:
                slices_layout = pn.Column(
                pn.Row(
                    pn.Spacer(width=50),
                    slices[0].getMainLayout().clone(width_policy='max', sizing_mode='stretch_both'),
                    pn.Spacer(width=50),
                    sizing_mode="stretch_both"
                ),
                pn.Row(
                    pn.Spacer(),
                    pn.Column(scale_bar1, width=150),
                    pn.Column(captions[0], sizing_mode="stretch_width"),
                    pn.Spacer(),),
                    align="center",
                sizing_mode="stretch_width",
            )
        
        elif n == 2:
            slices_layout = pn.Column(
                pn.Row(
                    slices[0].getMainLayout(),
                    pn.layout.VSpacer(),
                    slices[1].getMainLayout(),
                    pn.layout.VSpacer(),
                    sizing_mode="stretch_both",
                ),
                pn.Row(
                    scale_bar1,
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
                scale_bar1,
                sizing_mode='stretch_both'
            )
        )


    def back_to_selection(self, event):
        self.main_panel.clear()
        self.main_panel.append(self.selection_page)


########

if __name__.startswith('bokeh'):
    pn.extension(
        "ipywidgets",
        "floatpanel",
        "codeeditor",
        log_level="DEBUG",
        notifications=True,
    )

    query_params = {k: v for k, v in pn.state.location.query_params.items()}

    log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "/home/openvisuspy-dashboards.log")
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

    #response=requests.get("http://localhost/list_magicscan.php")
    #jsonbdy = response.json()
    #paths = [f"/mnt/visus_datasets/converted/{item['uuid']}/visus.idx" for item in jsonbdy]
    #print(paths)

    #app = SliceSelectorApp(paths)
    app = SliceSelectorApp(sys.argv[1:])
    app.main_panel.servable()
