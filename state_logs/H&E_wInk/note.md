# State Management Feature for OpenVisusPy MagicScan

## Overview

The state management system allows users to save and restore the viewing state of images, including:
- **Viewport position and zoom level**
- **Drawing annotations** (freehand drawings)
- **Timestamps** for tracking when state was last saved

## Features

### 1. Load Options
When selecting images from the main page, you now have two loading options:

- **Load New State**: Start with a fresh view (default zoom and no annotations)
- **Load Last State**: Restore the last saved state including zoom level and drawings

### 2. Automatic State Saving
- State is automatically saved every 2 seconds when changes are detected
- Changes tracked include:
  - Viewport position (panning)
  - Zoom level
  - Drawing annotations

### 3. Manual State Saving
- State is automatically saved when you click the "Back" button
- This ensures all changes are persisted before returning to the selection page

## How It Works

### State Storage
- States are stored as JSON files in the `state_logs/` directory
- Each image gets its own state file named `{image_name}_state.json`
- State files include:
  ```json
  {
    "viewport": [x, y, width, height],
    "zoom_level": 100.0,
    "drawings": {
      "xs": [[x1, x2, ...], [x1, x2, ...]],
      "ys": [[y1, y2, ...], [y1, y2, ...]]
    },
    "timestamp": 1234567890.123,
    "image_path": "/path/to/image/visus.idx"
  }
  ```

### Workflow

1. **Select Images**: Choose one or more images from the main page
2. **Choose Load Option**: 
   - Select "Load New State" for fresh start
   - Select "Load Last State" to restore previous session
3. **Click "Load Selected Slices"**: Images load with appropriate state
4. **Work with Images**: Zoom, pan, draw annotations
5. **State Auto-Saves**: Changes save automatically every 2 seconds
6. **Click "Back"**: Final state is saved before returning to selection

## Configuration

### Environment Variables

```bash
# Directory for storing state log files (default: ./state_logs)
export OPENVISUSPY_STATE_LOG_DIR="/path/to/state/logs"

# Auto-save interval can be modified in the code (default: 2.0 seconds)
```

### Docker Setup

For the Docker container, mount a volume to persist state logs:

```yaml
volumes:
  - ./state_logs:/usr/local/lib/python3.10/site-packages/openvisuspy/app_magicscan/state_logs
```

## Usage Example

### First Session
1. Select "1161_Panel2_in_idx"
2. Choose "Load New State"
3. Load the image
4. Zoom in to a region of interest
5. Draw some annotations
6. Click "Back" - state is saved

### Second Session
1. Select "1161_Panel2_in_idx" again
2. Choose "Load Last State"
3. Load the image
4. Image appears with your previous zoom level and annotations restored!

## Technical Details

### Classes

#### `StateManager`
- Handles file I/O for state persistence
- Methods:
  - `save_state(image_path, state_data)`: Save state to file
  - `load_state(image_path)`: Load state from file
  - `has_saved_state(image_path)`: Check if state exists
  - `delete_state(image_path)`: Remove saved state

#### `SliceStateTracker`
- Tracks changes for individual slices
- Methods:
  - `capture_current_state()`: Get current viewport and drawings
  - `save_if_changed()`: Conditional save based on interval
  - `force_save()`: Immediate save regardless of interval
  - `restore_state(state_data)`: Apply saved state to slice

### Integration Points

1. **SliceSelectorApp.__init__**: Initialize StateManager
2. **SliceSelectorApp.load_slices**: Create trackers and restore state
3. **SliceSelectorApp._setup_auto_save**: Hook into canvas events
4. **SliceSelectorApp.back_to_selection**: Force save before leaving

## Troubleshooting

### State Not Saving
- Check that `state_logs/` directory is writable
- Look for errors in console: `Failed to save state`
- Verify auto-save hooks are attached: Look for "✓ Auto-save enabled"

### State Not Restoring
- Confirm state file exists in `state_logs/`
- Check console for: "✓ Restored saved state" or "⚠ Failed to restore state"
- Verify "Load Last State" option is selected

### Drawings Not Appearing
- Ensure you're using the FreehandDrawTool (not other drawing tools)
- Check that `drawsource` is properly initialized
- Look for drawing data in state file: `"xs"` and `"ys"` arrays should have content

## Testing

### Manual Test Procedure

1. **Start the application**:
   ```bash
   docker exec -it syncview_1177_p11-syncview-1 bash
   # Check logs
   tail -f /tmp/openvisuspy-dashboards.log
   ```

2. **First load** (New State):
   - Select an image
   - Choose "Load New State"
   - Load and zoom/draw
   - Click Back
   - Check for "✓ Saved state" message

3. **Second load** (Last State):
   - Select same image
   - Choose "Load Last State"
   - Load
   - Verify zoom and drawings are restored

4. **Verify state files**:
   ```bash
   ls -la state_logs/
   cat state_logs/*_state.json
   ```

## Future Enhancements

- [ ] Add "Clear State" button to delete saved states
- [ ] Show state timestamp in UI
- [ ] Support multiple saved states per image (named snapshots)
- [ ] Export/import state files
- [ ] Compress state files for large annotation sets
- [ ] Add state preview thumbnails

## Notes

- State files are independent per image
- Multiple users sharing state_logs directory will share states
- For multi-user setups, consider user-specific state directories
- Drawing annotations are stored as coordinate arrays
- Large numbers of annotations may increase state file size
