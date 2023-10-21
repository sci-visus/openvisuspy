import os,sys,json

VISUS_CACHE=os.environ['VISUS_CACHE']

# should get a dashboard JSON file from stdin
# note it just print out the commands to execute
data = json.load(sys.stdin)
print("#!/bin/bash")
for dataset in data['datasets']:
	dataset_name=dataset["name"]
	src_urls=dataset["urls"]
	src_remote_url,src_local_url=[it['url'] for it in src_urls]
	src_local_url=os.path.dirname(src_local_url)
	# note IDX file must be created
	print(f"rclone sync chess1:{src_local_url} {VISUS_CACHE}/DiskAccess/nsdf01.classe.cornell.edu/443/zip/mod_visus/{dataset_name} -v --size-only --exclude='*.idx'")


