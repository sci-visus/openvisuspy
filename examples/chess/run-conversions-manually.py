import glob,os,sys,json

# change as needed
experiment_dir="/nfs/chess/raw/2023-3/id3a/berman-3804-a"

# change as needed
job_dir="/mnt/data1/nsdf/workflow/umich/jobs"

# where to temporary store jobs file (to be moved)
# I prefer not to write direcly to the jobs directory
tmp_dir="./tmp"


# TODO: far field too (this will get only tomo and nf)

num_found=0
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

    # no tiff files
    if not list(glob.glob(f"{dir}/*.tif")):
        continue

    body="""{
    "name": "${NAME}", 
    "src": "${experiment_dir}/nf_*.tif", 
    "metadata": [{"type": "chess-metadata", "query": {"Technique": "Tomography"}}]
}
""".replace("${NAME}",job_name).replace("${experiment_dir}",dir)

    # write the job in a temporary directory
    with open(f"{tmp_dir}/{job_name}.json","w") as f:
        f.write(body)

    # check syntax
    with open(f"{tmp_dir}/{job_name}.json","r") as f:
        json.load(f)

    num_found+=1

# User should be responsible to start the jobs
if num_found:
    print(f"found {num_found} new jobs to run")
    print(f"You need to run `mv {tmp_dir}/*.json {job_dir}/")
else:
    print("Did not find any new job to run")