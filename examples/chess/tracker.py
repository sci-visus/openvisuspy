import os
import sys
import logging
import json
import time
import argparse
import shutil
import json
import filelock
from datetime import datetime

import urllib3
urllib3.disable_warnings()

from openvisuspy import SaveJSON,LoadJSON, SetupLogger,Touch

from convert_config import GenerateDashboardConfig, GenerateModVisusConfig
from convert_data import ConvertData
from convert_db import ConvertDb

logger = logging.getLogger("nsdf-convert")

# /////////////////////////////////////////////////////////////////
class Tracker:

	# constructor
	def __init__(self,convert_dir):
		self.convert_dir=convert_dir
		self.config=None

	# getConfig
	def getConfig(self,force=False):
		if self.config is not None and not force: return self.config
		self.config=LoadJSON(os.path.join(self.convert_dir,".config"))
		return self.config

	# init
	def init(self, pull):
		logger.info(f"IniTracker convert_dir={self.convert_dir} pull={pull}...")

		# create convert directory
		os.makedirs(self.convert_dir, exist_ok=True)

		# assuming the last part of the path is the group name
		group_name = os.path.basename(self.convert_dir) 

		SaveJSON(os.path.join(self.convert_dir,".config"),{
			'db': os.path.join(self.convert_dir,"sqllite3.db"),
			'group' : group_name,
			'modvisus': os.environ["MODVISUS_CONFIG"],
			'modvisus-group': os.path.join(self.convert_dir,"visus.config"),
			'dashboards' : os.path.join(self.convert_dir,"dashboards.json"),
			'remote-url-template':os.environ["REMOTE_URL_TEMPLATE"].replace("{group}",group_name),
			'convert-log' : os.path.join(self.convert_dir,"convert.log"),
			'dashboards-log' : os.path.join(self.convert_dir,"dashboards.log"),
			'pull': pull,
		})
		config=self.getConfig(force=True)

		Touch(config['convert-log'])
		Touch(config['dashboards-log'])
		os.makedirs(os.path.dirname(pull), exist_ok=True ) # assuming it's like /a/b/c/*.json

		db = ConvertDb(config['db'])
		GenerateModVisusConfig(config['modvisus'], group_name, config['modvisus-group'],[])
		GenerateDashboardConfig(config['dashboards'], group_name)

		logger.info(f"convert_dir={self.convert_dir}")
		logger.info(f"\n" + json.dumps(config,indent=2))

	# convertBySpecs
	def convertBySpecs(self, specs):

		dataset_name=specs["name"]

		if not "dst" in specs:
			specs["dst"]=os.path.join(self.convert_dir,"datasets",dataset_name +".idx")

		if not "arco" in specs:
			specs["arco"]="8mb"

		if not "compression" in specs:
			specs["compression"]="zip"

		if not "metadata" in specs:
			specs["metadata"]=[]

		config=self.getConfig()
		group_name=config["group"]
		ConvertData(
			src=specs["src"], 
			dst=specs["dst"], 
			arco=specs["arco"],
			compression=specs["compression"],
			metadata=specs["metadata"]
		)
		specs["conversion_end"]=str(datetime.now())
		specs["remote_url"] = config["remote-url-template"].format(group=group_name, name=dataset_name)

		# NOTE: no generation of any files, pure conversion

	# convertByRecordId
	def convertByRecordId(self,record_id):
		logger.info(f"convert_dir={self.convert_dir} record_id={record_id} ...")
		config=self.getConfig()
		group_name=config["group"]
		db = ConvertDb(config["db"])
		specs = db.getRecordById(record_id)
		self.convertBySpecs(specs)
		db.markDone(specs)
		converted=[it for it in db.getConverted()]
		GenerateModVisusConfig(config["modvisus"]   , group_name, config["modvisus-group"], converted)
		GenerateDashboardConfig(config["dashboards"], group_name, add_specs=specs)
		logger.info(f"convert_dir={self.convert_dir} record_id={record_id} DONE")

	# convertNextPending
	def convertNextPending(self):

		logger.info(f"convert_dir={self.convert_dir} ...")
		config=self.getConfig()
		db = ConvertDb(config["db"])

		# check for new json files to insert into the db
		from convert_puller import LocalPuller
		puller = LocalPuller(config["pull"])
		for specs in puller.pull():
			dataset_name=specs["name"]
			src=specs["src"]
			dst=os.path.join(self.convert_dir,"datasets",dataset_name +".idx")
			compression=specs.get("compression","zip")
			arco=specs.get("arco","8mb")
			metadata=specs.get("metadata",[])
			db.pushPending(name=dataset_name, src=src, dst=dst, compression=compression,arco=arco,metadata=metadata)

		# run a new conversion if there are no old ones
		# Let's check if a conversion has failed. We do this by trying to acquire the lock
		# on the lockfile entry. If we get the lock that means the convert process that held
		# that lock no longer exists and failed prematurely (because conversion_end is null).
		for row in db.getRunning():
			record_id=row['id']
			lock_filename=row["dst"] + ".filelock"
			try:
				lock=filelock.FileLock(lock_filename, timeout=1)
				with lock.acquire(timeout=1):
					# We got the lock. That means conversion is no longer running and failed.
					# We don't want to see this entry again, so mark it as failed and then log the failure.
					error_msg=f"got the filelock {lock_filename}"
					db.markDone(row, error_msg=error_msg)
					logger.info(f"Conversion record_id={record_id} probably failed error_msg={error_msg}")
			except filelock.Timeout:
				logger.info(f"Conversion record_id={record_id} seems to be still running")
				return

		# avoid parallel conversion
		if db.getNumRunning():
			logger.info(f"num_running={db.getNumRunning()} num_converted={db.getNumConverted()} num_failed={db.getNumFailed()}")
			return

		specs=db.popPending()
		if specs is None:
			logger.info(f"there are no pending conversions")
			return

		# this is the next pending conversion
		record_id = specs['id']
		logger.info(f"Found new conversion to run record_id={record_id}")

		# The lockfile is used to monitor whether this conversion is running or not.
		lock_filename = specs["dst"] + ".filelock"
		lock=filelock.FileLock(lock_filename)
		with lock.acquire():
			self.convertByRecordId(record_id)

		logger.info(f"convert_dir={self.convert_dir} num_running={db.getNumRunning()} num_converted={db.getNumConverted()} num_failed={db.getNumFailed()} DONE ")


# ////////////////////////////////////////////////
def Main(args):

	action=args.pop(1)
	convert_dir=args.pop(1)

	SetupLogger(logger, stream=True, log_filename=os.path.join(convert_dir,"convert.log"))

	tracker=Tracker(convert_dir)

	if action == "init":
		pull_expr=args.pop(1)
		return tracker.init(pull=pull_expr)

	if action=="convert":

		if len(args)==2 and args[1].isdigit():
			record_id=int(args.pop(1))
			tracker.convertByRecordId(record_id)

		elif len(args)==2 and os.path.isfile(args[1]) and os.path.splitext(args[1])[1]==".json":
			specs=LoadJSON(args[1])
			tracker.convertBySpecs(specs)
		
		else:
			if "--loop" in args:
				while True:
					tracker.convertNextPending()
					time.sleep(10)
			else:
				tracker.convertNextPending()

		return
				
	raise Exception(f"unknown action={action}")


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	Main(sys.argv)
	sys.exit(0)
