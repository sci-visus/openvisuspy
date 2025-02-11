from bokeh.models import CustomJS
from threading import Timer
import math


class SliceSynchronizer:
    def __init__(self, slice1, slice2, scale_factor=4):
        self.slice1 = slice1
        self.slice2 = slice2
        self.scale_factor = scale_factor
        self.full_width = None
        self.debounce_timer = None  # Timer to debounce refresh calls
        self.debounce_delay = 0.1  # Delay in seconds for debounce
        self.update_callbacks = [] # Callback list for external

        # Store zoom levels
        self.zoom_level_1 = 1.0 #intial value
        self.zoom_level_2 = 1.0

        # Link ranges with JavaScript callbacks
        self.link_ranges()

    def link_ranges(self):
        """Link the x_range and y_range of slice1 and slice2 using JavaScript callbacks."""
        fig1, fig2 = self.slice1.canvas.fig, self.slice2.canvas.fig

        # JavaScript for synchronizing slice2 based on slice1
        js_code_slice1_to_slice2 = """
            fig2.x_range.start = fig1.x_range.start * scale_factor;
            fig2.x_range.end = fig1.x_range.end * scale_factor;
            fig2.y_range.start = fig1.y_range.start * scale_factor;
            fig2.y_range.end = fig1.y_range.end * scale_factor;
        """

        # JavaScript for synchronizing slice1 based on slice2
        js_code_slice2_to_slice1 = """
            fig1.x_range.start = fig2.x_range.start / scale_factor;
            fig1.x_range.end = fig2.x_range.end / scale_factor;
            fig1.y_range.start = fig2.y_range.start / scale_factor;
            fig1.y_range.end = fig2.y_range.end / scale_factor;
        """

        # Create JavaScript callbacks
        callback_slice1_to_slice2 = CustomJS(
            args=dict(fig1=fig1, fig2=fig2, scale_factor=self.scale_factor),
            code=js_code_slice1_to_slice2
        )
        callback_slice2_to_slice1 = CustomJS(
            args=dict(fig1=fig1, fig2=fig2, scale_factor=self.scale_factor),
            code=js_code_slice2_to_slice1
        )

        # Attach JavaScript callbacks for x_range and y_range synchronization
        fig1.x_range.js_on_change('start', callback_slice1_to_slice2)
        fig1.x_range.js_on_change('end', callback_slice1_to_slice2)
        fig1.y_range.js_on_change('start', callback_slice1_to_slice2)
        fig1.y_range.js_on_change('end', callback_slice1_to_slice2)

        fig2.x_range.js_on_change('start', callback_slice2_to_slice1)
        fig2.x_range.js_on_change('end', callback_slice2_to_slice1)
        fig2.y_range.js_on_change('start', callback_slice2_to_slice1)
        fig2.y_range.js_on_change('end', callback_slice2_to_slice1)

        # Attach Python-side refresh using a timer for debouncing
        self.attach_refresh(fig1, fig2)

    def attach_refresh(self, fig1, fig2):
        """Attach Python-side refresh with debouncing."""
        def trigger_refresh():
            """Trigger refresh for both slices."""
            self.slice1.refresh("DebouncedSyncFromSlice2")
            self.slice2.refresh("DebouncedSyncFromSlice1")

            self.zoom_level_1= self.update_zoom_level(fig1)
            self.zoom_level_2= self.update_zoom_level(fig2)

            self.notify_subscribers()

        def debounce_refresh(attr, old, new):
            """Debounce refresh calls."""
            if self.debounce_timer:
                self.debounce_timer.cancel()

            # Schedule the refresh after the debounce delay
            self.debounce_timer = Timer(self.debounce_delay, trigger_refresh)
            self.debounce_timer.start()

        # Attach Python refresh debounce to all range changes
        fig1.x_range.on_change('start', debounce_refresh)
        fig1.x_range.on_change('end', debounce_refresh)
        fig1.y_range.on_change('start', debounce_refresh)
        fig1.y_range.on_change('end', debounce_refresh)

        fig2.x_range.on_change('start', debounce_refresh)
        fig2.x_range.on_change('end', debounce_refresh)
        fig2.y_range.on_change('start', debounce_refresh)
        fig2.y_range.on_change('end', debounce_refresh)


    #Zoom level Calculation
    def update_zoom_level(self, fig):
        """
        Calculate and update the zoom level dynamically.
        """
        # Get current viewport size
        image_width = fig.x_range.end - fig.x_range.start

        # Prevent division by zero
        image_width = max(1, image_width)

        viewport_width = fig.inner_width

        zoomLevel = (viewport_width / math.ceil(image_width)) * 100

        print(f"zoom: viewport width={viewport_width}, image width={math.ceil(image_width)}, zoomLevel={zoomLevel}%")


        return (zoomLevel) # Return the zoom level

   
    def register_callback(self, callback):
        """
        Register a callback function to be notified when zoom levels are updated.
        The callback function should accept two arguments: (zoom_level_fig1, zoom_level_fig2).
        """
        self.update_callbacks.append(callback)

    def notify_subscribers(self):
        """
        Notify all registered subscribers with the updated zoom levels.
        """
        for callback in self.update_callbacks:
            callback(self.zoom_level_1, self.zoom_level_2)