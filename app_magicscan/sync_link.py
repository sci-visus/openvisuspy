
from bokeh.models import CustomJS, Div
from threading import Timer
import math
import numpy as np
from bokeh.core.property.descriptors import UnsetValueError  # add this at top (once)




class MultiSliceSynchronizer:
    def __init__(self, slices, scale_factors):
        self.slices = slices
        self.scale_factors = scale_factors
        self.debounce_timer = None
        self.debounce_delay = 0.1
        self.update_callbacks = []
        self.last_bb_zooms = [None] * len(self.slices)  # optional: track last bbox zoom
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

    def trigger_refresh3(self):
        for slc in self.slices:
            slc.refresh("Multi-Slice Sync Refresh with Scale Factor")
        zooms = [self.calc_zoom3(slc.canvas.fig) for slc in self.slices]
        #zoom_bbs = [self.calc_zoom2(slc.canvas.fig) for slc in self.slices] # Boundary box zoom levels
        self.notify_subscribers(*zooms)

    def trigger_refresh(self):
        for slc in self.slices:
            slc.refresh("Multi-Slice Sync Refresh with Scale Factor")

        zooms    = []
        bb_zooms = []
        for slc in self.slices:
            z, zbb = self.calc_zoom(slc.canvas.fig)   # <— tuple
            zooms.append(z)
            bb_zooms.append(zbb)

        self.last_bb_zooms = bb_zooms                 # <— stash BB zooms
        self.notify_subscribers(*zooms) 


    
    def calc_zoom3(self, fig):
        img_width = fig.x_range.end - fig.x_range.start
        bb_width= 1024
        viewport_width = fig.inner_width if fig.inner_width is not None else fig.plot_width
        if viewport_width is None or viewport_width == 0:
            self.last_zoom_level_bb = 100.0
            return 100.0  # safe default if still not rendered
        zoom_level = (viewport_width / max(1, img_width)) * 100
        zoom_level_bb= (viewport_width / max(1, bb_width)) * 100
        print(f"calc_zoom: viewport_width={viewport_width}, img_width={img_width}, zoom_level={zoom_level}%, zoom_level_bb={zoom_level_bb}%")
        return zoom_level 

    def calc_zoom2(self, fig):
        bb_width= 1024
        viewport_width = fig.inner_width if fig.inner_width is not None else fig.plot_width
        if viewport_width is None or viewport_width == 0:
            self.last_zoom_level_bb = 100.0
            return 100.0  # safe default if still not rendered
        zoom_level_bb= (viewport_width / max(1, bb_width)) * 100
        print(f"calc_zoom: viewport_width={viewport_width}, img_width={img_width}, zoom_level={zoom_level}%, zoom_level_bb={zoom_level_bb}%")
        return zoom_level_bb

    def calc_zoom(self, fig):
        # robust viewport width (avoid UnsetValueError before layout)
        def _viewport_width(f):
            for attr in ("inner_width", "plot_width"):
                try:
                    v = getattr(f, attr)
                except Exception:
                    v = None
                if isinstance(v, (int, float)) and v > 0:
                    return v
            return 0

        img_width = (fig.x_range.end - fig.x_range.start)
        bb_width  = 1024
        viewport_width = _viewport_width(fig)

        if viewport_width <= 0:
            zoom_level    = 100.0
            zoom_level_bb = 100.0
        else:
            zoom_level    = (viewport_width / max(1, img_width)) * 100.0
            zoom_level_bb = (viewport_width / max(1, bb_width))  * 100.0

        # keep the helpful print
        print(f"calc_zoom: viewport_width={viewport_width}, img_width={img_width}, "
              f"zoom_level={zoom_level}%, zoom_level_bb={zoom_level_bb}%")

        return zoom_level, zoom_level_bb 



    def register_callback(self, callback):
        self.update_callbacks.append(callback)

    def notify_subscribers(self, *zooms):
        for cb in self.update_callbacks:
            cb(*zooms)
