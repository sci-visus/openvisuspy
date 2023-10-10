import os ,sys, time, logging,shutil,glob,json, string, random, argparse, shutil, base64,copy,subprocess,xmltodict,pprint
from datetime import datetime
from openvisuspy import Touch,LoadJSON,LoadXML, SetupLogger, SaveXML,SaveFile,SaveJSON
from convert_data import ConvertData
from convert_config import GenerateDashboardConfig,GenerateModVisusConfig
from convert_db import ConvertDb

import urllib3
urllib3.disable_warnings()

logger = logging.getLogger("nsdf-convert")


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":

	# import OpenVisus as ov
	# ov.SetupLogger(logging.getLogger("OpenVisus"), output_stdout=True) 

	# convert directory is "self-contained"
	sqlite3_filename          = os.environ["NSDF_CONVERT_DIR"] + "/sqllite3.db"
	modvisus_group_filename   = os.environ["NSDF_CONVERT_DIR"] + "/visus.config"
	log_filename              = os.environ["NSDF_CONVERT_DIR"] + "/output.log"
	dashboard_config_filename = os.environ["NSDF_CONVERT_DIR"] + "/dashboards.json"

	# I need to know how to publish the dataset to external nodes
	remote_url_template       = os.environ["NSDF_CONVERT_REMOTE_URL_TEMPLATE"]

	# I need to know the `root` modvisus to add `include` to group
	modvisus_config_filename  = os.environ["MODVISUS_CONFIG"]
	
	SetupLogger(logger, log_filename)

	action=sys.argv[1]

	# _____________________________________________________________________
	if action=="init-db":
			group_name=sys.argv[2]
			os.remove(sqlite3_filename         ) if os.path.isfile(sqlite3_filename         ) else None
			os.remove(modvisus_group_filename  ) if os.path.isfile(modvisus_group_filename  ) else None
			os.remove(log_filename             ) if os.path.isfile(log_filename             ) else None
			os.remove(dashboard_config_filename) if os.path.isfile(dashboard_config_filename) else None
			db=ConvertDb(sqlite3_filename)
			GenerateModVisusConfig(db, modvisus_config_filename, group_name, modvisus_group_filename)
			GenerateDashboardConfig(dashboard_config_filename,specs=None)
			logger.info(f"action={action} done.")
			sys.exit(0)

	# _____________________________________________________________________
	if action=="convert":

		if os.path.isfile(sys.argv[2]):
			db=None
			specs=LoadJSON(sys.argv[2])

		elif sys.argv[2].isdigit():
			id=int(sys.argv[2])
			db=ConvertDb(sqlite3_filename)
			specs=db.getRecordById(id)
			
		else:
			raise Exception("not supported")
		
		specs=ConvertData(specs)
		specs["remote_url"]=remote_url_template.format(group=specs["group"], name=specs["name"])

		if db is not None:
			db.setConvertDone(specs)
			GenerateModVisusConfig(db, modvisus_config_filename, specs["group"], modvisus_group_filename)
			GenerateDashboardConfig(dashboard_config_filename, specs)			

		sys.exit(0)

	# _____________________________________________________________________
	if action=="run-puller":
		logger.info(f"action={action}")

		db=ConvertDb(sqlite3_filename)

		# is a pattern to json files
		if "*.json" in sys.argv[2]:
			pattern=type
			from convert_puller import PullEventsFromLocalDirectory
			puller=PullEventsFromLocalDirectory(db,pattern)

		# rabbitmq
		elif sys.argv[2].startswith("amqps://"):
			url,queue=sys.argv[2:]
			from convert_puller import PullEventsFromRabbitMq
			puller=PullEventsFromRabbitMq(db,url,queue)

		else:
			raise Exception(f"Cannot create puller for {type}")

		while True:
			puller.pull()
			specs=db.popPendingConvert()
			if not specs:
				time.sleep(1.0)
				continue
			specs=ConvertData(specs)
			specs["remote_url"]=remote_url_template.format(group=specs["group"], name=specs["name"])
			db.setConvertDone(specs)
			GenerateModVisusConfig(modvisus_config_filename, specs["group"], modvisus_group_filename)
			GenerateDashboardConfig(dashboard_config_filename, specs)
			logger.info(f"*** Re-entering loop ***")

		logger.info(f"RunConvertLoop end")
		sys.exit(0)

	raise Exception(f"unknown action={action}")


