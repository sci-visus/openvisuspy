
import os,sys,logging
import bokeh

from openvisuspy import Slice, Slices,cbool

VISUS_UI=os.environ.get("VISUS_UI","bokeh")
print("VISUS_UI",VISUS_UI)

if VISUS_UI=="panel":
	import panel as pn
	from panel.template import DarkTheme
	pn.extension(sizing_mode='stretch_both')

# ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def MyApp(doc=None):

	if False:

		palette,palette_range="Greys256",(0,255)
		urls=["http://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"]
		view=Slice(doc=doc, show_options=["palette","timestep","field","direction","offset","num_refinements"])
		view.setDataset(urls[0])
		view.setDirection(2)
		view.setNumberOfRefinements(3)
		view.setPalette(palette)
		view.setPaletteRange(palette_range)
		view.setTimestep(view.getTimestep())
		view.setField(view.getField())

	else:

		urls=[f"https://maritime.sealstorage.io/api/v0/s3/utah/nasa/dyamond/idx_arco/face{zone}/u_face_{zone}_depth_52_time_0_10269.idx?cached=1" for zone in range(6)]

		view=Slices(doc=doc, num_views=3,
			show_options=["num_views","palette","dataset","timestep","timestep-delta","field","viewdep","quality","num_refinements","play-button", "play-sec"],
			slice_show_options=["direction","offset","viewdep","status_bar"])
	
		view.setDatasets([(url,str(I)) for I,url in enumerate(urls)],"Zone")
		view.setDataset(urls[0])
		view.setQuality(-3)
		view.setNumberOfRefinements(3)
		view.setPalette("Turbo256") 
		view.setPaletteRange((-30,60))
		view.setTimestepDelta(10)
		view.setField(None)
		view.setLogicToPixel([(0.0,1.0), (0.0,1.0), (0.0,10.0)])
		view.setViewDependent(False) # important, there is aproblem in viewdep
		view.setDirections([('0','Long'),('1','Lat'),('2','Depth')])


	if VISUS_UI=="panel":
		main_layout=pn.pane.Bokeh(view.layout)
		bTemplate=True
		if bTemplate:
			from panel.template import DarkTheme
			app = pn.template.MaterialTemplate(
				title='Openvisus-Panel',
				logo ="https://www.sci.utah.edu/~pascucci/public/NSDF-smaller.PNG",
				site_url ="https://nationalsciencedatafabric.org/",
				header_background="#303050",
				theme=DarkTheme) 
			app.main.append(main_layout) 
		else:
			app=main_layout
		app.servable()

	else:
		if not doc: doc=bokeh.io.curdoc()
		doc.add_root(view.layout)

 
# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):
	logger=logging.getLogger("openvisuspy")
	logger.setLevel(logging.INFO)
	MyApp()

	
		 

