import bokeh.layouts
import bokeh.models
import bokeh.plotting
import time

print(time.time(),"New user session")
button = bokeh.models.Button(label="Is Bokeh working?")
def OnClick(evt=None): 
	button.label="YES!"

button.on_click(OnClick)

print(bokeh.plotting.curdoc().session_context.request)

bokeh.plotting.curdoc().add_root(bokeh.layouts.column(button))