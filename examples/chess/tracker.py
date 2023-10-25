import os
import sys
import logging
import json
import time
import argparse
import shutil
import json
import filelock

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

	# saveConfig
	def saveConfig(self,d):
		SaveJSON(os.path.join(self.convert_dir,".config"),d)

	# openConfig
	def openConfig(self):
		return LoadJSON(os.path.join(self.convert_dir,".config"))

	# init
	def init(self, pull):
		logger.info(f"IniTracker convert_dir={self.convert_dir} pull={pull}...")

		# assuming the last part of the path is the group name
		group_name = os.path.basename(self.convert_dir) 

		self.saveConfig({
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
		config=self.openConfig()

		Touch(config['convert-log'])
		Touch(config['dashboards-log'])
		os.makedirs(os.path.dirname(pull), exist_ok=True ) # assuming it's like /a/b/c/*.json

		db = ConvertDb(config['db'])
		GenerateModVisusConfig(config['modvisus'], group_name, config['modvisus-group'],[])
		GenerateDashboardConfig(config['dashboards'], specs=None)

		logger.info(f"convert_dir={self.convert_dir}")
		logger.info(f"\n" + json.dumps(config,indent=2))

	# convertByRecordId
	def convertByRecordId(self,record_id):
		logger.info(f"convert_dir={self.convert_dir} record_id={record_id} ...")
		config=self.openConfig()
		db = ConvertDb(config["db"])
		specs = db.getRecordById(record_id)
		assert(specs["group"]==config["group"])
		specs = ConvertData(specs)
		specs["remote_url"] = config["remote-url-template"].format(group=specs["group"], name=specs["name"])
		db.markDone(specs)
		converted=[it for it in db.getConverted()]
		GenerateModVisusConfig(config["modvisus"], specs["group"], config["modvisus-group"], converted)
		GenerateDashboardConfig(config["dashboards"], specs)
		logger.info(f"convert_dir={self.convert_dir} record_id={record_id} DONE")

	# convertNextPending
	def convertNextPending(self):

		logger.info(f"convert_dir={self.convert_dir} ...")
		config=self.openConfig()
		db = ConvertDb(config["db"])

		# check for new json files to insert into the db
		from convert_puller import LocalPuller
		puller = LocalPuller(config["pull"])
		for specs in puller.pull():
			db.pushPending(**specs)

		# run a new conversion if there are no old ones
		# Let's check if a conversion has failed. We do this by trying to acquire the lock
		# on the lockfile entry. If we get the lock that means the convert process that held
		# that lock no longer exists and failed prematurely (because conversion_end is null).
		for row in db.getRunning():
			record_id=row['id']
			lock_filename=row['dst'] + ".filelock"
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
