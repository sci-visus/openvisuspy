
import os,sys,logging

os.environ["BOKEH_ALLOW_WS_ORIGIN"]="*"
os.environ["BOKEH_LOG_LEVEL"]="debug" 
import bokeh

from openvisus_py import Slice, Slices, SetupLogger

# ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def MyApp(doc=bokeh.io.curdoc()):
	
	os.environ["VISUS_NETSERVICE_VERBOSE"]="0"
	os.environ["VISUS_CPP_VERBOSE"]="0"
	os.environ["VISUS_DASHBOARDS_VERBOSE"]="0" 
 
	if True:
		url="http://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1"
		view=Slice(doc=doc, show_options=["palette","timestep","field","direction","offset","num_refinements"])
		view.setDataset(url)
		view.setDirection(2)
		view.setNumberOfRefinements(3)
		view.setPalette("Greys256")
		view.setPaletteRange((0,255))
		view.setTimestep(view.getTimestep())
		view.setField(view.getField())         
		doc.add_root(view.layout)     
		return
	else:

		# profile=sealstorage
		os.environ["AWS_ACCESS_KEY_ID"]="any"
		os.environ["AWS_SECRET_ACCESS_KEY"]="any"
		os.environ["AWS_ENDPOINT_URL"]="https://maritime.sealstorage.io/api/v0/s3"

		urls=[f"https://maritime.sealstorage.io/api/v0/s3/utah/nasa/dyamond/idx_arco/face{zone}/u_face_{zone}_depth_52_time_0_10269.idx?cached=1" for zone in range(6)]
		palette,palette_range="Turbo256",(-30,60)
		field=None
		logic_to_pixel=[(0.0,1.0), (0.0,1.0), (0.0,10.0)]
		
		# urls,field,palette,palette_range=["https://maritime.sealstorage.io/api/v0/s3/utah/nasa/dyamond/mit_output/llc2160_arco/visus.idx?cached=1"],None,"Turbo256",(-1.3,1.7)

		# urls,palette,palette_range=["http://atlantis.sci.utah.edu/mod_visus?dataset=cmip6_cm2&cached=idx"],"Turbo256",(-1.3,1.7),"ssp585_tasmax"
		# logic_to_pixel=[(0.0,1.0), (0.0,1.0), (0.0,10.0)]

		slices=Slices(
			doc=doc,
			num_views=3,
			show_options=["num_views","palette","dataset","timestep","timestep-delta","field","viewdep","quality","num_refinements","play-button", "play-sec"],
			#slice_show_options=["num_views","palette","dataset","timestep","timestep-delta","field","viewdep","quality","num_refinements","play-button", "play-sec"],
			slice_show_options=["direction","offset","viewdep","status_bar"],
		)
	
		slices.setDatasets([(url,str(I)) for I,url in enumerate(urls)],"Zone")
		slices.setDataset(urls[0])
		slices.setQuality(-3)
		slices.setNumberOfRefinements(3)
		slices.setPalette(palette) 
		slices.setPaletteRange(palette_range)
		slices.setTimestepDelta(10)
		slices.setField(field)
		slices.setLogicToPixel(logic_to_pixel)
		slices.setDirections([('0','Long'),('1','Lat'),('2','Depth')])
	
		doc.add_root(slices.layout)
 
# //////////////////////////////////////////////////////////////////////////////////////
if __name__.startswith('bokeh'):
	logger=logging.getLogger("openvisus_py")
	logger.setLevel(logging.INFO)
	MyApp()

	

		 