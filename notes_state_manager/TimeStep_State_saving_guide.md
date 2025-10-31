# Timestep State Saving Implementation Guide

## Overview
Enhanced state saving system that organizes state files by image display name and supports saving timestep-specific states via keyboard shortcut.

## Folder Structure
```
state_logs/
  {display_name}/     # e.g., "P11", "P12" instead of filename
    00000.json        # Current/default state
    00001.json        # State saved for timestep 1
    00002.json        # State saved for timestep 2
    ...
```

## Key Features

### 1. Display Name-Based Folders
- Each image now has its own folder named after the **display name** shown in the UI (e.g., "P11", "P12")
- Display names are typically the parent directory name of the .idx file
- Example: `/data/scans/P11/image.idx` → `state_logs/P11/`
- This makes it easier to identify which image the states belong to

### 2. Automatic Current State Saving
- The current state is always saved as `00000.json`
- Happens automatically when navigating away or closing the application
- Contains viewport position, zoom level, and drawing annotations

### 3. Timestep-Specific State Saving
- Press **Shift+S** key to save the current state for the active timestep
- File naming: `{timestep:05d}.json` (e.g., timestep 42 → `00042.json`)
- Each timestep state includes:
  - Viewport position and zoom level
  - Drawing annotations
  - Timestep number
  - Timestamp

## Keyboard Shortcuts

- **Shift + S**: Save current state for active timestep
  - Creates a new JSON file named after the current timestep
  - Check console for confirmation: "✓ Saved state for timestep X (DisplayName)"

## Implementation Details

### StateManager Methods

#### `_get_state_file(image_path, timestep=None, display_name=None)`
Creates display name-based folders and returns appropriate file path:
- `display_name="P11"` → uses "P11" as folder name
- `display_name=None` → falls back to filename stem
- `timestep=None` → returns `00000.json` (default state)
- `timestep=42` → returns `00042.json` (timestep-specific state)

#### `save_state(image_path, state_data, timestep=None, display_name=None)`
Saves state to appropriate file with optional timestep and display_name parameters.

#### `save_timestep_state(image_path, timestep, state_data, display_name=None)`
Convenience method for saving timestep-specific states (called when Shift+S is pressed).

#### `get_saved_timesteps(image_path, display_name=None)`
Returns list of all saved timestep numbers for an image (excludes 00000.json).

#### `load_state(image_path, display_name=None)`
Loads the default state (00000.json) for an image.

#### `list_all_states()`
Lists all saved states across all images with metadata:
- file name
- display name (folder name)
- image path
- timestamp
- timestep (if applicable)
- has_drawings flag

## Usage

### Automatic Saving
```python
# Current state saved automatically on navigation/exit
state_data = tracker.capture_current_state()
tracker.state_manager.save_state(tracker.image_path, state_data, display_name=tracker.display_name)
# → Creates: state_logs/P11/00000.json (using display_name "P11")
```

### Manual Timestep Saving
```python
# User presses Shift+S key with timestep=42 active
current_timestep = slice.T.value  # Get current timestep
state_data = tracker.capture_current_state()
tracker.state_manager.save_timestep_state(
    image_path, 
    current_timestep, 
    state_data, 
    display_name="P11"
)
# → Creates: state_logs/P11/00042.json
```

### Loading States
```python
# Load default state
saved_state = state_manager.load_state(image_path, display_name="P11")
# Loads from: state_logs/P11/00000.json

# Get list of saved timesteps
timesteps = state_manager.get_saved_timesteps(image_path, display_name="P11")
# Returns: [1, 2, 5, 42, 100] (example)
```

## Keyboard Event Handler

Located in `main.py`, the keyboard handler uses JavaScript to detect keypresses:
1. Listens for **Shift+S** key press using JavaScript `document.addEventListener`
2. Detects `event.shiftKey` and checks for 'S' key (key code 83)
3. Updates a hidden `TextInput` widget to bridge JavaScript → Python
4. Python callback captures current timestep from `slice.T.value`
5. Captures current state (viewport, drawings, zoom)
6. Saves state with timestep number and display_name
7. Logs success/failure with display name

