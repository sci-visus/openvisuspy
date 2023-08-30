
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
	python ./examples/chess/pub.py --queue my-queue --message '{"key1":"value1","key2":"value2"}'
	"""
	PUBSUB_URL=os.environ["PUBSUB_URL"]
	params = pika.URLParameters(PUBSUB_URL)
	connection = pika.BlockingConnection(params)
	channel = connection.channel()
	parser = argparse.ArgumentParser(description="pubsub tutorial")
	parser.add_argument("--queue", type=str, help="Queue name", required=True)	
	parser.add_argument("--message", type=str, help="Message to send", required=True)	
	args = parser.parse_args()
	channel.queue_declare(queue=args.queue)
	channel.basic_publish(exchange='', routing_key=args.queue ,body=args.message)
	logger.info(f"Published body={args.message} queue={args.queue}")
	connection.close()
