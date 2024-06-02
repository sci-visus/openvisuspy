import openvisuspy as ovy
import panel as pn
import numpy as np
from bokeh.plotting import figure
from bokeh.models import LinearColorMapper
import bokeh.models
import logging

logger = logging.getLogger(__name__)
	
# ////////////////////////////////////////////////////////////////////////
def apply_min_cmap(self):
	self.range_min.value=self.vmin
	self.range_mode.value="user"

	logger.info('new min range applied')
	ShowInfoNotification('New min range applied successfully')

# ////////////////////////////////////////////////////////////////////////
def add_range(self):
	if self.range_max.value<self.vmax:
		self.range_max.value=self.vmax

	if self.range_min.value>self.vmin:
		self.range_min.value=self.vmin
	
	logger.info('Range added successfully')
	ShowInfoNotification('Range Added successfully')
		
# ////////////////////////////////////////////////////////////////////////
def apply_max_cmap(self):
	self.range_max.value=self.vmax
	self.range_mode.value="user"

	logger.info('new min range applied')
	ShowInfoNotification('New max range applied successfully')

# ////////////////////////////////////////////////////////////////////////
def apply_avg_min_cmap(self):
	new_avg_min=(self.range_min.value+self.vmin)/2
	self.range_min.value=round(new_avg_min, 4)
	self.range_mode.value="user"

	logger.info('new min range applied')
	ShowInfoNotification('Average Min range applied successfully')

# ////////////////////////////////////////////////////////////////////////
def apply_avg_max_cmap(self):
	new_avg_max=(self.range_max.value+self.vmax)/2
	self.range_max.value=round(new_avg_max, 4)
	self.range_mode.value="user"

	logger.info('new average max range applied')
	ShowInfoNotification('Average Max range applied successfully')

# ////////////////////////////////////////////////////////////////////////
def apply_cmap(self):
	self.range_min.value=self.vmin
	self.range_max.value=self.vmax
	self.range_mode.value="user"

	logger.info('new range applied')
	ShowInfoNotification('New Colormap Range applied successfully')
	self.refresh("apply_cmap")

# ////////////////////////////////////////////////////////////////////////
def download_script(self):
	url=self.data_url
	rounded_logic_box = [
		[int(self.logic_box[0][0]), int(self.logic_box[0][1]), self.logic_box[0][2]],  
		[int(self.logic_box[1][0] ), int(self.logic_box[1][1] ), self.logic_box[1][2]] 
	]

	python_file_content = "/n".join([
		f"import OpenVisus",
		f"import numpy as np",
		f"data_url='{url}'",
		f"db=OpenVisus.LoadDataset(data_url)",
		f"data=db.read(time={self.timestep.value},logic_box={rounded_logic_box})",
		f"np.savez('selected_data',data=data)",
	])

	file_path = f'./download_script_{rounded_logic_box[0][0]}_{rounded_logic_box[0][1]}.py'
	with open(file_path, 'w') as file:
		file.write(python_file_content)
	
	ShowInfoNotification('Script to download selected data saved!')
	logger.info("Script saved successfully.") 

# ////////////////////////////////////////////////////////////////////////
def save_data(self):
	if self.detailed_data is not None:
		if self.file_name_input.value:
			file_name = f"{self.file_name_input.value}.npz"
		else:
			file_name = "test_region.npz"			
		np.savez(file_name, data=self.detailed_data, lon_lat=self.selected_physic_box)
		ShowInfoNotification('Data Saved successfully to current directory!')
		logger.info("Data saved successfully.") 
	else:
		logger.info("No data to save.")

