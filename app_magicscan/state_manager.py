"""
State Manager for OpenVisusPy MagicScan Application
Handles persistence of viewport state (zoom level, position) and drawing annotations
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages persistent state for image slices including:
    - Viewport position and zoom level
    - Drawing annotations (freehand drawings)
    - Timestamps for state changes
    - Supports two modes: live_tracking and saved_states
    """
    
    def __init__(self, state_dir: str = "./state_logs"):
        """
        Initialize the state manager
        
        Args:
            state_dir: Directory to store state log files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"StateManager initialized with state_dir: {self.state_dir}")
    
    def _get_state_file(self, image_path: str, timestep: Optional[int] = None, display_name: Optional[str] = None, folder_type: str = "saved_states") -> Path:
        """
        Get the state file path for a given image
        
        Args:
            image_path: Path to the image/idx file
            timestep: Optional timestep number for timestep-specific state files
            display_name: Optional display name to use as folder name (e.g., "P11")
            folder_type: Either "live_tracking" or "saved_states" (default: "saved_states")
            
        Returns:
            Path to the state file
        """
        # Use display_name if provided, otherwise fall back to filename stem
        if display_name:
            folder_name = display_name
        else:
            folder_name = Path(image_path).stem
        
        # Create image-specific folder with subfolder for folder_type
        image_folder = self.state_dir / folder_name / folder_type
        image_folder.mkdir(parents=True, exist_ok=True)
        
        # Determine filename
        if timestep is None:
            # Current state file
            state_file = image_folder / "00000.json"
        else:
            # Timestep-specific state file
            state_file = image_folder / f"{timestep:05d}.json"
        
        return state_file
    
    def save_state(self, image_path: str, state_data: Dict[str, Any], timestep: Optional[int] = None, display_name: Optional[str] = None, folder_type: str = "saved_states") -> bool:
        """
        Save the current state for an image
        
        Args:
            image_path: Path to the image/idx file
            state_data: Dictionary containing state information:
                - viewport: [x, y, width, height]
                - zoom_level: current zoom percentage
                - drawings: {"xs": [[...]], "ys": [[...]]}
                - timestamp: when this state was saved
            timestep: Optional timestep number. If provided, saves as timestep-specific file
            display_name: Optional display name to use as folder name (e.g., "P11")
            folder_type: Either "live_tracking" or "saved_states" (default: "saved_states")
                
        Returns:
            True if save was successful
        """
        try:
            state_file = self._get_state_file(image_path, timestep, display_name, folder_type)
            
            # Add timestamp and image path to the state
            state_data["timestamp"] = time.time()
            state_data["image_path"] = str(image_path)
            if timestep is not None:
                state_data["timestep"] = timestep
            
            # Write to file
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            logger.info(f"State saved for {image_path} to {state_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state for {image_path}: {e}")
            return False
    
    def load_state(self, image_path: str, display_name: Optional[str] = None, folder_type: str = "saved_states") -> Optional[Dict[str, Any]]:
        """
        Load the saved state for an image
        
        Args:
            image_path: Path to the image/idx file
            display_name: Optional display name to use as folder name (e.g., "P11")
            folder_type: Either "live_tracking" or "saved_states" (default: "saved_states")
            
        Returns:
            Dictionary containing state information, or None if no state exists
        """
        try:
            state_file = self._get_state_file(image_path, display_name=display_name, folder_type=folder_type)
            
            if not state_file.exists():
                logger.info(f"No saved state found for {image_path}")
                return None
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            logger.info(f"State loaded for {image_path} from {state_file}")
            return state_data
            
        except Exception as e:
            logger.error(f"Failed to load state for {image_path}: {e}")
            return None
    
    def has_saved_state(self, image_path: str, display_name: Optional[str] = None, folder_type: str = "saved_states") -> bool:
        """
        Check if a saved state exists for an image
        
        Args:
            image_path: Path to the image/idx file
            display_name: Optional display name to use as folder name (e.g., "P11")
            folder_type: Either "live_tracking" or "saved_states" (default: "saved_states")
            
        Returns:
            True if saved state exists
        """
        state_file = self._get_state_file(image_path, display_name=display_name, folder_type=folder_type)
        return state_file.exists()
    
    def delete_state(self, image_path: str, display_name: Optional[str] = None, folder_type: str = "saved_states") -> bool:
        """
        Delete the saved state for an image
        
        Args:
            image_path: Path to the image/idx file
            display_name: Optional display name to use as folder name (e.g., "P11")
            folder_type: Either "live_tracking" or "saved_states" (default: "saved_states")
            
        Returns:
            True if deletion was successful
        """
        try:
            state_file = self._get_state_file(image_path, display_name=display_name, folder_type=folder_type)
            
            if state_file.exists():
                state_file.unlink()
                logger.info(f"State deleted for {image_path}")
                return True
            else:
                logger.info(f"No state file to delete for {image_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete state for {image_path}: {e}")
            return False
    
    def cleanup_live_tracking_except_last(self, image_path: str, display_name: Optional[str] = None) -> int:
        """
        Delete all live tracking JSON files except the most recent one
        
        Args:
            image_path: Path to the image/idx file
            display_name: Optional display name to use as folder name (e.g., "P11")
            
        Returns:
            Number of files deleted
        """
        try:
            # Use display_name if provided, otherwise fall back to filename stem
            if display_name:
                folder_name = display_name
            else:
                folder_name = Path(image_path).stem
            
            # Get the live_tracking folder
            live_tracking_folder = self.state_dir / folder_name / "live_tracking"
            
            if not live_tracking_folder.exists():
                logger.info(f"No live tracking folder found for {folder_name}")
                return 0
            
            # Get all JSON files sorted by name (which corresponds to timestep)
            json_files = sorted(live_tracking_folder.glob("*.json"))
            
            if len(json_files) <= 1:
                logger.info(f"Only {len(json_files)} live tracking file(s) found, nothing to delete")
                return 0
            
            # Delete all except the last one
            files_to_delete = json_files[:-1]  # All except the last
            deleted_count = 0
            
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")
            
            logger.info(f"Deleted {deleted_count} live tracking files for {folder_name}, kept the last one")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup live tracking for {image_path}: {e}")
            return 0
    
    def get_state_info(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about the saved state (without loading full state)
        
        Args:
            image_path: Path to the image/idx file
            
        Returns:
            Dictionary with state metadata (timestamp, etc.)
        """
        state_data = self.load_state(image_path)
        if state_data:
            return {
                "timestamp": state_data.get("timestamp"),
                "has_drawings": bool(state_data.get("drawings", {}).get("xs")),
                "viewport": state_data.get("viewport"),
                "zoom_level": state_data.get("zoom_level")
            }
        return None
    
    def list_all_states(self) -> List[Dict[str, Any]]:
        """
        List all saved states
        
        Returns:
            List of dictionaries with state information
        """
        states = []
        for image_folder in self.state_dir.iterdir():
            if image_folder.is_dir():
                for state_file in image_folder.glob("*.json"):
                    try:
                        with open(state_file, 'r') as f:
                            state_data = json.load(f)
                            states.append({
                                "file": state_file.name,
                                "image_name": image_folder.name,
                                "image_path": state_data.get("image_path"),
                                "timestamp": state_data.get("timestamp"),
                                "timestep": state_data.get("timestep"),
                                "has_drawings": bool(state_data.get("drawings", {}).get("xs"))
                            })
                    except Exception as e:
                        logger.error(f"Failed to read state file {state_file}: {e}")
        return states
    
    def get_saved_timesteps(self, image_path: str, display_name: Optional[str] = None, folder_type: str = "saved_states") -> List[int]:
        """
        Get all saved timestep numbers for an image
        
        Args:
            image_path: Path to the image/idx file
            display_name: Optional display name to use as folder name (e.g., "P11")
            folder_type: Either "live_tracking" or "saved_states" (default: "saved_states")
            
        Returns:
            List of timestep numbers that have saved states (including 00000.json)
        """
        if display_name:
            folder_name = display_name
        else:
            folder_name = Path(image_path).stem
        
        image_folder = self.state_dir / folder_name / folder_type
        
        if not image_folder.exists():
            return []
        
        timesteps = []
        for state_file in image_folder.glob("*.json"):
            # Include ALL timestep files now (including 00000.json)
            try:
                # Extract timestep number from filename
                timestep = int(state_file.stem)
                timesteps.append(timestep)
            except ValueError:
                pass
        
        return sorted(timesteps)
    
    def save_timestep_state(self, image_path: str, timestep: int, state_data: Dict[str, Any], display_name: Optional[str] = None, folder_type: str = "saved_states") -> bool:
        """
        Save state for a specific timestep (triggered by 'S' key press)
        
        Args:
            image_path: Path to the image/idx file
            timestep: Current timestep number
            state_data: Dictionary containing state information
            display_name: Optional display name to use as folder name (e.g., "P11")
            folder_type: Either "live_tracking" or "saved_states" (default: "saved_states")
            
        Returns:
            True if save was successful
        """
        return self.save_state(image_path, state_data, timestep=timestep, display_name=display_name, folder_type=folder_type)
    
    def save_live_tracking_state(self, image_path: str, state_data: Dict[str, Any], display_name: Optional[str] = None, max_files: int = 5000) -> bool:
        """
        Save state for live tracking with automatic cleanup of old files
        Maintains a rolling buffer of max_files most recent states
        
        Args:
            image_path: Path to the image/idx file
            state_data: Dictionary containing state information
            display_name: Optional display name to use as folder name (e.g., "P11")
            max_files: Maximum number of files to keep (default: 5000)
            
        Returns:
            True if save was successful
        """
        try:
            # Get all existing live tracking states
            existing_states = self.get_saved_timesteps(image_path, display_name=display_name, folder_type="live_tracking")
            
            # Find the next timestep number (excluding 00000 which is current state)
            existing_states_filtered = [s for s in existing_states if s > 0]
            if existing_states_filtered:
                next_timestep = max(existing_states_filtered) + 1
            else:
                next_timestep = 1
            
            # Save the new state
            success = self.save_timestep_state(
                image_path,
                next_timestep,
                state_data,
                display_name=display_name,
                folder_type="live_tracking"
            )
            
            if success:
                # Clean up old files if we exceed max_files
                existing_states_filtered = [s for s in self.get_saved_timesteps(image_path, display_name=display_name, folder_type="live_tracking") if s > 0]
                if len(existing_states_filtered) > max_files:
                    # Sort and delete oldest files
                    sorted_states = sorted(existing_states_filtered)
                    files_to_delete = sorted_states[:len(sorted_states) - max_files]
                    
                    if display_name:
                        folder_name = display_name
                    else:
                        folder_name = Path(image_path).stem
                    
                    live_folder = self.state_dir / folder_name / "live_tracking"
                    
                    for timestep in files_to_delete:
                        old_file = live_folder / f"{timestep:05d}.json"
                        if old_file.exists():
                            old_file.unlink()
                            logger.debug(f"Deleted old live tracking file: {old_file}")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to save live tracking state: {e}")
            return False


