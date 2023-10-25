
import os,sys,shutil
from datetime import datetime
from openvisuspy import SaveFile,LoadXML,SaveXML, LoadJSON,SaveJSON
import logging

logger = logging.getLogger("nsdf-convert")

# ///////////////////////////////////////////////////////////////////
def GenerateModVisusConfig(modvisus_config_filename, group_name, modvisus_group_filename, converted):

	logger.info(f"Generating modvisus config modvisus_config_filename={modvisus_config_filename} group_name={group_name} modvisus_group_filename={modvisus_group_filename}")

	# save the include
	v=[]
	for row in converted:
		record_id, name, dst=row["id"],row["name"],row["dst"]
		v.append(f"""<dataset name='{group_name}/{name}' url='{dst}' group='{group_name}' convert_id='{record_id}' />""" )

	body="\n".join([f"<!-- file automatically generated {str(datetime.now())} -->"] + v + [""])
	SaveFile(modvisus_group_filename,body)

	# make a backup copy of root visus.config
	if False:
		timestamp=str(datetime.now().date()) + '_' + str(datetime.now().time()).replace(':', '.')
		shutil.copy(modvisus_config_filename,modvisus_config_filename+f".{timestamp}")

	# Open the file and read the contents 
	d=LoadXML(modvisus_config_filename)

	datasets=d["visus"]["datasets"]
	
	if not "group" in datasets: 
		datasets["group"]=[]
	
	if isinstance(datasets["group"],dict):
		datasets["group"]=[datasets["group"]]

	datasets["group"]=[it for it in datasets["group"] if it["@name"]!=group_name]
	datasets["group"].append({
		'@name': group_name,
		'include': {'@url': modvisus_group_filename}
	})

	print("!!!"*10,modvisus_config_filename)
	SaveXML(modvisus_config_filename, d)


# ///////////////////////////////////////////////////////////////////
def GenerateDashboardConfig(filename, group_name, add_specs=None):
	
	logger.info(f"Generating dashboards config {filename}")

	if os.path.isfile(filename):
		config=LoadJSON(filename)
	else:
		config={"datasets": []}

	# add an item to the config
	if add_specs is not None:
		dataset_name   = add_specs["name"]
		local_url      = add_specs["dst"]
		metadata       = add_specs["metadata"]
		remote_url     = add_specs["remote_url"]

		config["datasets"].append({
			"name" : f"{group_name}/{dataset_name}",
			"url" : remote_url,
			"urls": [
				{"id": "remote","url": remote_url},
				{"id": "local" ,"url": local_url}
			],
			"color-mapper-type":"log",
			"metadata" : metadata + [{
				'type':'json-object', 
				'filename': 'generated-nsdf-convert.json',  
				'object' : {k:str(v) for k,v in add_specs.items() if k!="metadata"}
			}]
		})

	SaveJSON(filename,config)