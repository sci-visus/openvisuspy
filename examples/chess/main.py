import os ,sys, time, logging,shutil,glob,json, string, random, argparse, shutil, base64,copy,subprocess,xmltodict,pprint
from datetime import datetime
from openvisuspy import Touch,LoadJSON,LoadXML, SetupLogger, SaveXML,SaveFile,SaveJSON
from convert_data import ConvertData
from convert_config import GenerateDashboardConfig,GenerateModVisusConfig
from convert_db import ConvertDb

import urllib3
urllib3.disable_warnings()

logger = logging.getLogger("nsdf-convert")

# ////////////////////////////////////////////////
def Main(argv):

	sqlite3_filename          = os.environ["NSDF_CONVERT_DIR"] + "/sqllite3.db"
	modvisus_group_filename   = os.environ["NSDF_CONVERT_DIR"] + "/visus.config"
	log_filename              = os.environ["NSDF_CONVERT_DIR"] + "/output.log"
	dashboard_config_filename = os.environ["NSDF_CONVERT_DIR"] + "/dashboards.json"

	# I need to know how to publish the dataset to external nodes
	remote_url_template       = os.environ["NSDF_CONVERT_REMOTE_URL_TEMPLATE"]

	# I need to know the `root` modvisus to add `include` to group
	modvisus_config_filename  = os.environ["MODVISUS_CONFIG"]
	
	SetupLogger(logger, stream=True, log_filename=log_filename)
	# SetupLogger(logging.getLogger("OpenVisus"), stream=True) 

	action=argv[1]
	logger.info(f"action={action}")

	# _____________________________________________________________________
	if action=="init-db":
			group_name=argv[2]

			filenames=[sqlite3_filename,modvisus_group_filename,log_filename,dashboard_config_filename]
			for filename in filenames:
				if os.path.isfile(filename):
					os.remove(filename)

			db=ConvertDb(sqlite3_filename)
			Touch(log_filename)
			GenerateModVisusConfig(db, modvisus_config_filename, group_name, modvisus_group_filename)
			GenerateDashboardConfig(dashboard_config_filename,specs=None)

			for filename in filenames:
				logger.info(f"Generated {filename}")
				assert(os.path.isfile(filename))

			logger.info(f"action={action} done.")
			return

	# _____________________________________________________________________
	if action=="convert":

		if os.path.isfile(argv[2]):
			db=None
			specs=LoadJSON(argv[2])

		elif argv[2].isdigit():
			id=int(argv[2])
			db=ConvertDb(sqlite3_filename)
			specs=db.getRecordById(id)
			
		else:
			raise Exception("not supported")
		
		specs=ConvertData(specs)
		specs["remote_url"]=remote_url_template.format(group=specs["group"], name=specs["name"])

		if db is not None:
			GenerateModVisusConfig(db, modvisus_config_filename, specs["group"], modvisus_group_filename)
			GenerateDashboardConfig(dashboard_config_filename, specs)
			db.setConvertDone(specs)

		return

	# _____________________________________________________________________
	if action=="run-puller":

		# is a pattern to json files
		if "*.json" in argv[2]:
			glob_pattern=argv[2]
			from convert_puller import LocalPuller
			puller=LocalPuller(glob_pattern)

		# rabbitmq
		elif argv[2].startswith("amqps://"):
			url,queue=argv[2:]
			from convert_puller import RabbitMqPuller
			puller=RabbitMqPuller(url,queue)

		else:
			raise Exception(f"Cannot create puller for {type}")
		
		db=ConvertDb(sqlite3_filename)

		while True:
			for specs in puller.pull():
				db.pushPendingConvert(**specs)
			specs=db.popPendingConvert()
			if not specs:
				time.sleep(1.0)
				continue
			specs=ConvertData(specs)
			specs["remote_url"]=remote_url_template.format(group=specs["group"], name=specs["name"])
			GenerateModVisusConfig(db, modvisus_config_filename, specs["group"], modvisus_group_filename)
			GenerateDashboardConfig(dashboard_config_filename, specs)
			db.setConvertDone(specs)
			logger.info(f"*** Re-entering loop ***")

		logger.info(f"{action} end")
		return

	# _____________________________________________________________________
	if action=="run-tracker":

		glob_pattern=argv[2]
		db=ConvertDb(sqlite3_filename)
		from convert_puller import LocalPuller
		puller=LocalPuller(glob_pattern)

		for specs in puller.pull():
			db.pushPendingConvert(**specs) 

		# TODO: lock thingy?
		for row in db.getRecords(where="WHERE conversion_start is not NULL and conversion_end is NULL"):
			logger.info(f"Convertion {row['id']} may have failed")

		specs=db.popPendingConvert()
		if not specs:
			return 
		
		# TODO: lock thingy
		id=specs["id"]
		cmd=f"{sys.executable} {__file__} convert {id} &"
		logger.info(f"Running {cmd}")
		os.system(cmd)
		return

	raise Exception(f"unknown action={action}")

# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	Main(sys.argv)
	sys.exit(0)


