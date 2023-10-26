
import os,sys,shutil
from datetime import datetime
from openvisuspy import SaveFile,LoadXML,SaveXML, LoadJSON,SaveJSON
import logging

logger = logging.getLogger("nsdf-convert")

# ///////////////////////////////////////////////////////////////////
def AddGroupToModVisus(visus_config, group_name, visus_group_config):

	logger.info(f"visus_config={visus_config} group_name={group_name} visus_group_config={visus_group_config}")

	# Open the file and read the contents 
	d=LoadXML(visus_config)

	datasets=d["visus"]["datasets"]
	
	if not "group" in datasets: 
		datasets["group"]=[]
	
	if isinstance(datasets["group"],dict):
		datasets["group"]=[datasets["group"]]

	datasets["group"]=[it for it in datasets["group"] if it["@name"]!=group_name]
	datasets["group"].append({
		'@name': group_name,
		'include': {'@url': visus_group_config}
	})

	SaveXML(visus_config, d)


# ///////////////////////////////////////////////////////////////////
def GenerateVisusGroupConfig(group_name, visus_group_config, converted):
	logger.info(f"group_name={group_name} visus_group_config={visus_group_config}")
	v=[]
	v.append(f"<!-- file automatically generated {str(datetime.now())} -->")
	for row in converted:
		record_id, name, dst = row.get("id",-1),row["name"],row["dst"]
		v.append(f"""<dataset name='{group_name}/{name}' url='{dst}' group='{group_name}' convert_id='{record_id}' />""" )
	v.append("")
	SaveFile(visus_group_config,"\n".join(v))


# ///////////////////////////////////////////////////////////////////
def GenerateDashboardConfig(filename, group_name, add_specs=None):
	
	logger.info(f"Generating dashboards config {filename}")

	config={}
	if os.path.isfile(filename):
		config=LoadJSON(filename)
		
	if not "datasets" in config:
		config["datasets"]=[]

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