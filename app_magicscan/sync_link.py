
from bokeh.models import CustomJS, Div
from threading import Timer
import math
import numpy as np

class SliceSynchronizer:
    def __init__(self, slice1, slice2, scale_factor=4):
        self.slice1 = slice1
        self.slice2 = slice2
        self.scale_factor = scale_factor
        self.full_width = None
        self.debounce_timer = None  # Timer to debounce refresh calls
        self.debounce_delay = 0.1  # Delay in seconds for debounce
        
        # Callback list for external subscribers
        self.update_callbacks = []


        # Store zoom levels
        self.zoom_level_1 = 1.0
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
        """Attach Python-side refresh with trigger_refreshdebouncing."""
        def trigger_refresh():
            """Trigger refresh for both slices and update zoom level."""
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




#######################################################

    def update_zoom_level(self, fig):
        """
        Calculate and update the zoom level dynamically.
        """
        # Get current viewport size
        image_width = fig.x_range.end - fig.x_range.start

        print(f"Current1: {fig.x_range.end}% {fig.x_range.start} {image_width}")

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

##################

class MultiSliceSynchronizer:
    def __init__(self, slices, scale_factors):
        self.slices = slices
        self.scale_factors = scale_factors
        self.debounce_timer = None
        self.debounce_delay = 0.1
        self.update_callbacks = []
        self.link_ranges()

    def link_ranges(self):
        figs = [slice.canvas.fig for slice in self.slices]

        for idx, fig_source in enumerate(figs):
            args = {'source_fig': fig_source}
            for target_idx, target_fig in enumerate(figs):
                if idx != target_idx:
                    args[f'target_fig{target_idx}'] = target_fig
                    args[f'scale_factor_{idx}_{target_idx}'] = (
                        self.scale_factors[target_idx] / self.scale_factors[idx]
                    )

            js_code = """
                const sx_start = source_fig.x_range.start;
                const sx_end = source_fig.x_range.end;
                const sy_start = source_fig.y_range.start;
                const sy_end = source_fig.y_range.end;
            """ + "\n".join([
                f"""
                target_fig{target_idx}.x_range.start = sx_start * scale_factor_{idx}_{target_idx};
                target_fig{target_idx}.x_range.end = sx_end * scale_factor_{idx}_{target_idx};
                target_fig{target_idx}.y_range.start = sy_start * scale_factor_{idx}_{target_idx};
                target_fig{target_idx}.y_range.end = sy_end * scale_factor_{idx}_{target_idx};
                """ for target_idx in range(len(figs)) if target_idx != idx
            ])

            callback_js = CustomJS(args=args, code=js_code)

            for r in ('start', 'end'):
                fig_source.x_range.js_on_change(r, callback_js)
                fig_source.y_range.js_on_change(r, callback_js)

            fig_source.x_range.on_change('start', self.python_sync)
            fig_source.x_range.on_change('end', self.python_sync)
            fig_source.y_range.on_change('start', self.python_sync)
            fig_source.y_range.on_change('end', self.python_sync)


    def python_sync(self, attr, old, new):
        if self.debounce_timer:
            self.debounce_timer.cancel()
        self.debounce_timer = Timer(self.debounce_delay, self.trigger_refresh)
        self.debounce_timer.start()

    def trigger_refresh(self):
        for slc in self.slices:
            slc.refresh("Multi-Slice Sync Refresh with Scale Factor")
        zooms = [self.calc_zoom(slc.canvas.fig) for slc in self.slices]
        self.notify_subscribers(*zooms)

    def calc_zoom2(self, fig):
        img_width = fig.x_range.end - fig.x_range.start
        viewport_width = fig.inner_width
        zoom_level = (viewport_width / max(1, img_width)) * 100
        return zoom_level
    
    def calc_zoom(self, fig):
        img_width = fig.x_range.end - fig.x_range.start
        viewport_width = fig.inner_width if fig.inner_width is not None else fig.plot_width
        if viewport_width is None or viewport_width == 0:
            return 100.0  # safe default if still not rendered
        zoom_level = (viewport_width / max(1, img_width)) * 100
        return zoom_level


    def register_callback(self, callback):
        self.update_callbacks.append(callback)

    def notify_subscribers(self, *zooms):
        for cb in self.update_callbacks:
            cb(*zooms)
