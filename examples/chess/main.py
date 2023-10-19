import logging
import os
import sys
import time
import argparse

import urllib3
from openvisuspy import Touch, LoadJSON, SetupLogger

from convert_config import GenerateDashboardConfig, GenerateModVisusConfig
from convert_data import ConvertData
from convert_db import ConvertDb
import flock

urllib3.disable_warnings()

logger = logging.getLogger("nsdf-convert")


# ////////////////////////////////////////////////
def Main(argv):

	action = argv[1]

	# ____________________________________________________________________
	# pubsub specific (see https://customer.cloudamqp.com/instance)
	if action=="pub" or action=="sub" or action=="flush":


		

		"""
		echo '{"key1":"value1","key2":"value2"}' > message.json
		python ./examples/chess/main.py pub   --queue test-queue --message message.json
		python ./examples/chess/main.py sub   --queue test-queue
		python ./examples/chess/main.py flush --queue test-queue
		"""

		NSDF_CONVERT_PUBSUB_URL=os.environ["NSDF_CONVERT_PUBSUB_URL"]
		parser = argparse.ArgumentParser(description="pubsub tutorial")
		parser.add_argument("--action", type=str, help="action name", required=True)	
		parser.add_argument("--queue", type=str, help="Queue name", required=True)	
		parser.add_argument("--message", type=str, help="Message to send", default="", required=False)	
		args = parser.parse_args()

		import pika
		params = pika.URLParameters(NSDF_CONVERT_PUBSUB_URL)
		connection = pika.BlockingConnection(params)
		channel = connection.channel()
		channel.queue_declare(queue=args.queue)

		if args.action=="pub":
			if os.path.isfile(args.message):
				args.message=open(args.message).read()
			channel.basic_publish(exchange='', routing_key=args.queue ,body=args.message)
			print(f"Published message to queue={args.queue} body=\n{args.message}")

		elif args.action=="sub":
			def on_message(channel, method_frame, header_frame, body):
				body=body.decode("utf-8").strip()
				print(f"Received message from queue={args.queue} body=\n{body} ")
			channel.basic_consume(args.queue, on_message, auto_ack=True)
			channel.start_consuming()

		elif args.action=="flush":
			N=0
			while True:
				method_frame, header_frame, body =channel.basic_get(args.queue, auto_ack=False)
				if method_frame is None: break # finished
				body=body.decode("utf-8").strip()
				print(f"Received body={body} ")
				channel.basic_ack(delivery_tag=method_frame.delivery_tag)
				N+=1
			print(f"Flushed {N} messages")

		connection.close()
		return


	sqlite3_filename = os.environ["NSDF_CONVERT_DIR"] + "/sqllite3.db"
	modvisus_group_filename = os.environ["NSDF_CONVERT_DIR"] + "/visus.config"
	log_filename = os.environ["NSDF_CONVERT_DIR"] + "/output.log"
	dashboard_config_filename = os.environ["NSDF_CONVERT_DIR"] + "/dashboards.json"

	# I need to know how to publish the dataset to external nodes
	remote_url_template = os.environ["NSDF_CONVERT_REMOTE_URL_TEMPLATE"]

	# I need to know the `root` modvisus to add `include` to group
	modvisus_config_filename = os.environ["MODVISUS_CONFIG"]

	SetupLogger(logger, stream=True, log_filename=log_filename)
	# SetupLogger(logging.getLogger("OpenVisus"), stream=True)

	
	logger.info(f"action={action}")

	# _____________________________________________________________________
	if action == "init-db":
		group_name = argv[2]

		filenames = [sqlite3_filename, modvisus_group_filename, log_filename, dashboard_config_filename]
		for filename in filenames:
			if os.path.isfile(filename):
				os.remove(filename)

		db = ConvertDb(sqlite3_filename)
		Touch(log_filename)
		converted=[]
		GenerateModVisusConfig(converted, modvisus_config_filename, group_name, modvisus_group_filename)
		GenerateDashboardConfig(dashboard_config_filename, specs=None)

		for filename in filenames:
			logger.info(f"Generated {filename}")
			assert (os.path.isfile(filename))

		logger.info(f"action={action} done.")
		return


	# _____________________________________________________________________
	if action == "convert":
		if os.path.isfile(argv[2]):
			specs = LoadJSON(argv[2])
		else:
			raise Exception("not supported")

		specs = ConvertData(specs)
		specs["remote_url"] = remote_url_template.format(group=specs["group"], name=specs["name"])

		return

	# _____________________________________________________________________
	# supports either local puller or pubsub puller
	if action == "run-puller":

		# is a pattern to json files, even a signel json file
		if os.path.splitext(argv[2])[1]==".json":
			glob_pattern = argv[2]
			from convert_puller import LocalPuller
			puller = LocalPuller(glob_pattern)

		# rabbitmq
		elif argv[2].startswith("amqps://"):
			url = argv[2]
			assert(argv[3]=="--queue")
			queue=argv[4]
			from convert_puller import RabbitMqPuller
			puller = RabbitMqPuller(url, queue)

		else:
			raise Exception(f"Cannot create puller for {type}")

		db = ConvertDb(sqlite3_filename)

		while True:
			for specs in puller.pull():
				db.pushPendingConvert(**specs)
			specs = db.popPendingConvert()
			if not specs:
				time.sleep(1.0)
				continue
			specs = ConvertData(specs)
			specs["remote_url"] = remote_url_template.format(group=specs["group"], name=specs["name"])
			converted=db.getRecords(f"WHERE conversion_end is not NULL OR id={specs['id']}")
			GenerateModVisusConfig(converted, modvisus_config_filename, specs["group"], modvisus_group_filename)
			GenerateDashboardConfig(dashboard_config_filename, specs)
			db.setConvertDone(specs)
			logger.info(f"*** Re-entering loop ***")

		logger.info(f"{action} end")
		return


	# __________________________________________________________
	# specific for CHESS cronjob
	if action == "convert-from-tracker":
		# Get a lockfile. The lockfile is used to monitor whether this conversion
		# is running or not.
		pid = os.getpid()
		lockfile = f"/tmp/{pid}.pid"
		did_acquire, handle = flock.acquire(lockfile)

		if argv[2].isdigit():
			record_id = int(argv[2])
			db = ConvertDb(sqlite3_filename)
			specs = db.getRecordById(record_id)
		else:
			raise Exception("database record id is not numeric")

		db.setLockFile(record_id, lockfile)
		specs = ConvertData(specs)
		specs["remote_url"] = remote_url_template.format(group=specs["group"], name=specs["name"])
		converted=db.getRecords(f"WHERE conversion_end is not NULL OR id={specs['id']}")
		GenerateModVisusConfig(converted, modvisus_config_filename, specs["group"], modvisus_group_filename)
		GenerateDashboardConfig(dashboard_config_filename, specs)
		db.setConvertDone(specs)

		if did_acquire:
			# if we acquired the lockfile and the conversion was successful then
			# close the handle and remove the file. This will release the lock.
			handle.close()
			os.remove(lockfile)

		return

	# _____________________________________________________________________
	# specific for CHESS cronjob
	if action == "run-tracker":

		glob_pattern = argv[2]
		db = ConvertDb(sqlite3_filename)
		from convert_puller import LocalPuller
		puller = LocalPuller(glob_pattern)

		for specs in puller.pull():
			db.pushPendingConvert(**specs)

		for row in db.getFailedConverts():
			# Let's check if a conversion has failed. We do this by trying to acquire the lock
			# on the lockfile entry. If we get the lock that means the convert process that held
			# that lock no longer exists and failed prematurely (because conversion_end is null).
			if row['lockfile'] is not None and row['lockfile'] != '':
				acquired, handle = flock.check_and_acquire(row['lockfile'])
				if acquired:
					# We got the lock. That means conversion is no longer running and failed.
					# Let's log the failure and remove the lockfile.
					handle.close()
					os.remove(row['lockfile'])
					# We don't want to see this entry again, so mark it as failed and then log
					# the failure.
					db.markFailed(row['id'])
					logger.info(f"Conversion {row['id']} failed")

		for pending in db.getPendingConverts():
			record_id = pending['id']
			cmd = f"{sys.executable} {__file__} convert-from-tracker {record_id} &"
			logger.info(f"Starting conversion: {cmd}")
			db.markStarted(record_id)
			os.system(cmd)

		return

	raise Exception(f"unknown action={action}")


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	Main(sys.argv)
	sys.exit(0)
