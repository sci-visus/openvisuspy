# Setup

NOTE:
- COnnect to the NSDF entrypoint
- `OPEN FOLDER` `/mnt/data1/nsdf/openvisuspy`



Please check the body of the `setup.sh` file since it contains some useful explanations:

```bash
source examples/chess/setup.sh
```


# Handle with Jupyter notebook/Visual Studio Code problems

When you open Jupyter Notebooks.,..
You should see `my-env` as a Python Kernel on the top-right of the Visual code
If you do not see it, do:

```
conda install ipykernel
python -m ipykernel install --user --name my-env --display-name "my-env" and

# so that the terminal is configured properly
source examples/chess/setup.sh

# then just `Reload` in Visual Code, it should detect the `my-env` conda environment now
```

# Update OpenVisus

```bash

# I do not want the conda one
conda deactivate || true

# I guess we installed a python3 in this directory (accordingly to the `dirname`)
export PATH=/nfs/chess/nsdf01/openvisus/bin/:${PATH}
/nfs/chess/nsdf01/openvisus/bin/python3 -m OpenVisus dirname
which python3

python3 -m OpenVisus dirname

# ******************************************
# *** IMPORTANT **** make a copy of ${MODVISUS_CONFIG} before doing this, it will overwrite the file
# ******************************************
cp ${MODVISUS_CONFIG} ${MODVISUS_CONFIG}.$(date +"%Y_%m_%d_%I_%M_%p").backup
python3 -m pip install --upgrade OpenVisusNoGui

## mod_visus 

To enable multi-group security see [https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security](https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security

Restart the server

```bash
sudo /usr/bin/systemctl restart httpd

curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```

If you want to know more about apache status:

```bash
apachectl -S
```

If you want to know more about mod_visus 

```bash
`curl -vvvv --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=info"
```

Inspect apache logs

```bash
tail -f  ${APACHE_LOG_DIR}/*.log
```

See OpenVisus `Docker/group-security`` for details about how to add users


# Dashboard 

NOTE:
- ports are not opened to the outside, but visual code can automatically forward them (just ffor debugging)
- if you are on the CHESS entrypoint, debugging with VSCode, **you will need to remove** `--adress 0.0.0.0` (it cannot bind to the public IP)

Without group config:

```bash
python3 -m bokeh serve "examples/dashboards/run.py" --dev --address 0.0.0.0 --port 10077 --args "/mnt/data1/nsdf/visus-datasets/allison-1110-3-mg4al-sht-11-nf/visus.idx"
```


To test from inside CHESS network:
- change port as needed

```bash
ssh -i ~/.nsdf/vault/id_nsdf lnx201.classe.cornell.edu
curl -L "http://lnx-nsdf01.classe.cornell.edu:10077/run"
```

If you want to test from outside CHESS network you need to use ssh-tunneling.

But if you are on Windows VS Code, ports are automaticall forward and you can open (change port as needed) `http://localhost:10077/run`


# Convert workflow


Open two temintals and:

```bash
NSDF_CONVERT_GROUP=test-group
source examples/chess/setup.sh
```

Group setup:

```bash
rm -Rf ${NSDF_CONVERT_DATA}
rm -f ${NSDF_CONVERT_GROUP_CONFIG}
mkdir -p ${NSDF_CONVERT_DATA}
touch ${NSDF_CONVERT_MODVISUS_CONFIG}

# MANUAL OPERATION
echo "Add this to ${MODVISUS_CONFIG} : <include url='${NSDF_CONVERT_MODVISUS_CONFIG}' />"

pushd $(dirname ${NSDF_CONVERT_GROUP_CONFIG})
git commit -a -m "cleaning"
git push
popd

python ./examples/chess/pubsub.py --action flush --queue ${NSDF_CONVERT_QUEUE}
python examples/chess/convert.py init-db
sqlite3 ${NSDF_CONVERT_SQLITE3_FILENAME} ".schema"
sqlite3 ${NSDF_CONVERT_SQLITE3_FILENAME} "select * from datasets"

python examples/chess/convert.py generate-modvisus-config
more ${NSDF_CONVERT_MODVISUS_CONFIG}
```

In terminal 1, run the converter loop

```bash
python examples/chess/convert.py run-convert-loop
```

In terminal 2, convert an **image-stack**:

```bash

DATASET_NAME=example-$(date +"%Y_%m_%d_%I_%M_%p")
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json'},
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par' }
   ]}"
```

Check modvisus (you shoud see the new dataset):

```bash
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list&group=${NSDF_CONVERT_GROUP}" | grep ${NSDF_CONVERT_GROUP}
```

And check group configs:

```
curl ${NSDF_CONVERT_GROUP_CONFIG_REMOTE}
```


Also you can run the dashboard:

```
python -m bokeh serve examples/dashboards/run.py --dev --args ${NSDF_CONVERT_GROUP_CONFIG_REMOTE}
```

On CHPC, you can SSH to CHPC1, OpenFolder `github.com/sci-visus/openvisuspy`:
- change group as needed

```
python3 -m pip uninstall openvisuspy
python3 -m pip install --upgrade OpenVisus boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2
git pull
set PYTHONPATH=./src
python3 -m bokeh serve "examples/dashboards/run.py" --dev --address 0.0.0.0 --port 10077 --args https://raw.githubusercontent.com/nsdf-fabric/chess-convert-workflow/main/test-group.json
# http://chpc1.nationalsciencedatafabric.org:10077/run
```

Add a **near field**:

```bash
DATASET_NAME=example-$(date +"%Y_%m_%d_%I_%M_%p")
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json'},
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par' }
   ]}"
```

Add a **tomo**

```bash:
seq=18 # 
# 15: darkfield            W 2048 H 2048 D   26 dtype uint16
# 16: brightfield          W 2048 H 2048 D   26 dtype uint16
# 18: tomo rotation series W 2048 H 2048 D 1449 dtype uint16
# 19: darkfield            W 2048 H 2048 D   26 dtype uint16
# 20: brightfield          W 2048 H 2048 D   26 dtype uint16

Seq=18
DATASET_NAME="example-$(date +"%Y_%m_%d_%I_%M_%p")/${Seq}"
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/${Seq}/nf/nf_*.tif',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type':'file','path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.json'},
      {'type':'file','path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.par'},
   ]}"
```





# (OLD NOTES) PubSub

Links:
- https://customer.cloudamqp.com/instance
- https://www.cloudamqp.com/docs/index.html
- https://www.cloudamqp.com/docs/python.html

Little Lemur - For deplyment is Free

PUBLISHER - On Terminal 1:

```bash
python ./examples/chess/pubsub.py --action pub --queue test-queue --message '{"key1":"value1","key2":"value2"}'
```

SUBSCRIBER - On Terminal 2:

```bash
python ./examples/chess/pubsub.py --action sub --queue test-queue
```

to flush a queue

```bash
python ./examples/chess/pubsub.py --action flush --queue test-queue
```
