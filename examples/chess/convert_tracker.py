import os
import sys
import logging
import json

from openvisuspy import SaveJSON,LoadJSON,Touch

from convert_config import GenerateDashboardConfig, GenerateModVisusConfig
from convert_data import ConvertData
from convert_db import ConvertDb
import filelock

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
		GenerateModVisusConfig([], config['modvisus'], group_name, config['modvisus-group'])
		GenerateDashboardConfig(config['dashboards'], specs=None)

		logger.info(f"convert_dir={self.convert_dir}")
		logger.info(f"\n" + json.dumps(config,indent=2))

	# getNumRunning
	def getNumRunning(self, db):
		# Let's check if a conversion has failed. We do this by trying to acquire the lock
		# on the lockfile entry. If we get the lock that means the convert process that held
		# that lock no longer exists and failed prematurely (because conversion_end is null).
		ret=0
		for row in db.getRunning():
			record_id=row['id']
			lock_filename=row['dst'] + ".filelock"
			lock_acquired=False
			try:
				with filelock.FileLock(lock_filename, timeout=1).acquire(timeout=1):
					# We got the lock. That means conversion is no longer running and failed.
					lock_acquired=True
			except filelock.Timeout:
				pass
				
			if lock_acquired:
				# We don't want to see this entry again, so mark it as failed and then log the failure.
				error_msg="probably convert crashed"
				db.markDone(row, error_msg=error_msg)
				logger.info(f"Conversion record_id={record_id} lock_filename={lock_filename} failed error_msg={error_msg}")
			else:
				# means that the conversion is still running
				ret+=1
				logger.info(f"Conversion record_id={record_id} lock_filename={lock_filename} seems to be still running")

		return ret

	# convert
	def convert(self, record_id=None):

		logger.info(f"convert_dir={self.convert_dir} record_id={record_id} ...")
		config=self.openConfig()
		db = ConvertDb(config["db"])

		if record_id is None:
			from convert_puller import LocalPuller
			puller = LocalPuller(config["pull"])
			for specs in puller.pull():
				db.pushPending(**specs)

			# run a new conversion if there are no old ones
			num_running=self.getNumRunning(db)
			if num_running:
				logger.info(f"convert_dir={self.convert_dir} exit since there are still {num_running} pending conversions")

			row=db.popPending()
			if row is None:
				logger.info(f"convert_dir={self.convert_dir} exit since there are no pending conversions")

			record_id = row['id']
			logger.info(f"Starting conversion: convert_dir={self.convert_dir} record_id={record_id}")
			self.convert(record_id)

			logger.info(f"convert_dir={self.convert_dir} record_id={record_id} DONE")

		else:

			specs = db.getRecordById(record_id)
			assert(specs["group"]==config["group"])

			# The lockfile is used to monitor whether this conversion is running or not.
			lock_filename = specs["dst"] + ".filelock"
			with filelock.FileLock(lock_filename):
				specs = ConvertData(specs)

			specs["remote_url"] = config["remote-url-template"].format(group=specs["group"], name=specs["name"])
			db.markDone(specs)

			converted=[it for it in db.getConverted()]
			GenerateModVisusConfig(converted, config["modvisus"], specs["group"], config["modvisus-group"])
			GenerateDashboardConfig(config["dashboards"], specs)

			logger.info(f"convert_dir={self.convert_dir} DONE")