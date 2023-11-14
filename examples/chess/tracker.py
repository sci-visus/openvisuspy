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

from openvisuspy import SaveJSON, LoadJSON, SetupLogger,Touch

from convert_config import GenerateDashboardConfig, AddGroupToModVisus, GenerateVisusGroupConfig
from convert_data import ConvertData
from convert_db import ConvertDb
from convert_metadata import LoadMetadata

logger = logging.getLogger("nsdf-convert")

# /////////////////////////////////////////////////////////////////
class Tracker:

	# constructor
	def __init__(self, convert_dir):

		# where all the files will be
		self.convert_dir=convert_dir
		SetupLogger(logger, stream=True, log_filename=os.path.join(convert_dir,"convert.log"))

		# last part of the path
		self.group_name=os.path.basename(self.convert_dir) 

		# need to come from the env
		self.remote_url_template=os.environ["REMOTE_URL_TEMPLATE"]

		# all this in the convert_dir
		self.db_filename=os.path.join(convert_dir,"sqllite3.db")
		self.visus_config=os.path.join(convert_dir,"visus.config")
		self.visus_group_config=os.path.join(convert_dir,"visus.group.config")
		self.dashboards_config=os.path.join(convert_dir,"dashboards.json")

	# createDb
	def createDb(self):
		logger.info(f"createDb ...")
		db = ConvertDb(self.db_filename).createDb()
		logger.info(f"createDb done")

	# getDestinationFilename
	def getDestinationFilename(self, dataset_name):
		return os.path.join(self.convert_dir,"datasets",dataset_name,"visus.idx")

	# convertBySpecs
	def convertBySpecs(self, specs):

		dataset_name=specs["name"]

		if not specs.get("dst",None):
			specs["dst"] = self.getDestinationFilename(dataset_name) 

		logger.info(f"specs={specs}...")
		
		if not "metadata" in specs: specs["metadata"]={}
		specs["metadata"]=LoadMetadata(specs["metadata"])

		db = ConvertDb(self.db_filename)
		ConvertData(specs)
		specs["conversion_end"]=str(datetime.now())
		specs["remote_url"] = self.remote_url_template.format(group=self.group_name, name=dataset_name)

		converted=[it for it in db.getConverted()]
		AddGroupToModVisus(self.visus_config, self.group_name, self.visus_group_config) # automatically add group
		GenerateVisusGroupConfig(self.group_name,self.visus_group_config,converted + [specs])
		GenerateDashboardConfig(self.dashboards_config, self.group_name, add_specs=specs)

		if db.getRecordById(specs.get("id",-1)):
			db.markDone(specs)


	# convertByRecordId
	def convertByRecordId(self,record_id):
		logger.info(f"record_id={record_id} ...")
		db = ConvertDb(self.db_filename)
		specs = db.getRecordById(record_id)
		self.convertBySpecs(specs)
		logger.info(f"record_id={record_id} DONE")

	# convertNext
	def convertNext(self, glob_expr=None):

		if glob_expr is None:
			glob_expr=os.path.join(self.convert_dir,"jobs/*.json")

		logger.info("# -----------------------------------------------------------")
		logger.info(f"next {glob_expr}...")
		db = ConvertDb(self.db_filename)

		# check for new json files to insert into the db
		from convert_puller import LocalPuller
		puller = LocalPuller(glob_expr)
		for specs in puller.pull():
			specs["dst"]          = specs.get("dst",self.getDestinationFilename(specs["name"]))
			specs["compression"]  = specs.get("compression","zip")
			specs["arco"]         = specs.get("arco","8mb")
			specs["metadata"]     = specs.get("metadata",[]) 
			db.pushPending(specs)

		# run a new conversion if there are no old ones
		# Let's check if a conversion has failed. We do this by trying to acquire the lock
		# on the lockfile entry. If we get the lock that means the convert process that held
		# that lock no longer exists and failed prematurely (because conversion_end is null).
		for row in db.getRunning():
			record_id=row['id']
			lock_filename=row["dst"] + ".filelock"
			lock=filelock.FileLock(lock_filename, timeout=1)
			try:
				with lock.acquire(timeout=1):
					# We got the lock. That means conversion is no longer running and failed.
					# We don't want to see this entry again, so mark it as failed and then log the failure.
					error_msg=f"got the filelock[{lock_filename}]"
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

	action=args.pop(1)

	parser = argparse.ArgumentParser(description="Tracker")
	parser.add_argument("--convert-dir", type=str, help="action name", required=True)	
	parser.add_argument("--jobs", type=str, help="action name", required=action in ["run-loop", "run-next"], default=None)
	args, unknown_args = parser.parse_known_args(args)

	unknown_args=unknown_args[1:]


	tracker=Tracker(args.convert_dir)

	if action == "create-db":
		tracker.createDb()
		return 

	if action=="run-loop":
		while True:
			tracker.convertNext(args.jobs)
			time.sleep(10)
		return

	if action=="run-next":
		tracker.convertNext(args.jobs)
		return 

	if action=="convert":

		for it in unknown_args:

			if it.isdigit():
				record_id=int(it)
				tracker.convertByRecordId(record_id)
				continue

			elif os.path.isfile(it):
				specs=LoadJSON(it)
				tracker.convertBySpecs(specs)
				continue


			raise Exception(f"wrong argument {it}")
		return
		
	raise Exception(f"wrong arguments")


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	Main(sys.argv)
	sys.exit(0)
