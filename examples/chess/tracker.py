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
	def __init__(self):
		self.group_name=os.environ["NSDF_GROUP"]
		self.convert_dir=os.environ["NSDF_CONVERT_DIR"]
		self.remote_url_template=os.environ["REMOTE_URL_TEMPLATE"]
		self.glob_expr=os.environ["NSDF_TRACKER_GLOB"]
		SetupLogger(logger, stream=True, log_filename=os.path.join(self.convert_dir,"convert.log"))

	# init
	def init(self):
		logger.info(f"init ...")

		# create convert directory
		os.makedirs(self.convert_dir, exist_ok=True)

		Touch(os.path.join(self.convert_dir,"convert.log"))
		Touch(os.path.join(self.convert_dir,"dashboards.log"))
		os.makedirs(os.path.dirname(self.glob_expr), exist_ok=True ) # assuming it's like /a/b/c/*.json

		db_filename=os.path.join(self.convert_dir,"sqllite3.db")
		visus_config=os.path.join(self.convert_dir,"visus.config")
		visus_group_config=os.path.join(self.convert_dir,"visus.group.config")
		dashboards_json=os.path.join(self.convert_dir,"dashboards.json")

		db = ConvertDb(db_filename)

		GenerateModVisusConfig(visus_config, self.group_name, visus_group_config,converted=[])
		GenerateDashboardConfig(dashboards_json, self.group_name)
		logger.info(f"Tracker init done")

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

		ConvertData(
			src=specs["src"], 
			dst=specs["dst"], 
			arco=specs["arco"],
			compression=specs["compression"],
			metadata=specs["metadata"]
		)
		specs["conversion_end"]=str(datetime.now())
		specs["remote_url"] = self.remote_url_template.format(group=self.group_name, name=dataset_name)

		# NOTE: no generation of any files, pure conversion

	# convertByRecordId
	def convertByRecordId(self,record_id):
		logger.info(f"record_id={record_id} ...")
		db = ConvertDb(os.path.join(self.convert_dir,"sqllite3.db"))
		specs = db.getRecordById(record_id)
		self.convertBySpecs(specs)
		db.markDone(specs)
		converted=[it for it in db.getConverted()]
		GenerateModVisusConfig(os.path.join(self.convert_dir,"visus.config"), self.group_name, os.path.join(self.convert_dir,"visus.group.config"), converted)
		GenerateDashboardConfig(os.path.join(self.convert_dir,"dashboards.json"), self.group_name, add_specs=specs)
		logger.info(f"record_id={record_id} DONE")

	# convertNext
	def convertNext(self):

		logger.info(f"next ...")
		db = ConvertDb(os.path.join(self.convert_dir,"sqllite3.db"))

		# check for new json files to insert into the db
		from convert_puller import LocalPuller
		puller = LocalPuller(self.glob_expr)
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
			lock=filelock.FileLock(lock_filename, timeout=1)
			try:
				with lock.aquire(timeout=1):
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
		with lock:
			self.convertByRecordId(record_id)

		logger.info(f"Tracker num_running={db.getNumRunning()} num_converted={db.getNumConverted()} num_failed={db.getNumFailed()} DONE ")


# ////////////////////////////////////////////////
def Main(args):

	tracker=Tracker()

	if args[1] == "init":
		return tracker.init()

	if args[1]=="loop":
			while True:
				tracker.convertNext()
				time.sleep(10)

	if args[1]=="next":
		return tracker.convertNext()

	if args[1].isdigit():
		return tracker.convertByRecordId(record_id=int(args[1]))

	if os.path.isfile(args[1]):
		specs=LoadJSON(args[1])
		return tracker.convertBySpecs(specs)
		
	raise Exception(f"wrong arguments {args}")


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	Main(sys.argv)
	sys.exit(0)
