import glob,os,sys,json
from openvisuspy import SaveJSON, LoadJSON

# change as needed
experiment_dir="/nfs/chess/raw/2023-3/id3a/berman-3804-a"

# change as needed
job_dir="/mnt/data1/nsdf/workflow/umich/jobs"

# where to temporary store jobs file (to be moved)
# I prefer not to write direcly to the jobs directory
tmp_dir="./tmp"

# for near field
nf_ext=".tif"

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

		ret+=1

	return ret


# ////////////////////////////////////////////////////////////////////
if __name__=="__main__":

	num_found=0
	num_found+=ConvertNearField()

	# User should be responsible to start the jobs
	if num_found:
		print(f"found {num_found} new jobs to run")
		print(f"You need to run `mv {tmp_dir}/*.json {job_dir}/")
	else:
		print("Did not find any new job to run")