# ////////////////////////////////////////////////////////////////////////
def ShowDetails(self,x,y,w,h):

	pdim=self.getPointDim()

	# todo for 2D dataset
	assert(pdim==3)

	z=int(self.offset.value)
	logic_box=self.toLogic([x,y,w,h])
	self.logic_box=logic_box
	data=list(ovy.ExecuteBoxQuery(self.db, access=self.db.createAccess(), field=self.field.value,logic_box=logic_box,num_refinements=1))[0]["data"]
	
	self.selected_logic_box=self.logic_box
	self.selected_physic_box=[[x,x+w],[y,y+h]]
	logger.info(f'ShowDetails({x} {y} {x+w} {y+h}) logic_box={self.logic_box}...')
	self.detailed_data=data

	save_numpy_button = pn.widgets.Button(name='Save Data as Numpy', button_type='primary')
	save_numpy_button.on_click(lambda evt: save_data(self))
	
	download_script_button = pn.widgets.Button(name='Download Script', button_type='primary')
	download_script_button.on_click(lambda evt: download_script(self))

	apply_colormap_button = pn.widgets.Button(name='Replace Existing Range', button_type='primary')
	apply_colormap_button.on_click(lambda evt: apply_cmap(self))
	
	apply_min_colormap_button = pn.widgets.Button(name='Replace Min Range', button_type='primary')
	apply_min_colormap_button .on_click(lambda evt: apply_min_cmap(self))

	apply_max_colormap_button = pn.widgets.Button(name='Replace Max Range', button_type='primary')
	apply_max_colormap_button.on_click(lambda evt: apply_max_cmap(self))

	apply_avg_min_colormap_button = pn.widgets.Button(name='Apply Average Min', button_type='primary')
	apply_avg_min_colormap_button .on_click(lambda evt: apply_avg_min_cmap(self))

	apply_avg_max_colormap_button = pn.widgets.Button(name='Apply Average Max', button_type='primary')
	apply_avg_max_colormap_button.on_click(lambda evt: apply_avg_max_cmap(self))
	
	self.vmin,self.vmax=np.min(data),np.max(data)
	add_range_button=pn.widgets.Button(name='Add This Range',button_type='primary')
	add_range_button.on_click(lambda evt: add_range(self))

	if self.range_mode.value=="dynamic-acc":
		self.vmin,self.vmax=np.min(data),np.max(data)
		self.range_min.value = min(self.range_min.value, self.vmin)
		self.range_max.value = max(self.range_max.value, self.vmax)
		logger.info(f"Updating range with selected area vmin={self.vmin} vmax={self.vmax}")
	
	p = figure(x_range=(self.selected_physic_box[0][0], self.selected_physic_box[0][1]), y_range=(self.selected_physic_box[1][0], self.selected_physic_box[1][1]))
	palette_name = self.palette.value_name if self.palette.value_name.endswith("256") else "Turbo256"

	mapper = LinearColorMapper(palette=palette_name, low=np.min(self.detailed_data), high=np.max(self.detailed_data))

	# Flip data to match imshow orientation
	data_flipped = data 
	source = bokeh.models.ColumnDataSource(data=dict(image=[data_flipped]))
	dw = abs(self.selected_physic_box[0][1] -self.selected_physic_box[0][0])
	dh = abs(self.selected_physic_box[1][1] - self.selected_physic_box[1][0])
	p.image(image='image', x=self.selected_physic_box[0][0], y=self.selected_physic_box[1][0], dw=dw, dh=dh, color_mapper=mapper, source=source)  
	color_bar = bokeh.models.ColorBar(color_mapper=mapper, label_standoff=12, location=(0,0))
	p.add_layout(color_bar, 'right')
	p.xaxis.axis_label = "X"
	p.yaxis.axis_label = "Y"

	self.showDialog(
		pn.Column(
				self.file_name_input, 
				pn.Row(save_numpy_button,download_script_button),
				pn.Row(apply_avg_min_colormap_button,apply_avg_max_colormap_button,add_range_button,apply_colormap_button),
				pn.Row(pn.pane.Bokeh(p,sizing_mode="stretch_both")),
				sizing_mode="stretch_both"
		)
		, width=900, height=800, name=f"Palette: {palette_name} Min: {self.vmin}, Max: {self.vmax}")
