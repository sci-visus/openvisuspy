from bokeh.models import BoxAnnotation
import panel as pn
import logging
import uuid

logger = logging.getLogger(__name__)

class AnnotationManager:
    """Manages box annotations on a Canvas"""
    
    def __init__(self, canvas):
        """Initialize with Canvas instance"""
        self.canvas = canvas
        self.annotations = {}
        
        # Toggle button for annotation mode
        self.annotation_toggle = pn.widgets.Toggle(
            name='Annotate',
            value=False,
            button_type='primary',
            width=100
        )
        
        # State management
        self.drawing = False
        self.start_coords = None
        self.current_box = None
        
        # Store previous tool states
        self._prev_drag = None
        self._prev_scroll = None
        
        # Setup callbacks
        self._setup_callbacks()
        
    def _setup_callbacks(self):
        """Setup event callbacks"""
        # Toggle mode handling
        self.annotation_toggle.param.watch(self._toggle_mode, 'value')
        
        # Add tap event handler to figure
        self.canvas.on_event('tap', self._handle_tap)
        
    def _toggle_mode(self, event):
        """Handle annotation mode toggle"""
        if event.new:  # Entering annotation mode
            # Store current tool states
            self._prev_drag = self.canvas.fig.toolbar.active_drag
            self._prev_scroll = self.canvas.fig.toolbar.active_scroll
            
            # Disable other tools
            self.canvas.fig.toolbar.active_drag = None
            self.canvas.fig.toolbar.active_scroll = None
        else:  # Exiting annotation mode
            # Restore previous tool states
            self.canvas.fig.toolbar.active_drag = self._prev_drag
            self.canvas.fig.toolbar.active_scroll = self._prev_scroll
            
            # Cancel any in-progress drawing
            if self.drawing:
                self._cancel_drawing()
    
    def _cancel_drawing(self):
        """Cancel current drawing operation"""
        if self.current_box and self.current_box in self.canvas.fig.renderers:
            self.canvas.fig.renderers.remove(self.current_box)
        self.current_box = None
        self.start_coords = None
        self.drawing = False
        
    def _handle_tap(self, event):
        """Handle tap events for box drawing"""
        if not self.annotation_toggle.value:
            return
            
        if not self.drawing:
            # Start new box
            self.drawing = True
            self.start_coords = (event.x, event.y)
            
            self.current_box = BoxAnnotation(
                left=event.x,
                right=event.x,
                bottom=event.y,
                top=event.y,
                fill_alpha=0.2,
                fill_color='blue',
                line_color='blue'
            )
            self.canvas.fig.add_layout(self.current_box)
            
        else:
            # Complete the box
            self.drawing = False
            if self.current_box and self.start_coords:
                # Set final coordinates
                self.current_box.left = min(self.start_coords[0], event.x)
                self.current_box.right = max(self.start_coords[0], event.x)
                self.current_box.bottom = min(self.start_coords[1], event.y)
                self.current_box.top = max(self.start_coords[1], event.y)
                
                # Store with unique ID
                annotation_id = str(uuid.uuid4())
                self.annotations[annotation_id] = self.current_box
                
                logger.info(f"Created annotation {annotation_id}")
            
            self.current_box = None
            self.start_coords = None
    
    def clear_annotations(self):
        """Remove all annotations from plot"""
        for box in list(self.annotations.values()):
            if box in self.canvas.fig.renderers:
                self.canvas.fig.renderers.remove(box)
        self.annotations.clear()