import os,sys,logging,base64,json,types
import requests


# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):

	from openvisuspy import SetupLogger,IsPanelServe,GetBackend,Slice, Slices,cbool
	from openvisuspy.probes import ProbeTool
	
	logger=SetupLogger()
	logger.info(f"GetBackend()={GetBackend()}")

	probe=True
	cls=ProbeTool if probe else Slice

	if False:
		view=cls(show_options=[
			"datasets", "direction", "offset", "palette",  "field", "quality", "num_refinements", "colormapper_type","palette_range_mode","palette_range_vmin","palette_range_vmax"
		])
	else:
		view=Slices(
			show_options=["datasets", "num_views", "palette", 
								 #"field", 
								 "quality", "num_refinements", "colormapper_type","show_metadata"],  
			slice_show_options=["datasets", "direction", "offset", "colormapper_type", "palette_range_mode","palette_range_vmin","palette_range_vmax"],
			cls=cls
		)

	view.setDataset(sys.argv[1])

	if  IsPanelServe():
		import panel as pn
		main_layout=view.getBokehLayout(doc=None,is_panel=True)
		use_template=True
		if use_template:
			template = pn.template.MaterialTemplate(title='NSDF Dashboard')
			template.main.append(main_layout)
			template.servable()
		else:
			main_layout.servable()		
	else:
		import bokeh
		doc=bokeh.io.curdoc()
		doc.theme = 'light_minimal'
		main_layout=view.getBokehLayout(doc=doc,is_panel=False)
		doc.add_root(main_layout)
	

