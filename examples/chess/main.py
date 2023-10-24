import logging
import os
import sys
import time
import argparse
import shutil
import json
import urllib3

from openvisuspy import LoadJSON, SetupLogger

from convert_tracker import Tracker
from convert_data    import ConvertData

urllib3.disable_warnings()

logger = logging.getLogger("nsdf-convert")

# /////////////////////////////////////////////////
def RunPubSub(argv):

	"""
	echo '{"key1":"value1","key2":"value2"}' > message.json
	python ./examples/chess/main.py pub   --queue test-queue --message message.json
	python ./examples/chess/main.py sub   --queue test-queue
	python ./examples/chess/main.py flush --queue test-queue
	"""

	parser = argparse.ArgumentParser(description="pubsub tutorial")
	parser.add_argument("--url", type=str, help="action name", required=True)	
	parser.add_argument("--action", type=str, help="action name", required=True)	
	parser.add_argument("--queue", type=str, help="Queue name", required=True)	
	parser.add_argument("--message", type=str, help="Message to send", default="", required=False)	
	args = parser.parse_args()

	import pika
	params = pika.URLParameters(args.url)
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


# ////////////////////////////////////////////////
def Main(args):

	action=args.pop(1)
	
	if action=="pub" or action=="sub" or action=="flush":
		return RunPubSub(args)

	if action == "convert":
		specs=LoadJSON(args[1])
		return ConvertData(specs)
	
	# _________________________________________________________
	if "tracker" in action:

		convert_dir=args[1]
		SetupLogger(logger, stream=True, log_filename=os.path.join(convert_dir,"convert.log"))

		tracker=Tracker(convert_dir)

		if action == "tracker-init":
			return tracker.init(pull=args[2])

		if action=="tracker-convert":
			return tracker.convert(record_id=args[2] if len(args)>=3 else None)
				
	# _________________________________________________________

	raise Exception(f"unknown action={action}")


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	Main(sys.argv)
	sys.exit(0)
