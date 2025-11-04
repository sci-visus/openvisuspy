import os
import sys
import logging
import panel as pn
import base64
import json

# Set up module-level logger
logger = logging.getLogger(__name__)

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

# Add the openvisuspy source path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from openvisuspy import SetupLogger, Slice
from .sync_link import MultiSliceSynchronizer
from .state_manager import StateManager, SliceStateTracker
import math
from pathlib import Path
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


    def update_caption(self, caption, label, zoom_level, mm_per_pixel=None):
        #caption.object = f"<h4>{label} - Zoom Level: {round(zoom_level, 2)}%</h4>"
        #text-align: start;
        #text-align: center;
        
        # Calculate scale bar if mm_per_pixel is provided
        scale_bar_html = ""
        if mm_per_pixel:
            effective_mm_per_screen_pixel = mm_per_pixel / (zoom_level / 100)
            
            # Calculate base measurement in mm
            length_mm = self.fixed_pixel_length * effective_mm_per_screen_pixel
            
            # Auto-select appropriate unit based on size
            if length_mm < 1.0:  # Less than 1mm, use micrometers
                length_um = length_mm * 1000
                display_value = f"{length_um:.0f} μm"
            elif length_mm < 10.0:  # 1-10mm, use millimeters
                display_value = f"{length_mm:.1f} mm"
            else:  # 10mm or more, use centimeters
                length_cm = length_mm / 10
                display_value = f"{length_cm:.1f} cm"
            
            scale_bar_html = f"""
            <div style="display: inline-block; margin-left: 7cm;">
                <svg height="20" width="{self.fixed_pixel_length}px" style="vertical-align: middle;">
                  <line x1="0" y1="10" x2="{self.fixed_pixel_length}" y2="10" style="stroke:black;stroke-width:3" />
                </svg>
                <span style="font-size:20px; margin-left:5px; vertical-align: middle;">{display_value}</span>
            </div>
            """
        
        caption.object = f"""
        <div style="width: 100%; padding-top: 2px; display: flex; align-items: center; justify-content: center; white-space: nowrap;">
            <h4 style="margin: 0; font-size: 24px; display: flex; align-items: center; white-space: nowrap;">
                <span>Zoom: {round(zoom_level, 2)}%</span>
                <span style="display: inline-block; width: 6cm;"></span>
                <span>{label}</span>
            </h4>
            {scale_bar_html}
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
            self.update_caption(self.captions[idx], label, zoom, self.mm_x_1)
            # Keep the separate scale bar update for compatibility
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
        
        # Initialize state manager
        state_log_dir = os.environ.get("OPENVISUSPY_STATE_LOG_DIR", "./state_logs")
        self.state_manager = StateManager(state_dir=state_log_dir)
        
        # Track state trackers for active slices
        self.state_trackers = []
        
        # Track current state index for undo/redo functionality
        # None means we're viewing the current state (00000.json), not a saved timestep
        self.current_state_index = {}  # Dictionary for saved_states navigation (display_name -> index or None)
        self.live_tracking_index = {}  # Dictionary for live_tracking navigation (display_name -> index or None)
        
        # Live tracking periodic callback
        self.live_tracking_callback = None
        
        # Flag to determine if loading with last state
        self.load_with_last_state = False
        
        # Initialize annotation status tracking
        self.annotation_status = {
            "verified": {},  # {title: boolean}
            "ink_area": {},  # {title: boolean}
            "notes": {},  # {title: [list of notes with timestamp and text]}
            "dashboard_notices": []  # Global notices for the entire dashboard
        }
        self.annotation_file = Path("annotation_status.json")
        self._load_annotation_status()
        
        # Display friendly names like Image1, Image2, etc.
        #self.display_names = [f"Image{i+1}" for i in range(len(idx_files))]
        self.display_names = [f"{i+1}. {Path(f).parent.name}" for i, f in enumerate(idx_files)]

        #names = [f"case: {item['name']}" for item in jsonbdy]
        #print("names",names)

        #self.display_names = [names[f] for f in range(len(idx_files))]
        self.bbx=["Select Boundary Box (Only for single image)"]



        self.file_map = dict(zip(self.display_names, self.idx_files))

        # Create checkboxes with status indicators in labels
        self._create_checkboxes_with_status()

        self.checkbox2 = pn.widgets.CheckButtonGroup(
            name='Select Boundary Box',
            options=self.bbx,
            value=[],
            button_type='default',
            orientation='vertical',  # ← makes the buttons stack vertically
            sizing_mode='stretch_width'
        )

        # Add radio button group for state loading options
        self.state_option = pn.widgets.RadioButtonGroup(
            name='',
            options=['Load New View', 'Load Last View'],
            value='Load New View',
            button_type='default',
            orientation='horizontal'
        )

        self.load_button = pn.widgets.Button(name='Load Image', button_type='primary')
        self.load_button.on_click(self.load_slices)

        # Create a placeholder for notes panel that will update based on selection
        self.notes_panel_container = pn.Column(
            pn.pane.Markdown(
                "### 📝 Notes\n\n*Select an image from the list to view and add notes.*",
                styles={
                    'background': '#f9fafb',
                    'border': '1px solid #e5e7eb',
                    'border-radius': '8px',
                    'padding': '16px',
                    'color': '#6b7280',
                    'font-style': 'italic'
                }
            ),
            sizing_mode='stretch_width'
        )
        
        # Watch for checkbox selection changes to update notes panel
        self.checkboxes.param.watch(self._on_selection_change, 'value')

        # Wrap checkboxes in a scrollable container with max height
        self.checkboxes_container = pn.Column(
            self.checkboxes,
            scroll=True,
            max_height=900,  # Limit height to enable scrolling when content exceeds
            sizing_mode='stretch_width',
            styles={'border': '1px solid #ddd', 'padding': '10px', 'border-radius': '5px'}
        )

        # Count total number of titles
        total_count = len(self.display_names)
        
        # Count verified and ink area items
        verified_count = sum(1 for name in self.display_names if self.annotation_status.get("verified", {}).get(name, False))
        ink_area_count = sum(1 for name in self.display_names if self.annotation_status.get("ink_area", {}).get(name, False))

        # Create title header that will be updated dynamically
        self.selection_title = pn.pane.Markdown(
            f"# <span style='font-size:28px;'></span> ✅ Done: {verified_count} | 🖊️ Ink area found in: {ink_area_count} | Total: {total_count}</span>",
            sizing_mode='stretch_width'
        )

        # Left column: Checkboxes selection
        left_column = pn.Column(

            pn.Row(self.selection_title,"###### Load Options",self.state_option,self.load_button),
            pn.Row(self.checkboxes_container),
            width=1050,
            sizing_mode='stretch_height',
        )

        # Right column: Load options and button
        right_column = pn.Column(
            self._create_dashboard_notices_panel(),
            pn.Spacer(height=20),
            self.notes_panel_container,
            width=450,
            align='start',
        )

        self.selection_page = pn.Column(
            pn.Spacer(height=100),
            pn.Row(
                pn.Spacer(width=20),  # Small left margin
                left_column,
                pn.Spacer(width=40),
                right_column,
                pn.layout.HSpacer(),
                sizing_mode='stretch_both',
            ),
            pn.Spacer(height=20),
            sizing_mode='stretch_both',
        )

        self.main_panel = pn.Column(self.selection_page, sizing_mode='stretch_height')

    def _create_checkboxes_with_status(self):
        """Create checkboxes with status indicators visible in the button labels"""
        # Create display options with status indicators
        display_options = []
        for name in self.display_names:
            verified = self.annotation_status.get("verified", {}).get(name, False)
            ink_area = self.annotation_status.get("ink_area", {}).get(name, False)
            
            # Add status indicators as emojis
            verified_icon = "✅" if verified else "⬜"
            ink_icon = "🖊️" if ink_area else "📝"
            
            # Format: [verified_status] [ink_status] Title
            display_label = f"{verified_icon} {ink_icon} {name}"
            display_options.append(display_label)
        
        # Create mapping from display label to actual name
        self.label_to_name = {}
        for label, name in zip(display_options, self.display_names):
            self.label_to_name[label] = name
        
        self.checkboxes = pn.widgets.RadioButtonGroup(
            name='Select Here (click one image at a time)',
            options=display_options,
            value=None,
            button_type='default',
            orientation='vertical',
            sizing_mode='stretch_width',
            stylesheets=["""
                button.bk-btn.bk-active {
                    background-color: #fef08a !important;
                    border-color: #eab308 !important;
                    color: #000000 !important;
                    font-weight: bold !important;
                }
                button.bk-btn.bk-active:hover {
                    background-color: #fde047 !important;
                    border-color: #ca8a04 !important;
                }
            """]
        )
    
    def _update_checkbox_labels(self):
        """Update checkbox labels to reflect current status"""
        # Store current selection (single value, not list)
        current_value = self.label_to_name.get(self.checkboxes.value, self.checkboxes.value) if self.checkboxes.value else None
        
        # Recreate options with updated status
        display_options = []
        for name in self.display_names:
            verified = self.annotation_status.get("verified", {}).get(name, False)
            ink_area = self.annotation_status.get("ink_area", {}).get(name, False)
            
            verified_icon = "✅" if verified else "⬜"
            ink_icon = "🖊️" if ink_area else "📝"
            
            display_label = f"{verified_icon} {ink_icon} {name}"
            display_options.append(display_label)
        
        # Update label mapping
        self.label_to_name = {}
        for label, name in zip(display_options, self.display_names):
            self.label_to_name[label] = name
        
        # Update options and preserve selection
        self.checkboxes.options = display_options
        
        # Restore selection using new label (single value)
        if current_value:
            name_to_label = {name: label for label, name in self.label_to_name.items()}
            self.checkboxes.value = name_to_label.get(current_value, None)
        else:
            self.checkboxes.value = None
        
        # Update title with new counts
        total_count = len(self.display_names)
        verified_count = sum(1 for name in self.display_names if self.annotation_status.get("verified", {}).get(name, False))
        ink_area_count = sum(1 for name in self.display_names if self.annotation_status.get("ink_area", {}).get(name, False))
        
        if hasattr(self, 'selection_title'):
            self.selection_title.object = f"# 🔹 <span style='font-size:28px;'>Select Here </span> - Total: {total_count} | ✅ Verified: {verified_count} | 🖊️ Ink: {ink_area_count}</span>"

    def _on_selection_change(self, event):
        """Update notes panel when selection changes"""
        if event.new:
            # Convert display label back to actual name
            selected_display_name = self.label_to_name.get(event.new, event.new)
            
            # Update the notes panel container with yellow background
            self.notes_panel_container.clear()
            notes_panel = self._create_notes_panel(selected_display_name, highlighted=True)
            self.notes_panel_container.append(notes_panel)
        else:
            # Show placeholder message when nothing is selected
            self.notes_panel_container.clear()
            self.notes_panel_container.append(
                pn.pane.Markdown(
                    "### 📝 Notes \n\n*Select an image from the list to view and add notes.*",
                    styles={
                        'background': '#f9fafb',
                        'border': '1px solid #e5e7eb',
                        'border-radius': '8px',
                        'padding': '16px',
                        'color': '#6b7280',
                        'font-style': 'italic'
                    }
                )
            )


    def _load_annotation_status(self):
        """Load annotation status from JSON file if it exists"""
        try:
            if self.annotation_file.exists():
                with open(self.annotation_file, 'r') as f:
                    loaded_status = json.load(f)
                
                # Migrate old "checked" key to "verified" if needed
                if "checked" in loaded_status and "verified" not in loaded_status:
                    loaded_status["verified"] = loaded_status.pop("checked")
                    logger.info(f"✓ Migrated 'checked' to 'verified' in annotation status")
                
                # Ensure all keys exist
                if "verified" not in loaded_status:
                    loaded_status["verified"] = {}
                if "ink_area" not in loaded_status:
                    loaded_status["ink_area"] = {}
                if "notes" not in loaded_status:
                    loaded_status["notes"] = {}
                if "dashboard_notices" not in loaded_status:
                    loaded_status["dashboard_notices"] = []
                
                self.annotation_status = loaded_status
                logger.info(f"✓ Loaded annotation status from {self.annotation_file}")
                
                # Save the migrated version
                self._save_annotation_status()
        except Exception as e:
            logger.error(f"⚠ Failed to load annotation status: {e}")
    
    def _save_annotation_status(self):
        """Save annotation status to JSON file"""
        try:
            with open(self.annotation_file, 'w') as f:
                json.dump(self.annotation_status, f, indent=2)
            logger.info(f"✓ Saved annotation status to {self.annotation_file}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to save annotation status: {e}")
            return False

    def compute_scale_factors(self, slices):
        ref_box = slices[0].db.getPhysicBox()
        ref_size = ref_box[0][1] - ref_box[0][0]

        scale_factors = []
        for slc in slices:
            box = slc.db.getPhysicBox()
            size = box[0][1] - box[0][0]
            scale_factors.append(size / ref_size)
        return scale_factors
    
    def _create_notes_panel(self, display_name, highlighted=False):
        """Create a panel for viewing and managing notes for the selection page"""
        import datetime
        
        # Set colors based on highlighted state
        if highlighted:
            bg_color = '#fef08a'  # Yellow background
            border_color = '2px solid #eab308'  # Yellow border
            title_color = '#854d0e'  # Dark yellow text
        else:
            bg_color = 'white'
            border_color = '1px solid #e5e7eb'
            title_color = 'inherit'
        
        # Get current notes for the selected image
        current_notes = self.annotation_status.get("notes", {}).get(display_name, [])
        
        # Text input for new note
        note_input = pn.widgets.TextAreaInput(
            name='Add Note',
            placeholder='Enter your note here...',
            height=80,
            sizing_mode='stretch_width'
        )
        
        # Add note button
        add_note_btn = pn.widgets.Button(
            name='➕ Add Note',
            button_type='success',
            width=120
        )
        
        # Notes display area
        notes_display = pn.Column(sizing_mode='stretch_width')
        
        def refresh_notes_display():
            """Refresh the notes display"""
            notes_display.clear()
            current_notes = self.annotation_status.get("notes", {}).get(display_name, [])
            
            if not current_notes:
                notes_display.append(
                    pn.pane.Markdown("*No notes yet. Add one above!*", 
                                   styles={'color': '#6b7280', 'font-style': 'italic'})
                )
            else:
                for idx, note in enumerate(reversed(current_notes)):
                    timestamp = note.get('timestamp', 'Unknown time')
                    text = note.get('text', '')
                    
                    # Delete button for this note
                    delete_btn = pn.widgets.Button(
                        name='🗑️',
                        button_type='danger',
                        width=40,
                        height=30
                    )
                    
                    # Store the actual index (reverse it back)
                    actual_idx = len(current_notes) - 1 - idx
                    
                    def make_delete_callback(note_idx):
                        def delete_note(event):
                            if display_name in self.annotation_status.get("notes", {}):
                                self.annotation_status["notes"][display_name].pop(note_idx)
                                self._save_annotation_status()
                                refresh_notes_display()
                                # Update checkbox labels to reflect changes
                                self._update_checkbox_labels()
                                logger.info(f"✓ Deleted note {note_idx} for {display_name}")
                                pn.state.notifications.success("Note deleted", duration=1500)
                        return delete_note
                    
                    delete_btn.on_click(make_delete_callback(actual_idx))
                    
                    # Create note card
                    note_card = pn.Card(
                        pn.Column(
                            pn.pane.Markdown(f"**📅 {timestamp}**", 
                                           styles={'font-size': '12px', 'color': '#4b5563'}),
                            pn.pane.Markdown(text, 
                                           styles={'font-size': '14px', 'margin-top': '8px'}),
                        ),
                        header=pn.Row(
                            pn.pane.Markdown(f"**Note #{actual_idx + 1}**"),
                            pn.layout.HSpacer(),
                            delete_btn,
                        ),
                        styles={
                            'background': '#f9fafb',
                            'border': '1px solid #e5e7eb',
                            'border-radius': '8px',
                            'padding': '12px',
                            'margin-bottom': '8px'
                        },
                        collapsed=False,
                        sizing_mode='stretch_width'
                    )
                    notes_display.append(note_card)
        
        def on_add_note(event):
            """Add a new note"""
            text = note_input.value.strip()
            if not text:
                pn.state.notifications.warning("Please enter a note", duration=1500)
                return
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            new_note = {
                'timestamp': timestamp,
                'text': text
            }
            
            # Initialize notes list if it doesn't exist
            if "notes" not in self.annotation_status:
                self.annotation_status["notes"] = {}
            if display_name not in self.annotation_status["notes"]:
                self.annotation_status["notes"][display_name] = []
            
            # Add the note
            self.annotation_status["notes"][display_name].append(new_note)
            self._save_annotation_status()
            
            # Clear input and refresh display
            note_input.value = ''
            refresh_notes_display()
            
            logger.info(f"✓ Added note for {display_name}: {text[:50]}...")
            pn.state.notifications.success("Note added", duration=1500)
        
        add_note_btn.on_click(on_add_note)
        
        # Initial display
        refresh_notes_display()
        
        # Create the notes panel
        notes_panel = pn.Column(
            pn.pane.Markdown("### 📝 Notes", styles={'font-size': '18px', 'font-weight': 'bold', 'color': title_color}),
            pn.pane.Markdown(f"*{display_name}*", styles={'font-size': '14px', 'color': '#6b7280', 'margin-top': '-8px', 'font-style': 'italic'}),
            pn.Spacer(height=5),
            pn.Row(
                note_input,
                pn.Spacer(width=10),
                add_note_btn,
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=10),
            pn.pane.Markdown("**Recent Notes:**", styles={'font-size': '14px', 'font-weight': 'bold'}),
            pn.layout.Divider(),
            notes_display,
            styles={
                'background': bg_color,
                'border': border_color,
                'border-radius': '8px',
                'padding': '16px',
                'max-height': '400px',
                'overflow-y': 'auto'
            },
            sizing_mode='stretch_width',
            scroll=True
        )
        
        return notes_panel

    def _create_dashboard_notices_panel(self):
        """Create a panel for viewing and managing global dashboard notices"""
        import datetime
        
        # Get current dashboard notices
        current_notices = self.annotation_status.get("dashboard_notices", [])
        
        # Text input for new notice
        notice_input = pn.widgets.TextAreaInput(
            name='Add Dashboard Notice',
            placeholder='Enter a notice/announcement for everyone...',
            height=80,
            sizing_mode='stretch_width'
        )
        
        # Add notice button
        add_notice_btn = pn.widgets.Button(
            name='➕ Add Notice',
            button_type='warning',
            width=120
        )
        
        # Notices display area
        notices_display = pn.Column(sizing_mode='stretch_width')
        
        def refresh_notices_display():
            """Refresh the notices display"""
            notices_display.clear()
            current_notices = self.annotation_status.get("dashboard_notices", [])
            
            if not current_notices:
                notices_display.append(
                    pn.pane.Markdown("*No dashboard notices yet.*", 
                                   styles={'color': '#6b7280', 'font-style': 'italic'})
                )
            else:
                for idx, notice in enumerate(reversed(current_notices)):
                    timestamp = notice.get('timestamp', 'Unknown time')
                    text = notice.get('text', '')
                    
                    # Delete button for this notice
                    delete_btn = pn.widgets.Button(
                        name='🗑️',
                        button_type='danger',
                        width=40,
                        height=30
                    )
                    
                    # Store the actual index (reverse it back)
                    actual_idx = len(current_notices) - 1 - idx
                    
                    def make_delete_callback(notice_idx):
                        def delete_notice(event):
                            self.annotation_status["dashboard_notices"].pop(notice_idx)
                            self._save_annotation_status()
                            refresh_notices_display()
                            logger.info(f"✓ Deleted dashboard notice {notice_idx}")
                            pn.state.notifications.success("Notice deleted", duration=1500)
                        return delete_notice
                    
                    delete_btn.on_click(make_delete_callback(actual_idx))
                    
                    # Create notice card
                    notice_card = pn.Card(
                        pn.Column(
                            pn.pane.Markdown(f"**📅 {timestamp}**", 
                                           styles={'font-size': '12px', 'color': '#4b5563'}),
                            pn.pane.Markdown(text, 
                                           styles={'font-size': '14px', 'margin-top': '8px', 'font-weight': 'bold'}),
                        ),
                        header=pn.Row(
                            pn.pane.Markdown(f"**📢 Notice #{actual_idx + 1}**"),
                            pn.layout.HSpacer(),
                            delete_btn,
                        ),
                        styles={
                            'background': '#fef3c7',
                            'border': '2px solid #f59e0b',
                            'border-radius': '8px',
                            'padding': '12px',
                            'margin-bottom': '8px'
                        },
                        collapsed=False,
                        sizing_mode='stretch_width'
                    )
                    notices_display.append(notice_card)
        
        def on_add_notice(event):
            """Add a new dashboard notice"""
            text = notice_input.value.strip()
            if not text:
                pn.state.notifications.warning("Please enter a notice", duration=1500)
                return
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            new_notice = {
                'timestamp': timestamp,
                'text': text
            }
            
            # Initialize notices list if it doesn't exist
            if "dashboard_notices" not in self.annotation_status:
                self.annotation_status["dashboard_notices"] = []
            
            # Add the notice
            self.annotation_status["dashboard_notices"].append(new_notice)
            self._save_annotation_status()
            
            # Clear input and refresh display
            notice_input.value = ''
            refresh_notices_display()
            
            logger.info(f"✓ Added dashboard notice: {text[:50]}...")
            pn.state.notifications.success("Notice added to dashboard", duration=1500)
        
        add_notice_btn.on_click(on_add_notice)
        
        # Initial display
        refresh_notices_display()
        
        # Create the notices panel
        notices_panel = pn.Column(
            pn.pane.Markdown("### 📢 Dashboard Notices", 
                           styles={'font-size': '18px', 'font-weight': 'bold', 'color': '#f59e0b'}),
            pn.pane.Markdown("*Global announcements visible to everyone*", 
                           styles={'font-size': '12px', 'color': '#6b7280', 'font-style': 'italic', 'margin-top': '-10px'}),
            pn.Row(
                notice_input,
                pn.Spacer(width=10),
                add_notice_btn,
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=10),
            pn.pane.Markdown("**Active Notices:**", styles={'font-size': '14px', 'font-weight': 'bold'}),
            pn.layout.Divider(),
            notices_display,
            styles={
                'background': '#fffbeb',
                'border': '2px solid #fbbf24',
                'border-radius': '8px',
                'padding': '16px',
                'max-height': '400px',
                'overflow-y': 'auto'
            },
            sizing_mode='stretch_width',
            scroll=True
        )
        
        return notices_panel


    def load_slices(self, event):
        # Convert display label back to actual name (single selection)
        if not self.checkboxes.value:
            self.main_panel.append(pn.pane.Markdown("**⚠️ Please select a slice.**"))
            return
        
        selected_display_name = self.label_to_name.get(self.checkboxes.value, self.checkboxes.value)
        selected_display_names = [selected_display_name]  # Convert to list for compatibility with rest of code

        selected_files = [self.file_map[name] for name in selected_display_names]
        
        # Check if user wants to load last state
        self.load_with_last_state = (self.state_option.value == 'Load Last State')
        logger.info(f"========================================")
        logger.info(f"Loading slices with option: {self.state_option.value}")
        logger.info(f"load_with_last_state = {self.load_with_last_state}")
        logger.info(f"========================================")
        
        # Clear existing state trackers
        self.state_trackers = []

        n = len(selected_files)
        print("loaded slices: ",n)
        draw_source = bokeh.models.ColumnDataSource(data={"xs": [], "ys": []})

        # Choose class: your SliceDL for single view; Slice for multi

        if self.checkbox2.value:
            SliceClass = None 
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
            pn.pane.HTML(f"<h4>Case Name: {name}</h4>", sizing_mode="stretch_width")
            for name in selected_display_names
        ]

        scale_bar1 = pn.pane.HTML(sizing_mode="stretch_width")

        scale_bar2 = pn.pane.HTML(sizing_mode="stretch_width")

        # Initialize synchronization ONLY with real slices (no placeholders)
        self.multi_slice_sync_app = MultiSliceSyncApp(slices, captions, scale_factors, scale_bar1= scale_bar1, scale_bar2= scale_bar2)
        self.multi_slice_sync_app.is_bbox_mode = True  # <— tell app we're in BB mode
        self.multi_slice_sync_app.run()
        
        # Setup state tracking and restoration for each slice
        for slc, path, display_name in zip(slices, selected_files, selected_display_names):
            # Create state tracker with display_name
            tracker = SliceStateTracker(slc, path, self.state_manager, auto_save_interval=2.0, display_name=display_name)
            self.state_trackers.append(tracker)
            
            # Initialize state indices as None (viewing current state, not a saved timestep)
            self.current_state_index[display_name] = None  # For saved_states
            self.live_tracking_index[display_name] = None  # For live_tracking
            
            logger.info(f">>> Processing slice: {Path(path).parent.name}")
            logger.info(f">>> Keyboard handler (Shift+S) will be registered for {display_name}")
            logger.info(f">>> load_with_last_state: {self.load_with_last_state}")
            
            # Restore last state if requested
            if self.load_with_last_state:
                logger.info(f">>> Attempting to load saved state...")
                saved_state = self.state_manager.load_state(path, display_name=display_name)
                logger.info(f">>> Saved state found: {saved_state is not None}")
                
                if saved_state:
                    logger.info(f"✓ Found saved state for {Path(path).parent.name}")
                    logger.info(f"  Viewport: {saved_state.get('viewport')}")
                    logger.info(f"  Zoom: {saved_state.get('zoom_level')}%")
                    
                    # Use a flag to restore state after first render
                    tracker._pending_restore = saved_state
                    tracker._restore_attempted = False
                    
                    # Restore state immediately after slice is set up
                    # Use Bokeh's add_next_tick_callback to safely modify the figure
                    def do_restore():
                        logger.info(f">>> [CALLBACK] Executing state restoration for {Path(path).parent.name}...")
                        try:
                            success = tracker.restore_state(saved_state)
                            if success:
                                logger.info(f"✓ [CALLBACK] Successfully restored state")
                                logger.info(f"   Viewport: {saved_state.get('viewport')}")
                                logger.info(f"   Zoom: {saved_state.get('zoom_level')}%")
                            else:
                                logger.info(f"✗ [CALLBACK] Failed to restore state")
                        except Exception as e:
                            logger.error(f"⚠ [CALLBACK] Error during restoration: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                    
                    # Schedule restoration using Bokeh's document callback
                    logger.info(f">>> Scheduling restoration via add_next_tick_callback...")
                    logger.info(f">>> slc has canvas attribute: {hasattr(slc, 'canvas')}")
                    if hasattr(slc, 'canvas'):
                        logger.info(f">>> slc.canvas has fig attribute: {hasattr(slc.canvas, 'fig')}")
                        if hasattr(slc.canvas, 'fig'):
                            logger.info(f">>> slc.canvas.fig = {slc.canvas.fig}")
                            logger.info(f">>> slc.canvas.fig.document = {slc.canvas.fig.document if slc.canvas.fig else 'NO FIG'}")
                    
                    if hasattr(slc, 'canvas') and hasattr(slc.canvas, 'fig') and slc.canvas.fig and slc.canvas.fig.document:
                        logger.info(f">>> Document is available, scheduling callback...")
                        slc.canvas.fig.document.add_next_tick_callback(do_restore)
                    else:
                        logger.info(f">>> Document not available, using delayed callback...")
                        # If document isn't ready, schedule with periodic callback
                        restored = [False]  # Track if restoration has been completed
                        attempt_count = [0]
                        
                        def delayed_restore():
                            if restored[0]:  # Already restored, stop trying
                                return
                                
                            attempt_count[0] += 1
                            logger.info(f">>> Delayed restore attempt {attempt_count[0]}/20...")
                            
                            if hasattr(slc, 'canvas') and hasattr(slc.canvas, 'fig') and slc.canvas.fig and slc.canvas.fig.document:
                                logger.info(f">>> Document now available, executing restoration...")
                                do_restore()
                                restored[0] = True  # Mark as complete
                                logger.info(f">>> Restoration complete, stopping delayed callback")
                            else:
                                logger.info(f">>> Still waiting for document (has canvas: {hasattr(slc, 'canvas')}, has fig: {hasattr(slc.canvas, 'fig') if hasattr(slc, 'canvas') else False})...")
                        
                        pn.state.add_periodic_callback(delayed_restore, period=100, count=20)
                else:
                    logger.info(f"ℹ No saved state found for {Path(path).parent.name}")
            else:
                logger.info(f">>> Skipping state restoration (Load New View selected)")
            
            # Setup periodic state saving by hooking into canvas events
            self._setup_auto_save(slc, tracker)

        self.main_panel.clear()

        back_button = pn.widgets.Button(name="⬅️ Back", button_type="warning", width=100)
        back_button.on_click(self.back_to_selection)
        
        # Add Reset button to load 00000.json from saved_states
        reset_button = pn.widgets.Button(name="🔄 Reset", button_type="danger", width=100)
        reset_button.on_click(self._execute_reset_state)
        
        # Add Verified toggle button
        verified_button = pn.widgets.Toggle(
            name="✓ Done",
            button_type="success",
            width=120,
            value=all(self.annotation_status.get("verified", {}).get(name, False) for name in selected_display_names)
        )
        
        def on_verified_toggle(event):
            for name in selected_display_names:
                self.annotation_status["verified"][name] = event.new
            self._save_annotation_status()
            self._update_checkbox_labels()  # Update the checkbox display
            logger.info(f"✓ Updated verified status to {event.new} for {selected_display_names}")
            pn.state.notifications.success(f"Verified status: {'ON' if event.new else 'OFF'}", duration=2000)
        
        verified_button.param.watch(on_verified_toggle, 'value')
        
        # Add Ink Area toggle button
        ink_area_button = pn.widgets.Toggle(
            name="🖊️ Ink Area",
            button_type="primary",
            width=120,
            value=all(self.annotation_status.get("ink_area", {}).get(name, False) for name in selected_display_names)
        )
        
        def on_ink_area_toggle(event):
            for name in selected_display_names:
                self.annotation_status["ink_area"][name] = event.new
            self._save_annotation_status()
            self._update_checkbox_labels()  # Update the checkbox display
            logger.info(f"✓ Updated ink_area status to {event.new} for {selected_display_names}")
            pn.state.notifications.success(f"Ink Area status: {'ON' if event.new else 'OFF'}", duration=2000)
        
        ink_area_button.param.watch(on_ink_area_toggle, 'value')

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
                        pn.layout.HSpacer(),
                        captions[0], 
                        pn.layout.HSpacer(),
                        align="center", 
                        sizing_mode="stretch_width"
                    ),
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
                        "right": "16px",
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

                # === SAVED STATES SECTION (Manual Saves) ===
                # Add Save State button for single slice view (not bbox mode)
                save_state_btn = pn.widgets.Button(
                    name='💾 Save State', 
                    button_type='success', 
                    width=150
                )
                
                def on_save_state_click(event):
                    print(f"[Button] Button clicked! Event: {event}")
                    logger.info(f"[Button] Save State button clicked")
                    self._execute_state_save()
                
                save_state_btn.on_click(on_save_state_click)
                print(f"[Setup] Save State button created and callback registered")

                # Add Load Prev button (for saved_states)
                load_prev_btn = pn.widgets.Button(
                    name='⬅️ Load Prev',
                    button_type='warning',
                    width=120
                )
                
                def on_load_prev_click(event):
                    print(f"[Button] Load Prev button clicked")
                    logger.info(f"[Button] Load Prev button clicked")
                    self._execute_load_prev()
                
                load_prev_btn.on_click(on_load_prev_click)
                
                # Add Load Next button (for saved_states)
                load_next_btn = pn.widgets.Button(
                    name='➡️ Load Next',
                    button_type='warning',
                    width=120
                )
                
                def on_load_next_click(event):
                    print(f"[Button] Load Next button clicked")
                    logger.info(f"[Button] Load Next button clicked")
                    self._execute_load_next()
                
                load_next_btn.on_click(on_load_next_click)
                
                # Get line thickness slider, color selector, and clear button from the first slice's canvas
                line_thickness_slider = None
                line_color_selector = None
                clear_drawings_btn = None
                if hasattr(self, 'multi_slice_sync_app') and self.multi_slice_sync_app and hasattr(self.multi_slice_sync_app, 'slices'):
                    slices = self.multi_slice_sync_app.slices
                    if slices and len(slices) > 0:
                        line_thickness_slider = slices[0].canvas.line_thickness_slider
                        line_color_selector = slices[0].canvas.line_color_selector
                        clear_drawings_btn = slices[0].canvas.clear_drawings_btn
                
                # === LIVE TRACKING SECTION (Auto Saves) ===
                # Add Undo button (for live_tracking)
                undo_btn = pn.widgets.Button(
                    name='↩️ Undo',
                    button_type='primary',
                    width=100
                )
                
                def on_undo_click(event):
                    print(f"[Button] Undo button clicked")
                    logger.info(f"[Button] Undo button clicked")
                    self._execute_live_undo()
                
                undo_btn.on_click(on_undo_click)
                
                # Add Redo button (for live_tracking)
                redo_btn = pn.widgets.Button(
                    name='↪️ Redo',
                    button_type='primary',
                    width=100
                )
                
                def on_redo_click(event):
                    print(f"[Button] Redo button clicked")
                    logger.info(f"[Button] Redo button clicked")
                    self._execute_live_redo()
                
                redo_btn.on_click(on_redo_click)

                slices_layout = pn.Column(
                    pn.Row(
                        # Left column: Back, Verified, Ink Area
                        back_button,
                        pn.Spacer(width=20),
                        verified_button,
                        pn.Spacer(width=10),
                        ink_area_button,
                        # Right column: Reset button aligned to right
                        pn.layout.HSpacer(),
                        reset_button,
                        pn.Spacer(width=20),
                        sizing_mode="stretch_width"
                    ),
                    pn.Row(
                        # Line drawing controls
                        pn.pane.Markdown("**Draw:**", sizing_mode="fixed", width=45),
                        line_thickness_slider if line_thickness_slider else pn.Spacer(width=0),
                        pn.Spacer(width=10),
                        line_color_selector if line_color_selector else pn.Spacer(width=0),
                        pn.Spacer(width=10),
                        clear_drawings_btn if clear_drawings_btn else pn.Spacer(width=0),
                        pn.Spacer(width=30),
                        # Live Tracking controls
                        pn.pane.Markdown("**Live:**", sizing_mode="fixed", width=50),
                        undo_btn,
                        pn.Spacer(width=5),
                        redo_btn,
                        pn.Spacer(width=30),
                        # Saved States controls
                        pn.layout.HSpacer(),  

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
                        
                        pn.pane.Markdown("**Saved:**", sizing_mode="fixed", width=50),
                        load_prev_btn,
                        pn.Spacer(width=5),
                        save_state_btn,
                        pn.Spacer(width=5),
                        load_next_btn,
                        pn.Spacer(width=30),
                        #pn.layout.HSpacer(),
                        captions[0], 
                        #pn.layout.HSpacer(),
                        align="center", 
                        sizing_mode="stretch_width"
                    ),
                    sizing_mode="stretch_width",
                )
        
        elif n == 2:
            slices_layout = pn.Column(
                pn.Row(
                    # Left column: Back, Verified, Ink Area
                    back_button,
                    pn.Spacer(width=20),
                    verified_button,
                    pn.Spacer(width=10),
                    ink_area_button,
                    # Right column: Reset button aligned to right
                    pn.layout.HSpacer(),
                    reset_button,
                    pn.Spacer(width=20),
                    sizing_mode="stretch_width"
                ),
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
                pn.Row(
                    # Left column: Back, Verified, Ink Area
                    back_button,
                    pn.Spacer(width=20),
                    verified_button,
                    pn.Spacer(width=10),
                    ink_area_button,
                    # Right column: Reset button aligned to right
                    pn.layout.HSpacer(),
                    reset_button,
                    pn.Spacer(width=20),
                    sizing_mode="stretch_width"
                ),
                pn.Row(*layout_top_slices, sizing_mode="stretch_both"),
                pn.Row(*layout_top_captions, sizing_mode="stretch_width"),
                pn.Row(*layout_bottom_slices, sizing_mode="stretch_both"),
                pn.Row(*layout_bottom_captions, scale_bar1, sizing_mode="stretch_width"),
                sizing_mode="stretch_both",
            )

        self.main_panel.append(
            pn.Column(
                slices_layout,
                sizing_mode='stretch_both'
            )
        )
        
        # Start live tracking timer (saves every 1 second)
        self._start_live_tracking()
        
        # Setup keyboard shortcuts and add to main panel
        keyboard_shortcuts_html = self._setup_keyboard_shortcuts()
        self.main_panel.append(keyboard_shortcuts_html)

    def _start_live_tracking(self):
        """Start the live tracking periodic callback"""
        def save_live_state():
            try:
                if not hasattr(self, 'state_trackers') or not self.state_trackers:
                    return
                
                for tracker in self.state_trackers:
                    try:
                        state_data = tracker.capture_current_state()
                        tracker.state_manager.save_live_tracking_state(
                            tracker.image_path,
                            state_data,
                            display_name=tracker.display_name,
                            max_files=1000
                        )
                    except Exception as e:
                        logger.error(f"[Live Tracking] Error saving for {tracker.display_name}: {e}")
            except Exception as e:
                logger.error(f"[Live Tracking] Error in live tracking: {e}")
        
        # Save every seconds
        self.live_tracking_callback = pn.state.add_periodic_callback(save_live_state, period=1000)
        logger.info("[Live Tracking] Started with 2-second interval")
        print("[Live Tracking] Started - saving every 2 seconds")
    
    def _stop_live_tracking(self):
        """Stop the live tracking periodic callback"""
        try:
            if hasattr(self, 'live_tracking_callback') and self.live_tracking_callback:
                self.live_tracking_callback.stop()
                self.live_tracking_callback = None
                logger.info("[Live Tracking] Stopped")
                print("[Live Tracking] Stopped")
        except Exception as e:
            logger.error(f"[Live Tracking] Error stopping: {e}")
            print(f"[Live Tracking] Error stopping: {e}")

    def _execute_reset_state(self, event=None):
        """Reset to initial state - clear drawings and reset viewport to full image view"""
        try:
            logger.info(f"[Reset State] Executing reset to initial state")
            print(f"\n{'='*60}")
            print(f"[🔄 Reset State] Resetting to initial state...")
            print(f"{'='*60}")
            
            if not hasattr(self, 'state_trackers') or not self.state_trackers:
                logger.warning(f"[Reset State] No state trackers available")
                print(f"⚠ No active slices to reset")
                pn.state.notifications.warning("No active slices to reset", duration=2000)
                return
            
            # Iterate through all trackers and reset them
            for tracker in self.state_trackers:
                try:
                    display_name = tracker.display_name
                    slc = tracker.slice
                    
                    logger.info(f"[Reset State] Resetting {display_name}")
                    print(f"[Reset State] Resetting {display_name}")
                    
                    # Clear all drawings
                    if hasattr(slc.canvas, 'drawsource') and slc.canvas.drawsource:
                        slc.canvas.drawsource.data = {"xs": [], "ys": []}
                        logger.info(f"[Reset State] Cleared drawings for {display_name}")
                    
                    # Reset viewport to show full image
                    # Get the physical box dimensions from the database
                    if hasattr(slc, 'db') and slc.db:
                        physic_box = slc.db.getPhysicBox()
                        if physic_box:
                            # physic_box is like [[x_min, x_max], [y_min, y_max], [z_min, z_max]]
                            x_min, x_max = physic_box[0]
                            y_min, y_max = physic_box[1]
                            
                            # Calculate width and height
                            width = x_max - x_min
                            height = y_max - y_min
                            
                            # Set viewport to show the full image
                            viewport = [x_min, y_min, width, height]
                            
                            # Use the canvas setViewport method
                            slc.canvas.setViewport(viewport)
                            
                            logger.info(f"[Reset State] Reset viewport to full image: {viewport}")
                            print(f"[Reset State] Reset viewport for {display_name}: x={x_min:.2f}, y={y_min:.2f}, w={width:.2f}, h={height:.2f}")
                            
                            # Trigger a refresh to update the view
                            if hasattr(slc, 'refresh'):
                                slc.refresh("reset_state")
                            
                            # Reset state indices
                            self.current_state_index[display_name] = None
                            self.live_tracking_index[display_name] = None
                            
                            logger.info(f"✓ [Reset State] Successfully reset {display_name}")
                            print(f"✓ Successfully reset {display_name}")
                        else:
                            logger.warning(f"⚠ [Reset State] Could not get physic box for {display_name}")
                            print(f"⚠ Could not determine image dimensions for {display_name}")
                    else:
                        logger.warning(f"⚠ [Reset State] No database loaded for {display_name}")
                        print(f"⚠ No database loaded for {display_name}")
                        
                except Exception as e:
                    logger.error(f"[Reset State] Error resetting {tracker.display_name}: {e}")
                    print(f"✗ Error resetting {tracker.display_name}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            pn.state.notifications.success("Reset to initial state", duration=2000)
            print(f"{'='*60}\n")
                    
        except Exception as e:
            logger.error(f"[Reset State] Error in reset execution: {e}")
            pn.state.notifications.error("Failed to reset state", duration=2000)
            import traceback
            logger.error(traceback.format_exc())

    def _execute_state_save(self):
        """Execute the state save operation"""
        try:
            logger.info(f"[Save State] Executing state save")
            print(f"\n{'='*60}")
            print(f"[💾 Save State] Saving states...")
            print(f"{'='*60}")
            
            if not hasattr(self, 'state_trackers') or not self.state_trackers:
                logger.warning(f"[Save State] No state trackers available")
                print(f"⚠ No active slices to save")
                return
            
            # Iterate through all trackers and save their current state
            for tracker in self.state_trackers:
                try:
                    display_name = tracker.display_name
                    
                    # Find the next available timestep number in saved_states folder
                    # Get all existing saved timesteps
                    existing_timesteps = tracker.state_manager.get_saved_timesteps(
                        tracker.image_path,
                        display_name=display_name,
                        folder_type="saved_states"
                    )
                    
                    # Find the next timestep number (max + 1, or 0 if none exist)
                    if existing_timesteps:
                        next_timestep = max(existing_timesteps) + 1
                    else:
                        next_timestep = 0
                    
                    logger.info(f"[Save State] Next state number: {next_timestep} (existing: {existing_timesteps})")
                    print(f"[Save State] Saving as state {next_timestep}")
                    
                    # Capture and save state with the new timestep number in saved_states folder
                    state_data = tracker.capture_current_state()
                    success = tracker.state_manager.save_timestep_state(
                        tracker.image_path,
                        next_timestep,
                        state_data,
                        display_name=tracker.display_name,
                        folder_type="saved_states"
                    )
                    
                    if success:
                        # After saving, we're back to current state (not viewing a saved timestep)
                        self.current_state_index[display_name] = None
                        logger.info(f"✓ [Save State] Saved state {next_timestep} ({display_name})")
                        print(f"✓ Saved state {next_timestep:05d}.json for {display_name}")
                        print(f"   File: state_logs/{display_name}/{next_timestep:05d}.json")
                    else:
                        logger.error(f"✗ [Save State] Failed to save for {display_name}")
                        print(f"✗ Failed to save for {display_name}")
                except Exception as e:
                    logger.error(f"[Save State] Error saving {tracker.display_name}: {e}")
                    print(f"✗ Error saving {tracker.display_name}: {e}")
            
            print(f"{'='*60}\n")
                    
        except Exception as e:
            logger.error(f"[Save State] Error in save execution: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _execute_load_prev(self):
        """Load the previous saved state for all active slices (from saved_states folder)"""
        try:
            logger.info(f"[Load Prev] Executing load prev operation")
            print(f"\n{'='*60}")
            print(f"[⬅️ Load Prev] Loading previous state...")
            print(f"{'='*60}")
            
            if not hasattr(self, 'state_trackers') or not self.state_trackers:
                logger.warning(f"[Load Prev] No state trackers available")
                print(f"⚠ No active slices to load")
                return
            
            # Iterate through all trackers and load their previous state from saved_states
            for tracker in self.state_trackers:
                try:
                    display_name = tracker.display_name
                    
                    # Get all existing saved states from saved_states folder (excluding 00000.json)
                    all_states = tracker.state_manager.get_saved_timesteps(
                        tracker.image_path,
                        display_name=display_name,
                        folder_type="saved_states"
                    )
                    
                    # Filter out 00000 (current state file) to get only saved timesteps
                    existing_states = [s for s in all_states if s > 0]
                    
                    if not existing_states:
                        print(f"⚠ No saved timesteps available for {display_name}")
                        continue
                    
                    # Sort states in descending order for easier navigation
                    sorted_states = sorted(existing_states, reverse=False)
                    
                    # Get current state index
                    current_idx = self.current_state_index.get(display_name, None)
                    
                    # Determine which state to load
                    if current_idx is None:
                        # Not viewing any saved state yet, load the most recent one
                        prev_idx = sorted_states[-1]  # Highest numbered state
                        logger.info(f"[Load Prev] First load - loading most recent state {prev_idx}")
                    else:
                        # Currently viewing a saved state, find the previous one
                        try:
                            current_position = sorted_states.index(current_idx)
                            if current_position > 0:
                                prev_idx = sorted_states[current_position - 1]
                            else:
                                print(f"⚠ Already at earliest saved state (00001) for {display_name}")
                                continue
                        except ValueError:
                            # Current index not in list, go to last state
                            prev_idx = sorted_states[-1]
                    
                    logger.info(f"[Load Prev] Loading state {prev_idx} for {display_name} (from {current_idx or 'current'})")
                    print(f"[Load Prev] Loading state {prev_idx:05d}.json for {display_name}")
                    
                    # Load the previous state from saved_states folder
                    state_file = tracker.state_manager._get_state_file(
                        tracker.image_path, 
                        timestep=prev_idx,
                        display_name=display_name,
                        folder_type="saved_states"
                    )
                    
                    if state_file.exists():
                        with open(state_file, 'r') as f:
                            state_data = json.load(f)
                        
                        # Restore the state
                        success = tracker.restore_state(state_data)
                        
                        if success:
                            self.current_state_index[display_name] = prev_idx
                            logger.info(f"✓ [Load Prev] Loaded state {prev_idx} for {display_name}")
                            print(f"✓ Loaded state {prev_idx:05d}.json for {display_name}")
                        else:
                            logger.error(f"✗ [Load Prev] Failed to restore state for {display_name}")
                            print(f"✗ Failed to restore state for {display_name}")
                    else:
                        print(f"✗ State file not found for {display_name}")
                        
                except Exception as e:
                    logger.error(f"[Load Prev] Error loading state for {tracker.display_name}: {e}")
                    print(f"✗ Error loading state for {tracker.display_name}: {e}")
            
            print(f"{'='*60}\n")
                    
        except Exception as e:
            logger.error(f"[Load Prev] Error in load prev execution: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _execute_load_next(self):
        """Load the next saved state for all active slices (from saved_states folder)"""
        try:
            logger.info(f"[Load Next] Executing load next operation")
            print(f"\n{'='*60}")
            print(f"[➡️ Load Next] Loading next state...")
            print(f"{'='*60}")
            
            if not hasattr(self, 'state_trackers') or not self.state_trackers:
                logger.warning(f"[Load Next] No state trackers available")
                print(f"⚠ No active slices to load")
                return
            
            # Iterate through all trackers and load their next state from saved_states
            for tracker in self.state_trackers:
                try:
                    display_name = tracker.display_name
                    
                    # Get all existing saved states from saved_states folder (excluding 00000.json)
                    all_states = tracker.state_manager.get_saved_timesteps(
                        tracker.image_path,
                        display_name=display_name,
                        folder_type="saved_states"
                    )
                    
                    # Filter out 00000 (current state file) to get only saved timesteps
                    existing_states = [s for s in all_states if s > 0]
                    
                    if not existing_states:
                        print(f"⚠ No saved timesteps available for {display_name}")
                        continue
                    
                    # Sort states in ascending order
                    sorted_states = sorted(existing_states)
                    
                    # Get current state index
                    current_idx = self.current_state_index.get(display_name, None)
                    
                    # Determine which state to load
                    if current_idx is None:
                        # Not viewing any saved state, can't redo
                        print(f"⚠ Not viewing a saved state for {display_name}, cannot load next")
                        continue
                    else:
                        # Currently viewing a saved state, find the next one
                        try:
                            current_position = sorted_states.index(current_idx)
                            if current_position < len(sorted_states) - 1:
                                next_idx = sorted_states[current_position + 1]
                            else:
                                print(f"⚠ Already at latest saved state ({sorted_states[-1]:05d}) for {display_name}")
                                continue
                        except ValueError:
                            # Current index not in list, go to first state
                            next_idx = sorted_states[0]
                    
                    logger.info(f"[Load Next] Loading state {next_idx} for {display_name} (from {current_idx})")
                    print(f"[Load Next] Loading state {next_idx:05d}.json for {display_name}")
                    
                    # Load the next state from saved_states folder
                    state_file = tracker.state_manager._get_state_file(
                        tracker.image_path, 
                        timestep=next_idx,
                        display_name=display_name,
                        folder_type="saved_states"
                    )
                    
                    if state_file.exists():
                        with open(state_file, 'r') as f:
                            state_data = json.load(f)
                        
                        # Restore the state
                        success = tracker.restore_state(state_data)
                        
                        if success:
                            self.current_state_index[display_name] = next_idx
                            logger.info(f"✓ [Load Next] Loaded state {next_idx} for {display_name}")
                            print(f"✓ Loaded state {next_idx:05d}.json for {display_name}")
                        else:
                            logger.error(f"✗ [Load Next] Failed to restore state for {display_name}")
                            print(f"✗ Failed to restore state for {display_name}")
                    else:
                        print(f"✗ State file not found for {display_name}")
                        
                except Exception as e:
                    logger.error(f"[Load Next] Error loading state for {tracker.display_name}: {e}")
                    print(f"✗ Error loading state for {tracker.display_name}: {e}")
            
            print(f"{'='*60}\n")
                    
        except Exception as e:
            logger.error(f"[Load Next] Error in load next execution: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _execute_live_undo(self):
        """Load the previous live tracking state for all active slices (from live_tracking folder)"""
        try:
            logger.info(f"[Live Undo] Executing live undo operation")
            print(f"\n{'='*60}")
            print(f"[↩️ Undo] Loading previous live state...")
            print(f"{'='*60}")
            
            if not hasattr(self, 'state_trackers') or not self.state_trackers:
                logger.warning(f"[Live Undo] No state trackers available")
                print(f"⚠ No active slices to undo")
                return
            
            # Iterate through all trackers and load their previous state from live_tracking
            for tracker in self.state_trackers:
                try:
                    display_name = tracker.display_name
                    
                    # Get all existing live tracking states (excluding 00000.json)
                    all_states = tracker.state_manager.get_saved_timesteps(
                        tracker.image_path,
                        display_name=display_name,
                        folder_type="live_tracking"
                    )
                    
                    # Filter out 00000 to get only live tracking timesteps
                    existing_states = [s for s in all_states if s > 0]
                    
                    if not existing_states:
                        print(f"⚠ No live tracking states available for {display_name}")
                        continue
                    
                    # Sort states
                    sorted_states = sorted(existing_states, reverse=False)
                    
                    # Get current live tracking index
                    current_idx = self.live_tracking_index.get(display_name, None)
                    
                    # Determine which state to load
                    if current_idx is None:
                        # Not viewing any live state yet, load the most recent one
                        prev_idx = sorted_states[-1]
                        logger.info(f"[Live Undo] First undo - loading most recent live state {prev_idx}")
                    else:
                        # Currently viewing a live state, find the previous one
                        try:
                            current_position = sorted_states.index(current_idx)
                            if current_position > 0:
                                prev_idx = sorted_states[current_position - 1]
                            else:
                                print(f"⚠ Already at earliest live state for {display_name}")
                                continue
                        except ValueError:
                            prev_idx = sorted_states[-1]
                    
                    logger.info(f"[Live Undo] Loading live state {prev_idx} for {display_name}")
                    print(f"[Live Undo] Loading live state {prev_idx:05d}.json for {display_name}")
                    
                    # Load the previous live state
                    state_file = tracker.state_manager._get_state_file(
                        tracker.image_path, 
                        timestep=prev_idx,
                        display_name=display_name,
                        folder_type="live_tracking"
                    )
                    
                    if state_file.exists():
                        with open(state_file, 'r') as f:
                            state_data = json.load(f)
                        
                        # Restore the state
                        success = tracker.restore_state(state_data)
                        
                        if success:
                            self.live_tracking_index[display_name] = prev_idx
                            logger.info(f"✓ [Live Undo] Loaded live state {prev_idx} for {display_name}")
                            print(f"✓ Loaded live state {prev_idx:05d}.json for {display_name}")
                        else:
                            logger.error(f"✗ [Live Undo] Failed to restore state for {display_name}")
                            print(f"✗ Failed to restore state for {display_name}")
                    else:
                        print(f"✗ Live state file not found for {display_name}")
                        
                except Exception as e:
                    logger.error(f"[Live Undo] Error loading state for {tracker.display_name}: {e}")
                    print(f"✗ Error loading state for {tracker.display_name}: {e}")
            
            print(f"{'='*60}\n")
                    
        except Exception as e:
            logger.error(f"[Live Undo] Error in live undo execution: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _execute_live_redo(self):
        """Load the next live tracking state for all active slices (from live_tracking folder)"""
        try:
            logger.info(f"[Live Redo] Executing live redo operation")
            print(f"\n{'='*60}")
            print(f"[↪️ Redo] Loading next live state...")
            print(f"{'='*60}")
            
            if not hasattr(self, 'state_trackers') or not self.state_trackers:
                logger.warning(f"[Live Redo] No state trackers available")
                print(f"⚠ No active slices to redo")
                return
            
            # Iterate through all trackers and load their next state from live_tracking
            for tracker in self.state_trackers:
                try:
                    display_name = tracker.display_name
                    
                    # Get all existing live tracking states (excluding 00000.json)
                    all_states = tracker.state_manager.get_saved_timesteps(
                        tracker.image_path,
                        display_name=display_name,
                        folder_type="live_tracking"
                    )
                    
                    # Filter out 00000 to get only live tracking timesteps
                    existing_states = [s for s in all_states if s > 0]
                    
                    if not existing_states:
                        print(f"⚠ No live tracking states available for {display_name}")
                        continue
                    
                    # Sort states
                    sorted_states = sorted(existing_states)
                    
                    # Get current live tracking index
                    current_idx = self.live_tracking_index.get(display_name, None)
                    
                    # Determine which state to load
                    if current_idx is None:
                        # Not viewing any live state, can't redo
                        print(f"⚠ Not viewing a live state for {display_name}, cannot redo")
                        continue
                    else:
                        # Currently viewing a live state, find the next one
                        try:
                            current_position = sorted_states.index(current_idx)
                            if current_position < len(sorted_states) - 1:
                                next_idx = sorted_states[current_position + 1]
                            else:
                                print(f"⚠ Already at latest live state for {display_name}")
                                continue
                        except ValueError:
                            next_idx = sorted_states[0]
                    
                    logger.info(f"[Live Redo] Loading live state {next_idx} for {display_name}")
                    print(f"[Live Redo] Loading live state {next_idx:05d}.json for {display_name}")
                    
                    # Load the next live state
                    state_file = tracker.state_manager._get_state_file(
                        tracker.image_path, 
                        timestep=next_idx,
                        display_name=display_name,
                        folder_type="live_tracking"
                    )
                    
                    if state_file.exists():
                        with open(state_file, 'r') as f:
                            state_data = json.load(f)
                        
                        # Restore the state
                        success = tracker.restore_state(state_data)
                        
                        if success:
                            self.live_tracking_index[display_name] = next_idx
                            logger.info(f"✓ [Live Redo] Loaded live state {next_idx} for {display_name}")
                            print(f"✓ Loaded live state {next_idx:05d}.json for {display_name}")
                        else:
                            logger.error(f"✗ [Live Redo] Failed to restore state for {display_name}")
                            print(f"✗ Failed to restore state for {display_name}")
                    else:
                        print(f"✗ Live state file not found for {display_name}")
                        
                except Exception as e:
                    logger.error(f"[Live Redo] Error loading state for {tracker.display_name}: {e}")
                    print(f"✗ Error loading state for {tracker.display_name}: {e}")
            
            print(f"{'='*60}\n")
                    
        except Exception as e:
            logger.error(f"[Live Redo] Error in live redo execution: {e}")
            import traceback
            logger.error(traceback.format_exc())                    
        except Exception as e:
            logger.error(f"[Redo] Error in redo execution: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _setup_auto_save(self, slice_obj, tracker):
        """
        Setup automatic state saving when viewport or drawings change
        """
        try:
            # Hook into range changes for viewport tracking
            fig = slice_obj.canvas.fig
            
            def on_range_change(attr, old, new):
                # Save state if interval has passed and state changed
                tracker.save_if_changed()
            
            # Attach to x and y range changes
            fig.x_range.on_change('start', on_range_change)
            fig.x_range.on_change('end', on_range_change)
            fig.y_range.on_change('start', on_range_change)
            fig.y_range.on_change('end', on_range_change)
            
            # Hook into drawing source changes if available
            if hasattr(slice_obj.canvas, 'drawsource') and slice_obj.canvas.drawsource:
                def on_drawing_change(attr, old, new):
                    # Save when drawings are modified
                    tracker.save_if_changed()
                
                slice_obj.canvas.drawsource.on_change('data', on_drawing_change)
            
            print(f"✓ Auto-save enabled for {Path(tracker.image_path).parent.name}")
            
        except Exception as e:
            print(f"⚠ Failed to setup auto-save: {e}")
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for the application using HTML pane with Shadow DOM support"""
        
        script = """
        <script>
        function $$$(selector, rootNode=document.body) {
            const arr = []

            const traverser = node => {
                // 1. decline all nodes that are not elements
                if(node.nodeType !== Node.ELEMENT_NODE) {
                    return
                }

                // 2. add the node to the array, if it matches the selector
                if(node.matches(selector)) {
                    arr.push(node)
                }

                // 3. loop through the children
                const children = node.children
                if (children.length) {
                    for(const child of children) {
                        traverser(child)
                    }
                }

                // 4. check for shadow DOM, and loop through it's children
                const shadowRoot = node.shadowRoot
                if (shadowRoot) {
                    const shadowChildren = shadowRoot.children
                    for(const shadowChild of shadowChildren) {
                        traverser(shadowChild)
                    }
                }
            }

            traverser(rootNode)
            return arr
        }

        const doc = window.parent.document;
        
        doc.addEventListener('keydown', function(e) {
            // Find buttons every time to ensure we have the latest DOM
            const buttons = Array.from($$$('button[type=button]'));
            
            let handled = false;
            
            if (e.shiftKey && e.key.toLowerCase() === 's') {
                // Shift+S = Save State
                const btn = buttons.find(el => el.innerText.includes('Save State'));
                if (btn) {
                    e.preventDefault();
                    console.log('🎹 Shift+S pressed - Save State');
                    btn.click();
                    handled = true;
                }
            } else if (e.ctrlKey && e.key.toLowerCase() === 'z') {
                // Ctrl+Z = Undo (Live)
                const btn = buttons.find(el => el.innerText.includes('Undo'));
                if (btn) {
                    e.preventDefault();
                    console.log('🎹 Ctrl+Z pressed - Undo');
                    btn.click();
                    handled = true;
                }
            } else if (e.ctrlKey && e.key.toLowerCase() === 'y') {
                // Ctrl+Y = Redo (Live)
                const btn = buttons.find(el => el.innerText.includes('Redo'));
                if (btn) {
                    e.preventDefault();
                    console.log('🎹 Ctrl+Y pressed - Redo');
                    btn.click();
                    handled = true;
                }
            } else if ((e.altKey && e.key === 'ArrowLeft') || e.key === '[') {
                // Alt+Left or [ = Load Prev
                const btn = buttons.find(el => el.innerText.includes('Load Prev'));
                if (btn) {
                    e.preventDefault();
                    console.log('🎹 Alt+Left or [ pressed - Load Prev');
                    btn.click();
                    handled = true;
                }
            } else if ((e.altKey && e.key === 'ArrowRight') || e.key === ']') {
                // Alt+Right or ] = Load Next
                const btn = buttons.find(el => el.innerText.includes('Load Next'));
                if (btn) {
                    e.preventDefault();
                    console.log('🎹 Alt+Right or ] pressed - Load Next');
                    btn.click();
                    handled = true;
                }
            }
            
            if (handled) {
                e.stopPropagation();
            }
        });
        
        console.log('🎹 Keyboard shortcuts registered!');
        console.log('  Shift+S: Save State');
        console.log('  Ctrl+Z: Undo (Live Tracking)');
        console.log('  Ctrl+Y: Redo (Live Tracking)');
        console.log('  Alt+Left or [: Load Prev');
        console.log('  Alt+Right or ]: Load Next');
        </script>
        """
        
        # Create HTML pane with the script
        self.keyboard_shortcuts_pane = pn.pane.HTML(script, width=0, height=0, sizing_mode='fixed')
        
        logger.info("🎹 Keyboard shortcuts enabled")
        print("🎹 Keyboard shortcuts enabled:")
        print("  Shift+S: Save State")
        print("  Ctrl+Z: Undo (Live Tracking)")
        print("  Ctrl+Y: Redo (Live Tracking)")
        print("  Alt+Left or [: Load Prev")
        print("  Alt+Right or ]: Load Next")
        
        return self.keyboard_shortcuts_pane

    def back_to_selection(self, event):
        try:
            logger.info(f"========================================")
            logger.info(f"BACK BUTTON CLICKED - Saving current state")
            logger.info(f"========================================")
            
            # Stop live tracking first
            self._stop_live_tracking()
            
            # Force save state for all active slices before going back
            for tracker in self.state_trackers:
                try:
                    # Capture state RIGHT NOW before anything changes
                    current_state = tracker.capture_current_state()
                    logger.info(f">>> Captured state before back:")
                    logger.info(f"    Viewport: {current_state.get('viewport')}")
                    logger.info(f"    Zoom: {current_state.get('zoom_level')}%")
                    
                    # Force save immediately
                    success = tracker.state_manager.save_state(tracker.image_path, current_state, display_name=tracker.display_name, folder_type="saved_states")
                    if success:
                        logger.info(f"✓ Saved state for {Path(tracker.image_path).parent.name}")
                    else:
                        logger.info(f"✗ Failed to save state for {Path(tracker.image_path).parent.name}")
                    
                    # Clean up live tracking files except the last one
                    deleted_count = tracker.state_manager.cleanup_live_tracking_except_last(tracker.image_path, display_name=tracker.display_name)
                    logger.info(f"🧹 Cleaned up {deleted_count} live tracking files for {tracker.display_name}")
                    
                except Exception as e:
                    logger.error(f"⚠ Failed to save state: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Clear trackers
            self.state_trackers = []
            
            # Return to selection page
            self.main_panel.clear()
            self.main_panel.append(self.selection_page)
            logger.info("✓ Successfully returned to selection page")
            
        except Exception as e:
            logger.error(f"❌ Error in back_to_selection: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Try to at least clear and show selection page
            try:
                self.main_panel.clear()
                self.main_panel.append(self.selection_page)
            except:
                pass


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

    log_filename = os.environ.get("OPENVISUSPY_DASHBOARDS_LOG_FILENAME", "./openvisuspy-dashboards.log")
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



    # Resolve dataset paths: prefer API if provided, else CLI args
    api_url = os.environ.get("MAGICSCAN_API_URL")
    paths = []
    if api_url:
        try:
            resp = requests.get(api_url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            # Expecting {"paths": ["/path/..../visus.idx", ...]}
            paths = list(data.get("paths", [])) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[WARN] Failed to fetch MAGICSCAN_API_URL={api_url}: {e}")
            paths = []

    if not paths:
        paths = sys.argv[1:]

    app = SliceSelectorApp(paths)
    #app = SliceSelectorApp(sys.argv[1:])
    app.main_panel.servable()