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
from sync_link import MultiSliceSynchronizer
import math
from pathlib import Path
from slice_dl import Slice as SliceDL
import requests

from bokeh.plotting import figure
from bokeh.models import BoxAnnotation
import numpy as np
from bokeh.models import LinearColorMapper

##################################


class MultiSliceSyncApp:
    def __init__(self, slices, captions, scale_factors, scale_bar1, scale_bar2):
        self.slices = slices
        self.captions = captions
        self.scale_bar1 = scale_bar1
        self.scale_bar2 = scale_bar2
        self.is_bbox_mode = False  # set by caller for single-image + BB mode
        
        self.mm_x_1 = 0.0006559980709556726  # mm/pixel
        self.fixed_pixel_length = 200

        self.synchronizer = MultiSliceSynchronizer(slices, scale_factors)
        self.synchronizer.register_callback(self.on_zoom_update)


    def update_caption(self, caption, label, zoom_level):
        #caption.object = f"<h4>{label} - Zoom Level: {round(zoom_level, 2)}%</h4>"
        #text-align: start;
        #text-align: center;
        caption.object = f"""
        <div style="width: 100%; padding-top: 2px;">
            <h4 style="margin: 0;font-size: 24px">{label}</h4>
        </div>
        """


    def update_scale_bar(self, bar, mm_per_pixel, zoom_level):
        effective_mm_per_screen_pixel = mm_per_pixel / (zoom_level / 100)
        length_mm = self.fixed_pixel_length * effective_mm_per_screen_pixel
        bar.object = f"""
        <div style="width: 100%; padding-top: 2px;">
            <svg height="20" width="{self.fixed_pixel_length}px">
              <line x1="0" y1="10" x2="{self.fixed_pixel_length}" y2="10" style="stroke:black;stroke-width:3" />
            </svg>
            <div style="font-size:20px; padding-top:2px;">{length_mm:.5f} mm</div>
        </div>
        """

    def update_scale_bar_bb(self, bar, mm_per_pixel, zoom_level):
        effective_mm_per_screen_pixel = mm_per_pixel / (zoom_level / 100)
        length_mm = self.fixed_pixel_length * effective_mm_per_screen_pixel
        bar.object = f"""
        <div style="width: 100%; padding-top: 2px;">
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
            

        try:
            # only print in single-image + bbox mode
            if self.is_bbox_mode and len(zooms) == 1:
                bb_list = getattr(self.synchronizer, "last_bb_zooms", None)
                if bb_list and bb_list[0] is not None:
                    zoom_level_bb = round(bb_list[0], 2)
                    print(f"Zoom Level BB: {zoom_level_bb}%")
                    self.update_scale_bar_bb(self.scale_bar2, self.mm_x_1, zoom_level_bb)
        except Exception as e:
            print("BB zoom print failed:", e)


    def run(self):
        print("MultiSliceSyncApp running with full synchronization & scale factors...")

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

        scale_bar2 = pn.pane.HTML(sizing_mode="stretch_width")

        # Initialize synchronization ONLY with real slices (no placeholders)
        self.multi_slice_sync_app = MultiSliceSyncApp(slices, captions, scale_factors, scale_bar1= scale_bar1, scale_bar2= scale_bar2)
        self.multi_slice_sync_app.is_bbox_mode = True  # <— tell app we're in BB mode
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
                         scale_bar1, captions[0], scale_bar2, align= "start", sizing_mode="stretch_width"),
                        pn.Spacer(),
                        #align="start",
                    sizing_mode="stretch_width",
                )
                
                            
            else:
                main_view = slices[0].getMainLayout().clone(width_policy='max', sizing_mode='stretch_both')

                # Button to toggle overlay
                overview_btn = pn.widgets.Button(
                    name="Show overview",
                    button_type="default",
                    width=140
                )
                overview_btn.styles = dict(background="#f3f4f6", color="#111827", border="1px solid #e5e7eb")

                # Holder to position overlay on top of main view
                main_holder = pn.Column(
                    main_view,
                    sizing_mode="stretch_both",
                    styles={"position": "relative"}
                )

                # Absolutely-positioned overlay container (hidden by default)
                overlay_area = pn.Column(
                    visible=False,
                    styles={
                        "position": "absolute",
                        "left": "16px",
                        "top": "16px",
                        "zIndex": "50",
                        "background": "white",
                        "padding": "6px",
                        "border": "1px solid #e5e7eb",
                        "borderRadius": "12px",
                        "boxShadow": "0 8px 24px rgba(0,0,0,.18)"
                    }
                )
                main_holder.append(overlay_area)

                # Keep references so we only build once (snapshot stays fixed)
                _overlay_fig = {"fig": None, "box": None}

                def _copy_src_data(src):
                    data = {}
                    for k, v in src.data.items():
                        if isinstance(v, np.ndarray):
                            data[k] = v.copy()
                        elif hasattr(v, "copy"):
                            data[k] = v.copy()
                        else:
                            data[k] = list(v) if isinstance(v, (list, tuple)) else v
                    return data

                def _update_box_from_main_ranges():
                    if not _overlay_fig["fig"] or not _overlay_fig["box"]:
                        return
                    fig_main = slices[0].canvas.fig
                    x0, x1 = fig_main.x_range.start, fig_main.x_range.end
                    y0, y1 = fig_main.y_range.start, fig_main.y_range.end

                    # normalize ordering just in case
                    left, right = (x0, x1) if x0 <= x1 else (x1, x0)
                    bottom, top = (y0, y1) if y0 <= y1 else (y1, y0)

                    box = _overlay_fig["box"]
                    box.left   = left
                    box.right  = right
                    box.bottom = bottom
                    box.top    = top

                def toggle_overview(event):
                    # Hide if visible
                    if overlay_area.visible:
                        overlay_area.visible = False
                        overview_btn.name = "Show overview"
                        return

                    slc = slices[0]
                    lr = getattr(slc.canvas, "last_renderer", {})
                    src = lr.get("source", None)
                    dtype = lr.get("dtype", None)

                    if src is None:
                        slc.refresh("force-render-for-overview")
                        return

                    # Build once (snapshot stays fixed even if main view changes)
                    if _overlay_fig["fig"] is None:
                        snap_src = bokeh.models.ColumnDataSource(_copy_src_data(src))

                        # Compute snapshot extents for ranges
                        X = np.array(snap_src.data["X"]).ravel()[0]
                        Y = np.array(snap_src.data["Y"]).ravel()[0]
                        DW = np.array(snap_src.data["dw"]).ravel()[0]
                        DH = np.array(snap_src.data["dh"]).ravel()[0]
                        x0_snap, x1_snap = X, X + DW
                        y0_snap, y1_snap = Y, Y + DH

                        fig_over = bokeh.plotting.figure(
                            height=240, width=340, toolbar_location=None,
                            x_range=(min(x0_snap, x1_snap), max(x0_snap, x1_snap)),
                            y_range=(min(y0_snap, y1_snap), max(y0_snap, y1_snap)),
                            match_aspect=True
                        )
                        fig_over.axis.visible = False
                        fig_over.grid.visible = False

                        if dtype == np.uint32:
                            fig_over.image_rgba("image", source=snap_src, x="X", y="Y", dw="dw", dh="dh")
                        else:
                            fig_over.image(
                                "image", source=snap_src, x="X", y="Y", dw="dw", dh="dh",
                                color_mapper=slc.color_bar.color_mapper
                            )

                        # Green viewport box (no fill, just stroke)
                        box_anno = BoxAnnotation(
                            left=x0_snap, right=x1_snap, bottom=y0_snap, top=y1_snap,
                            line_color="black", line_width=3, fill_alpha=0.2
                        )
                        fig_over.add_layout(box_anno)

                        _overlay_fig["fig"] = fig_over
                        _overlay_fig["box"] = box_anno

                        overlay_area.objects = [pn.pane.Bokeh(fig_over, width=240, height=240)]

                        # Hook updates to main view ranges
                        fig_main = slc.canvas.fig

                        # Initial sync once (Python) so the box is correct before any JS fires
                        xr, yr = fig_main.x_range, fig_main.y_range
                        box_anno.left   = min(xr.start, xr.end)
                        box_anno.right  = max(xr.start, xr.end)
                        box_anno.bottom = min(yr.start, yr.end)
                        box_anno.top    = max(yr.start, yr.end)

                        # High-perf client-side updates
                        if not _overlay_fig.get("js_hooked"):
                            cb = CustomJS(args=dict(box=box_anno, xr=xr, yr=yr), code="""
                                // Throttle to ~60fps
                                if (box._ticking) return;
                                box._ticking = true;
                                requestAnimationFrame(() => {
                                const left   = Math.min(xr.start, xr.end);
                                const right  = Math.max(xr.start, xr.end);
                                const bottom = Math.min(yr.start, yr.end);
                                const top    = Math.max(yr.start, yr.end);
                                // Batch update in ONE change
                                box.setv({left, right, bottom, top});
                                box._ticking = false;
                                });
                            """)

                            #Also update continuously during interactive tools (pan/zoom)
                            fig_main.js_on_event(bokeh.events.RangesUpdate, cb)

                            _overlay_fig["js_hooked"] = True
                       
                        # Initial sync
                        _update_box_from_main_ranges()

                    overlay_area.visible = True
                    overview_btn.name = "Hide overview"

                overview_btn.on_click(toggle_overview)

                slices_layout = pn.Column(
                    pn.Row(
                        pn.Spacer(),
                        overview_btn,
                        sizing_mode="stretch_width"
                    ),
                    pn.Row(
                        pn.Spacer(width=50),
                        main_holder,
                        pn.Spacer(width=50),
                        sizing_mode="stretch_both"
                    ),
                    pn.Row(
                    scale_bar1, captions[0], sizing_mode="stretch_width"),
                    #align="center",
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
                pn.Row(*layout_bottom_captions, scale_bar1, sizing_mode="stretch_width"),
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
