import glob,os,sys,json
from openvisuspy import SaveJSON, LoadJSON

group_name=os.environ["NSDF_GROUP"]

# change as needed
experiment_dir=f"/nfs/chess/raw/2023-3/id3a/{group_name}"

# change as needed
job_dir="/mnt/data1/nsdf/workflow/{group_name}/jobs"

# where to temporary store jobs file (to be moved)
# I prefer not to write direcly to the jobs directory
tmp_dir="./tmp"
os.makedirs(tmp_dir,exist_ok=True)

# for near field
nf_ext=".tif"

# //////////////////////////////////////////////////////////
def ConvertFarField():

	ret=0
	for filename in glob.glob(f"{experiment_dir}/**/ff/ff*.h5",recursive=True):

		# not useful
		if "snapshots" in filename or "test" in filename:
			continue
		
		# compose the job name
		v=filename.split("/")
		sample,scan,panel=v[-4],v[-3],v[-1][0:3]
		job_name=f"{sample}_{scan}_{panel}"

		# already done
		if list(glob.glob(f"{job_dir}/{job_name}.json*")):
			continue

		SaveJSON(f"{tmp_dir}/{job_name}.json",{
			"name": job_name,
			"src": filename,
			"metadata": [{"type": "chess-metadata", "query": {"Technique": "Tomography"}}]
		})

		print(f"[{ret}] Adding far-field {job_name}")
		ret+=1

	return ret

# ///////////////////////////////////////////////
def ConvertNearField():
	ret=0
	for dir in glob.glob(f"{experiment_dir}/**/nf",recursive=True):
		
		# not useful
		if "snapshots" in dir or "test" in dir:
			continue
		
		# compose the job name
		sample,scan=dir.split("/")[-3:-1]
		job_name=f"{sample}_{scan}"

		# already done
		if list(glob.glob(f"{job_dir}/{job_name}.json*")):
			continue

		# no image files
		if not list(glob.glob(f"{dir}/{nf_ext}")):
			continue

		SaveJSON(f"{tmp_dir}/{job_name}.json",{
			"name": job_name,
			"src": f"${dir}/nf_{nf_ext}",
			"metadata": [{"type": "chess-metadata", "query": {"Technique": "Tomography"}}]
		})

		print(f"[{ret}] Adding near-field {job_name}")
		ret+=1

	return ret


# ////////////////////////////////////////////////////////////////////
if __name__=="__main__":

	num_found=0
	num_found+=ConvertFarField()
	num_found+=ConvertNearField()

	# User should be responsible to start the jobs
	if num_found:
		print(f"found {num_found} new jobs to run")
		print(f"You need to run `mv {tmp_dir}/*.json {job_dir}/")
	else:
		print("Did not find any new job to run")