class SliceStateTracker:
    """
    Tracks state changes for a Slice object and periodically saves them
    """
    
    def __init__(self, slice_obj, image_path: str, state_manager: StateManager, 
                 auto_save_interval: float = 2.0, display_name: Optional[str] = None):
        """
        Initialize the state tracker
        
        Args:
            slice_obj: The Slice object to track
            image_path: Path to the image being displayed
            state_manager: StateManager instance
            auto_save_interval: Seconds between auto-saves
            display_name: Optional display name for the image (e.g., "P11")
        """
        self.slice = slice_obj
        self.image_path = image_path
        self.state_manager = state_manager
        self.auto_save_interval = auto_save_interval
        self.display_name = display_name
        self.last_save_time = 0
        self.last_viewport = None
        self.last_drawings = None
        
    def capture_current_state(self) -> Dict[str, Any]:
        """
        Capture the current state of the slice
        
        Returns:
            Dictionary with current state
        """
        state = {}
        
        # Capture viewport
        try:
            viewport = self.slice.canvas.getViewport()
            state["viewport"] = viewport
        except Exception as e:
            logger.warning(f"Failed to capture viewport: {e}")
            state["viewport"] = None
        
        # Capture drawings
        try:
            if hasattr(self.slice.canvas, 'drawsource') and self.slice.canvas.drawsource:
                drawings = {
                    "xs": list(self.slice.canvas.drawsource.data.get("xs", [])),
                    "ys": list(self.slice.canvas.drawsource.data.get("ys", []))
                }
                state["drawings"] = drawings
            else:
                state["drawings"] = {"xs": [], "ys": []}
        except Exception as e:
            logger.warning(f"Failed to capture drawings: {e}")
            state["drawings"] = {"xs": [], "ys": []}
        
        # Calculate zoom level from viewport and figure dimensions
        try:
            fig = self.slice.canvas.fig
            
            # Get viewport width in screen pixels
            viewport_width = None
            for attr in ("inner_width", "plot_width"):
                try:
                    v = getattr(fig, attr)
                    if isinstance(v, (int, float)) and v > 0:
                        viewport_width = v
                        break
                except:
                    pass
            
            # Calculate zoom level as percentage
            if viewport_width and viewport_width > 0:
                img_width = abs(fig.x_range.end - fig.x_range.start)
                if img_width > 0:
                    state["zoom_level"] = (viewport_width / img_width) * 100.0
                    logger.info(f"StateManager: calc_zoom viewport_width={viewport_width}, "
                              f"img_width={img_width:.2f}, zoom_level={state['zoom_level']:.2f}%")
                else:
                    state["zoom_level"] = 100.0
                    logger.warning(f"StateManager: img_width is 0, using default zoom_level=100.0%")
            else:
                state["zoom_level"] = 100.0
                logger.warning(f"StateManager: viewport_width invalid ({viewport_width}), using default zoom_level=100.0%")
                
        except Exception as e:
            logger.warning(f"Failed to calculate zoom level: {e}")
            state["zoom_level"] = 100.0
        
        return state
    
    def should_save(self) -> bool:
        """
        Check if enough time has passed to trigger auto-save
        
        Returns:
            True if should save now
        """
        current_time = time.time()
        return (current_time - self.last_save_time) >= self.auto_save_interval
    
    def save_if_changed(self) -> bool:
        """
        Save state if it has changed and auto-save interval has passed
        
        Returns:
            True if state was saved
        """
        if not self.should_save():
            return False
        
        current_state = self.capture_current_state()
        
        # Check if state has changed
        viewport_changed = current_state["viewport"] != self.last_viewport
        drawings_changed = current_state["drawings"] != self.last_drawings
        
        if viewport_changed or drawings_changed:
            logger.info(f"StateManager: Auto-saving state (viewport_changed={viewport_changed}, "
                       f"drawings_changed={drawings_changed}, zoom={current_state.get('zoom_level', 0):.2f}%)")
            success = self.state_manager.save_state(self.image_path, current_state, display_name=self.display_name)
            if success:
                self.last_save_time = time.time()
                self.last_viewport = current_state["viewport"]
                self.last_drawings = current_state["drawings"]
                return True
        
        return False
    
    def force_save(self) -> bool:
        """
        Force save the current state regardless of interval
        
        Returns:
            True if save was successful
        """
        current_state = self.capture_current_state()
        logger.info(f"StateManager: Force saving state (zoom={current_state.get('zoom_level', 0):.2f}%)")
        success = self.state_manager.save_state(self.image_path, current_state, display_name=self.display_name)
        if success:
            self.last_save_time = time.time()
            self.last_viewport = current_state["viewport"]
            self.last_drawings = current_state["drawings"]
            logger.info(f"StateManager: Force save successful")
        return success
    
    def restore_state(self, state_data: Dict[str, Any]) -> bool:
        """
        Restore a slice to a saved state
        
        Args:
            state_data: State dictionary from StateManager
            
        Returns:
            True if restoration was successful
        """
        try:
            logger.info(f"StateManager: Starting state restoration")
            
            # Get the figure - should already have document context from caller
            fig = self.slice.canvas.fig
            
            # Restore drawings first
            if state_data.get("drawings"):
                drawings = state_data["drawings"]
                if hasattr(self.slice.canvas, 'drawsource') and self.slice.canvas.drawsource:
                    self.slice.canvas.drawsource.data = {
                        "xs": drawings.get("xs", []),
                        "ys": drawings.get("ys", [])
                    }
                    num_strokes = len(drawings.get('xs', []))
                    logger.info(f"StateManager: Restored {num_strokes} drawing strokes")
            
            # Restore viewport
            if state_data.get("viewport"):
                viewport = state_data["viewport"]
                
                # Set the viewport directly on the figure ranges
                x, y, w, h = viewport
                fig.x_range.start = x
                fig.x_range.end = x + w
                fig.y_range.start = y
                fig.y_range.end = y + h
                
                zoom_level = state_data.get("zoom_level", "N/A")
                logger.info(f"StateManager: Set viewport: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, zoom: {zoom_level}%")
                
                # Trigger a refresh with the restored viewport
                if hasattr(self.slice, 'refresh'):
                    logger.info(f"StateManager: Triggering slice.refresh()")
                    self.slice.refresh("StateRestored")
            
            self.last_viewport = state_data.get("viewport")
            self.last_drawings = state_data.get("drawings")
            
            logger.info(f"StateManager: State restoration complete")
            return True
            
        except Exception as e:
            logger.error(f"StateManager: Failed to restore state: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
            import traceback
            logger.error(traceback.format_exc())
            return False
