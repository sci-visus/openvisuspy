import glob,os,sys,json

# change as needed
experiment_dir="/nfs/chess/id4b/2023-3/gopalan-3842-a"

# change as needed
job_dir="/mnt/data1/nsdf/workflow/gopalan/jobs"

# where to temporary store jobs file (to be moved)
# I prefer not to write direcly to the jobs directory
tmp_dir="./tmp"

# extension
ext=".cbf"

# TODO: far field too (this will get only tomo and nf)

dirs=sorted(list(set([os.path.dirname(it) for it in glob.glob(f"{experiment_dir}/**/*{ext}",recursive=True)])))

num_found=0
for dir in dirs:

    job_name="-".join(dir.split("/")[len(experiment_dir.split("/")):])

    
    # already done
    if list(glob.glob(f"{job_dir}/{job_name}.json*")):
        continue

    # no files
    if not list(glob.glob(f"{dir}/*{ext}")):
        continue

    body="""{
    "name": "{job_name}", 
    "src": "{experiment_dir}/*{ext}" 
}
""".replace("{job_name}",job_name).replace("{experiment_dir}",dir).replace("{ext}",ext)

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