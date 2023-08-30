
# # python3 -m pip install pika
import os,sys, json, argparse, pika

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# ////////////////////////////////////////////////////////////////
if __name__=="__main__":

	"""
	python ./examples/chess/sub.py --queue my-queue
	""" 
	PUBSUB_URL=os.environ["PUBSUB_URL"]
	params = pika.URLParameters(PUBSUB_URL)
	connection = pika.BlockingConnection(params)
	channel = connection.channel()
	parser = argparse.ArgumentParser(description="pubsub tutorial")
	parser.add_argument("--queue", type=str, help="Queue name", required=True)	
	args = parser.parse_args()
	channel.queue_declare(queue=args.queue)

	def on_message(channel, method_frame, header_frame, body):
		msg=json.loads(body.decode("utf-8").strip())
		logger.info(f"Received msg={msg} ")

	channel.basic_consume(args.queue, on_message, auto_ack=True)
	channel.start_consuming()
	connection.close()





