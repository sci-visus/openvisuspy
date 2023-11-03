
import os,sys,json,logging,shutil
from datetime import datetime

from openvisuspy import LoadJSON

logger = logging.getLogger("nsdf-convert")

# ///////////////////////////////////////////////////////////////////
def ConvertData(src, dst, arco="8mb", compression="zip"):

	assert(src)
	assert(dst)

	logger.info(f"src={src} dst={dst}")

	if True:
			# NOTE: this is dangerous but I have to do it: I need to remove all openvisus files in case I crashed in a middle of compression
		# e.g assuyming /mnt/data1/nsdf/tmp/near-field-scrgiorgio-20230912-01/visus.idx I need to clean up the parent directory
		# SO MAKE SURE you are using unique directories!		
		data_dir=os.path.splitext(dst)[0]	
		logger.info(f" DANGEROUS but needed: removing any old data file from {data_dir}")
		shutil.rmtree(data_dir, ignore_errors=True)

	src_ext=os.path.splitext(src)[1]

	# image stack 
	if src_ext==".tif" and "*" in src:
		from convert_image_stack import ConvertImageStack
		ConvertImageStack(src, dst, compression=compression, arco=arco)

	# nexus file
	elif src_ext ==".nxs":
		# TODO: not supporting multiple fields inside a nexus file
		# TODO: with some nexus file I am unable to create shrinked streamable (probably related to NXlinkfield)
		streamable=None # os.path.splitext(dst)[0]+".nxs"
		from convert_nexus import ConvertNexus
		ConvertNexus(src, dst, compression=compression, arco=arco, streamable=None).run()
		# LocalFileToMetadata(metadata,streamable_nexus)

	elif src_ext == ".npy":
		from convert_numpy import ConvertNumPy
		ConvertNumPy(src, dst, compression=compression, arco=arco)
	
	else:
		raise Exception("to handle... ")
	


	

