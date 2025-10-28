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
from panel.layout import FloatPanel

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
        #self.display_names = [Path(f).parent.name for f in idx_files]

        names = [f"case: {item['name']}" for item in jsonbdy]
        print("names",names)

        self.display_names = [names[f] for f in range(len(idx_files))]
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
                slc = slices[0]
                main_view = slices[0].getMainLayout().clone(width_policy='max', sizing_mode='stretch_both')

                # Button to toggle overlay
                overview_btn = pn.widgets.Button(
                    name="Show overview",
                    button_type="default",
                    width=140
                )
                overview_btn.styles = dict(background="#f3f4f6", color="#111827", border="1px solid #e5e7eb")

                # Right-side overlay page (fixed width) with Mark/+/-/Reset/Save buttons and a log dashboard
                btnA = pn.widgets.Button(name="Mark", width=80)
                btnB = pn.widgets.Button(name="➕", width=60)
                btnC = pn.widgets.Button(name="➖", width=60)
                btnReset = pn.widgets.Button(name="Reset", width=80, button_type="warning")
                btnSave = pn.widgets.Button(name="Save", width=80, button_type="success")

                side_log = pn.widgets.TextAreaInput(
                    name="Log",
                    value="",
                    height=240,
                    disabled=False,
                    sizing_mode="stretch_width"
                )
                
                sam_format_display = pn.widgets.TextAreaInput(
                    name="SAM Format (point_coords)",
                    value="",
                    height=200,
                    disabled=False,
                    sizing_mode="stretch_width"
                )

                # Send Slice log outputs to the overlay dashboard
                try:
                    slc.set_log_sink(side_log)
                except Exception:
                    setattr(slc, "log_sink", side_log)
                
                # Function to update SAM format display
                def update_sam_format():
                    try:
                        d = slc.points_source.data
                        xs = list(d.get('x', []))
                        ys = list(d.get('y', []))
                        cs = list(d.get('color', []))
                        if xs and ys:
                            # Get image dimensions from the slice's logic box
                            try:
                                logic_box = slc.getQueryLogicBox()
                                p1, p2 = logic_box
                                W = abs(p2[0] - p1[0])  # image width
                                H = abs(p2[1] - p1[1])  # image height
                            except Exception:
                                # Fallback: use canvas viewport dimensions
                                viewport = slc.canvas.getViewport()
                                W = abs(viewport[2])
                                H = abs(viewport[3])
                            
                            # Convert pixel coords to normalized [0, 1] range
                            point_coords = []
                            for x, y in zip(xs, ys):
                                x_px = int(round(x))
                                y_px = int(round(y))
                                x_norm = round(x_px / W, 4) if W > 0 else 0
                                y_norm = round(y_px / H, 4) if H > 0 else 0
                                point_coords.append([x_norm, y_norm])
                            
                            # Green (lightgreen) = 1, Blue = 0
                            point_labels = [1 if c == "lightgreen" else 0 for c in cs]
                            
                            # Extract current ROI image as base64
                            b64img = None
                            try:
                                import base64
                                from io import BytesIO
                                from PIL import Image
                                
                                # Get the current rendered image from canvas
                                lr = getattr(slc.canvas, "last_renderer", {})
                                src = lr.get("source", None)
                                if src and "image" in src.data:
                                    img_data = src.data["image"][0]
                                    
                                    # Convert to PIL Image
                                    if img_data.dtype == np.uint32:
                                        # RGBA image
                                        img = Image.fromarray(img_data, mode='RGBA')
                                    else:
                                        # RGB or grayscale
                                        if len(img_data.shape) == 3 and img_data.shape[2] == 3:
                                            img = Image.fromarray(img_data.astype(np.uint8), mode='RGB')
                                        else:
                                            img = Image.fromarray(img_data.astype(np.uint8))
                                    
                                    # Flip vertically to correct orientation
                                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
                                    
                                    # Convert to base64
                                    buffered = BytesIO()
                                    img.save(buffered, format="PNG")
                                    b64img = base64.b64encode(buffered.getvalue()).decode('utf-8')
                            except Exception as e:
                                print(f"Error extracting ROI image: {e}")
                            
                            import json
                            sam_data = {
                                "point_coords": point_coords,
                                "point_labels": point_labels
                            }
                            if b64img:
                                sam_data["b64img"] = b64img
                            
                            sam_json = json.dumps(sam_data, indent=2)
                            sam_format_display.value = sam_json
                        else:
                            sam_format_display.value = ""
                    except Exception as e:
                        print(f"Error updating SAM format: {e}")
                
                # Set the callback on the slice
                slc.sam_format_callback = update_sam_format

                def _log_click(label):
                    def _cb(ev):
                        sep = "" if side_log.value == "" else "\n"
                        side_log.value = f"{side_log.value}{sep}{label}"
                    return _cb

                btnB.on_click(_log_click("positive"))
                btnC.on_click(_log_click("negative"))

                # Button A toggles the point tool on the main figure
                def _toggle_point_tool(_=None):
                    active = not getattr(slc, "point_tool_active", False)
                    try:
                        slc.set_point_tool(active)
                    except Exception:
                        setattr(slc, "point_tool_active", active)
                    btnA.button_type = "success" if active else "default"
                    # Disable B/C if tool is off
                    btnB.disabled = not active
                    btnC.disabled = not active
                    # Reset dot color if tool is off
                    if not active:
                        try:
                            slc.set_dot_color(None)
                        except Exception:
                            slc.active_dot_color = None
                    # Write status to the log dashboard
                    status = "ON" if active else "OFF"
                    sep = "" if side_log.value == "" else "\n"
                    side_log.value = f"{side_log.value}{sep}Point tool: {status}"


                def _set_green(_=None):
                    if not getattr(slc, "point_tool_active", False):
                        return
                    try:
                        slc.set_dot_color("lightgreen")
                    except Exception:
                        slc.active_dot_color = "lightgreen"
                    btnB.button_type = "success"
                    btnC.button_type = "default"

                def _set_blue(_=None):
                    if not getattr(slc, "point_tool_active", False):
                        return
                    try:
                        slc.set_dot_color("blue")
                    except Exception:
                        slc.active_dot_color = "blue"
                    btnC.button_type = "primary"
                    btnB.button_type = "default"

                btnA.on_click(_toggle_point_tool)
                btnB.on_click(_set_green)
                btnC.on_click(_set_blue)

                def _reset_all(_=None):
                    # Clear all points
                    try:
                        slc.clear_points()
                    except Exception:
                        slc.points_source.data = dict(x=[], y=[], color=[])
                    # Clear log dashboard
                    side_log.value = ""
                    # Clear SAM format display
                    sam_format_display.value = ""
                    # Reset button states
                    btnA.button_type = "default"
                    btnB.button_type = "default"
                    btnC.button_type = "default"
                    btnB.disabled = True
                    btnC.disabled = True
                    # Turn off point tool
                    try:
                        slc.set_point_tool(False)
                    except Exception:
                        slc.point_tool_active = False
                        slc.active_dot_color = None

                btnReset.on_click(_reset_all)

                def _save_sam_format(_=None):
                    try:
                        sam_data = sam_format_display.value
                        if not sam_data:
                            print("No SAM data to save")
                            return
                        
                        import json
                        import os
                        from datetime import datetime
                        
                        # Create a filename with timestamp
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"sam_coords_{timestamp}.json"
                        
                        # Try multiple writable locations (prioritize mounted volumes for persistence)
                        possible_dirs = [
                            "/mnt/visus_datasets/sam_output",  # Likely mounted volume - persists outside container
                            "/mnt/visus_datasets/converted/sam_output",  # Alternative mounted location
                            "/tmp/sam_output",  # Container temp - lost on restart
                            os.path.expanduser("~/sam_output")  # Container home - lost on restart
                        ]
                        
                        filepath = None
                        for save_dir in possible_dirs:
                            try:
                                if not os.path.exists(save_dir):
                                    os.makedirs(save_dir, exist_ok=True)
                                filepath = os.path.join(save_dir, filename)
                                # Test write permission
                                test_file = os.path.join(save_dir, ".write_test")
                                with open(test_file, 'w') as f:
                                    f.write("test")
                                os.remove(test_file)
                                break
                            except (OSError, PermissionError):
                                continue
                        
                        if filepath is None:
                            raise PermissionError("No writable directory found")
                        
                        filepath = os.path.join(save_dir, filename)
                        
                        # Parse JSON to get image data
                        sam_json = json.loads(sam_data)
                        
                        # Save the ROI image if b64img exists
                        if "b64img" in sam_json:
                            import base64
                            from PIL import Image
                            from io import BytesIO
                            
                            # Decode base64 image (already flipped when encoded)
                            img_data = base64.b64decode(sam_json["b64img"])
                            img = Image.open(BytesIO(img_data))
                            
                            # Save the image (no need to flip again, already flipped in b64img creation)
                            img_filename = f"sam_roi_{timestamp}.png"
                            img_filepath = os.path.join(save_dir, img_filename)
                            img.save(img_filepath)
                            print(f"Saved ROI image to: {img_filepath}")
                        
                        # Write JSON to file
                        with open(filepath, 'w') as f:
                            f.write(sam_data)
                        
                        # Log success message
                        msg = f"Saved to: {filepath}"
                        if "b64img" in sam_json:
                            msg += f"\nROI image: {img_filepath}"
                        print(msg)
                        sep = "" if side_log.value == "" else "\n"
                        side_log.value = f"{side_log.value}{sep}{msg}"
                        
                    except Exception as e:
                        error_msg = f"Error saving SAM format: {e}"
                        print(error_msg)
                        sep = "" if side_log.value == "" else "\n"
                        side_log.value = f"{side_log.value}{sep}{error_msg}"

                btnSave.on_click(_save_sam_format)

                # Start with B/C disabled
                btnB.disabled = True
                btnC.disabled = True

                overlay_side_panel = pn.Column(
                    pn.pane.Markdown("### Overlay Page"),
                    pn.Row(btnA, btnB, btnC),
                    pn.Row(btnReset, btnSave),
                    side_log,
                    sam_format_display,
                    width=340,
                    sizing_mode="stretch_height",
                    visible=False,
                    styles={"flex": "0 0 auto"}
                )

                # Keep reference for toggling
                self._side_overlay_col = overlay_side_panel

                # Top-right overlay toggle button
                overlay_btn = pn.widgets.Button(
                    name="Overlay",
                    button_type="primary",
                    width=120
                )

                def toggle_side_overlay(event=None):
                    show = not overlay_side_panel.visible
                    overlay_side_panel.visible = show
                    overlay_btn.name = "Hide overlay" if show else "Overlay"

                overlay_btn.on_click(toggle_side_overlay)

                # Holder to position overlay on top of main view
                main_holder = pn.Column(
                    main_view,
                    sizing_mode="stretch_both",
                    styles={"position": "relative"}
                )

                # Absolutely-positioned overlay container (visible by default for overview)
                overlay_area = pn.Column(
                    visible=True,
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
                _overlay_fig = {"fig": None, "box": None, "initializing": False, "event_handlers": []}

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
                    print(f"Updated box: left={left}, right={right}, bottom={bottom}, top={top}")

                def toggle_overview(event):
                    # Prevent recursion during initialization
                    if _overlay_fig.get("initializing"):
                        return
                        
                    # Always show overview (no toggle)
                    slc = slices[0]
                    lr = getattr(slc.canvas, "last_renderer", {})
                    src = lr.get("source", None)
                    dtype = lr.get("dtype", None)

                    if src is None:
                        _overlay_fig["initializing"] = True
                        slc.refresh("force-render-for-overview")
                        # Schedule a retry after the refresh completes
                        def retry_overview():
                            import time
                            time.sleep(0.3)  # Wait for refresh to complete
                            _overlay_fig["initializing"] = False
                            try:
                                toggle_overview(None)
                            except:
                                pass
                        import threading
                        threading.Thread(target=retry_overview, daemon=True).start()
                        return

                    # Build once (snapshot stays fixed even if main view changes)
                    if _overlay_fig["fig"] is None:
                        print("Creating overview figure...")
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

                        try:
                            # Hook updates to main view ranges (only if not already hooked)
                            if not _overlay_fig.get("js_hooked"):
                                fig_main = slc.canvas.fig

                                # Initial sync once (Python) so the box is correct before any JS fires
                                xr, yr = fig_main.x_range, fig_main.y_range
                                box_anno.left   = min(xr.start, xr.end)
                                box_anno.right  = max(xr.start, xr.end)
                                box_anno.bottom = min(yr.start, yr.end)
                                box_anno.top    = max(yr.start, yr.end)
                                print(f"Initial box position set: {box_anno.left}, {box_anno.right}, {box_anno.bottom}, {box_anno.top}")

                                # High-perf client-side updates
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

                                # Attach JS event handler for smooth real-time updates
                                fig_main.js_on_event(bokeh.events.RangesUpdate, cb)
                                print("JS event handler attached")
                                
                                # Also add Python callback for reliability
                                def update_box_on_ranges(evt):
                                    try:
                                        _update_box_from_main_ranges()
                                    except Exception as e:
                                        print(f"Error in update_box_on_ranges: {e}")
                                
                                # Use the slice's canvas event system
                                slc.canvas.on_event(bokeh.events.RangesUpdate, update_box_on_ranges)
                                print("Python event handler attached")
                                
                                _overlay_fig["js_hooked"] = True
                                print("Overview figure created and tracking hooks attached!")
                               
                                # Initial sync
                                _update_box_from_main_ranges()
                            else:
                                print("Tracking already set up, skipping...")
                        except Exception as e:
                            print(f"Error setting up tracking: {e}")
                            import traceback
                            traceback.print_exc()

                    overlay_area.visible = True
                    # Keep button name as "Show overview"

                overview_btn.on_click(toggle_overview)

                slices_layout = pn.Column(
                    pn.Row(
                        pn.Spacer(),
                        overview_btn,
                        overlay_btn,
                        sizing_mode="stretch_width"
                    ),
                    pn.Row(
                        pn.Spacer(width=24),
                        main_holder,
                        pn.Spacer(width=16),
                        overlay_side_panel,
                        pn.Spacer(width=24),
                        sizing_mode="stretch_both"
                    ),
                    pn.Row(
                        scale_bar1, captions[0], sizing_mode="stretch_width"
                    ),
                    sizing_mode="stretch_width",
                )
                
                # Trigger overview after layout is created
                print("Attempting to trigger initial overview...")
                try:
                    toggle_overview(None)
                    print("Initial overview triggered successfully")
                except Exception as e:
                    print(f"Initial overview failed: {e}")
                    import traceback
                    traceback.print_exc()

        
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

    log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "/srv/tmp/openvisuspy-dashboards.log")
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

    API_HOST = os.environ.get("MAGICSCAN_API_HOST", "visstore_nginx")  # docker service name
    API_SCHEME = os.environ.get("MAGICSCAN_API_SCHEME", "http")
    API_PORT = os.environ.get("MAGICSCAN_API_PORT", "80")

    url = f"{API_SCHEME}://{API_HOST}:{API_PORT}/list_magicscan.php"

    response=requests.get(url,timeout=10)
    jsonbdy = response.json()
    paths = [f"/mnt/visus_datasets/converted/{item['uuid']}/visus.idx" for item in jsonbdy]
    print(paths)

    app = SliceSelectorApp(paths)
    #app = SliceSelectorApp(sys.argv[1:])
    app.main_panel.servable()