**Note**: Bokeh doesn't have a native Python `KeyEvent`, so we use JavaScript to detect keyboard input and communicate with Python via a hidden widget.

```python
# Implementation snippet
save_trigger = TextInput(value="", visible=False)

js_code = """
document.addEventListener('keydown', function(event) {
    if (event.shiftKey && (event.key === 'S' || event.keyCode === 83)) {
        save_trigger.value = String(Date.now());
    }
});
"""

callback = CustomJS(args=dict(save_trigger=save_trigger), code=js_code)
slc.canvas.fig.js_on_event('document_ready', callback)

def on_save_trigger_change(attr, old, new):
    # Save timestep state with display_name
    tracker.state_manager.save_timestep_state(...)

save_trigger.on_change('value', on_save_trigger_change)
```

## File Format

### State JSON Structure
```json
{
  "image_path": "/path/to/image.idx",
  "timestamp": "2024-01-15T10:30:45.123456",
  "timestep": 42,  // Optional: only in timestep-specific files
  "viewport": {
    "x": 100.5,
    "y": 200.3,
    "width": 512,
    "height": 512
  },
  "zoom_level": 150.25,
  "drawings": {
    "xs": [[10, 20, 30], [40, 50, 60]],
    "ys": [[15, 25, 35], [45, 55, 65]]
  }
}
```

## Migration from Old Structure

Old structure:
```
state_logs/
  image_scan_123_state.json
  another_image_state.json
```

New structure (display name-based):
```
state_logs/
  P11/              # Display name instead of filename
    00000.json
  P12/
    00000.json
```

The system automatically creates folders on first save using the display name. Old state files can be manually migrated by:
1. Creating display name-specific folder (e.g., "P11")
2. Renaming `{image}_state.json` to `00000.json`
3. Moving into appropriate folder

## Benefits

1. **Human-Readable Organization**: Folders use display names (e.g., "P11") instead of cryptic filenames
2. **Easy Navigation**: Quickly find states by patient/sample name
3. **History**: Keep multiple timestep states for comparison/replay
4. **Clarity**: Zero-padded filenames (00001, 00042) sort naturally
5. **Flexibility**: Easy to add/delete timestep states without affecting default
6. **Scalability**: No filename collision issues with many images

## Testing

To test the implementation:
1. Open an image in the viewer (note its display name, e.g., "P11")
2. Navigate to different viewport positions
3. Draw some annotations
4. Change timestep (if applicable)
5. Press **Shift+S** key → Check console for "✓ Saved state for timestep X (P11)"
6. Check `state_logs/P11/` folder for new JSON file (e.g., `00042.json`)
7. Navigate away → Check for `00000.json` with current state in `state_logs/P11/`
8. Reload image → Should restore viewport and drawings from `state_logs/P11/00000.json`

## Troubleshooting

**Q: Shift+S key doesn't save anything**
- Make sure you're pressing Shift AND S together (capital S)
- Check browser console (F12) for "Shift+S pressed - triggering save" message
- Check Python logs for save confirmation or error messages
- Verify timestep value is available (`slice.T.value`)
- Ensure keyboard handler JavaScript was installed (check for "Keyboard handler for Shift+S installed" in console)
- Try refreshing the page if handler doesn't respond

**Q: Folder named with filename instead of display name**
- Check if display_name is being passed correctly to StateManager methods
- Verify tracker.display_name is set during initialization
- If display_name is None, system falls back to filename stem

**Q: Folder not created**
- Check state_logs directory permissions
- Verify display_name or image_path is valid
- Check logs for PathError exceptions

**Q: States not loading on reload**
- Verify `load_with_last_state` flag is True
- Check `state_logs/{display_name}/00000.json` exists
- Ensure display_name matches between save and load
- Review restoration logs for errors
