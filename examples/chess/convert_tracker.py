import os,sys, glob,json,logging,shutil
import sqlite3
from datetime import datetime

from openvisuspy import SetupLogger, LoadJSON
from convert_db import ConvertDb

logger = logging.getLogger("nsdf-convert")

# ///////////////////////////////////////////////////////////////////
def Main(pattern,db_filename):

	"""
cat <<EOF > ./test.json
{
   "group": "my-group",
   "name": "my-dataset",
   "src": "./recon_combined_1_2_3_fullres.npy",
   "dst": "./tmp/visus.idx",
   "compression": "zip",
   "arco": "1mb",
   "metadata": []}
EOF

python3 examples/chess/chess_conversion_tracker.py ./*.json ./db.sqlite3 
	"""

	# run this function every XX seconds
	db=ConvertDb(db_filename)

	# check for JSON files in a common directory
	for filename in list(glob.glob(pattern)):
			logger.info(f"found new JSON file {filename}")
			try:
				specs=LoadJSON(filename)
				logger.info(f"json.loads('{filename}') ok")
				db.pushPendingConvert(**specs)
				shutil.move(filename,filename + ".running")

			except Exception as ex:
				logger.info(f"json.loads('{filename}') failed {ex}")
				shutil.move(filename,filename + ".failed")

	for row in db.getMaybeFailed():
		logger.info(f"Convertion {id} may have failed")
		# TODO... lock thingy?

	# run another conversion
	specs=db.popPendingConvert()
	id=specs["id"]
	logger.info(f"Running new conversion {specs}")
	# TODO... lock thingy?
	# os.system(f"{sys.executable} examples/chess/main.py convert {id} &")


# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":
	SetupLogger(logger, stream=True, filename=f"/tmp/chess-conversion-tracker.{os.getpid()}.log")
	pattern,db_filename=sys.argv[1:]
	Main(pattern,db_filename)