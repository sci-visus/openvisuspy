
import os,sys,json,logging,shutil
from datetime import datetime

from openvisuspy import LoadJSON

logger = logging.getLogger("nsdf-convert")

# ///////////////////////////////////////////////////////////////////
def ConvertData(specs):

	logger.info(f"spec={json.dumps(specs,indent=2)}")

	src,dst=specs["src"],specs["dst"]

	# extract group_name (name should be in the form `group/whatever`)
	group_name, dataset_name=specs['group'],specs['name']
	logger.info(f"group={group_name} name={dataset_name}")

	from convert_metadata import LoadMetadata
	metadata=LoadMetadata(specs["metadata"])

	if True:
			# NOTE: this is dangerous but I have to do it: I need to remove all openvisus files in case I crashed in a middle of compression
		# e.g assuyming /mnt/data1/nsdf/tmp/near-field-scrgiorgio-20230912-01/visus.idx I need to clean up the parent directory
		# SO MAKE SURE you are using unique directories!			
		logger.info(f" DANGEROUS but needed: removing any file from {os.path.dirname(dst)}")
		shutil.rmtree(os.path.dirname(dst), ignore_errors=True)

	src_ext=os.path.splitext(src)[1]

	# image stack 
	if src_ext==".tif" and "*" in src:
		from convert_image_stack import ConvertImageStack
		ConvertImageStack(src, dst, compression=specs["compression"], arco=specs["arco"])

	# nexus file
	elif src_ext ==".nxs":
		# TODO: not supporting multiple fields inside a nexus file
		# TODO: with some nexus file I am unable to create shrinked streamable (probably related to NXlinkfield)
		streamable=None # os.path.splitext(dst)[0]+".nxs"
		from convert_nexus import ConvertNexus
		ConvertNexus(src, dst, compression=specs["compression"], arco=specs["arco"], streamable=None).run()
		# LocalFileToMetadata(metadata,streamable_nexus)

	elif src_ext == ".npy":
		from convert_numpy import ConvertNumPy
		ConvertNumPy(src, dst, compression=specs["compression"], arco=specs["arco"])
	
	else:
		raise Exception("to handle... ")
	
	specs["conversion_end"]=str(datetime.now())
	return specs

	

