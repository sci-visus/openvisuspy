# Setup

NOTE:
- Connect to the NSDF entrypoint
- `OPEN FOLDER` `/mnt/data1/nsdf/openvisuspy`
- run `source examples/chess/setup.sh` in your terminal

# Update NSDF-CHESS OpenVisus Server

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

# Debug dashboard on windows

```

python -m bokeh serve examples/dashboards/run.py --dev --args C:\visus_datasets\chess\3scans_HKLI\3scans_HKLI.counts.idx
```

# Run NSDF Convert Workflow

Open **two terminals** on the NSDF entrypoint and type:

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

DATASET_NAME=example-tiff-image-stack
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


Add **NEXUS**:

```bash
DATASET_NAME=example-nexus
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/mnt/data1/nsdf/3scans_HKLI.nxs',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': []}"
```

Add **NEXUS reduced** example:

```bash
DATASET_NAME=rolf-example-reduced
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/nfs/chess/scratch/user/rv43/2023-2/id3a/shanks-3731-a/ti-2-exsitu/reduced/reduced_data.nxs',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type': 'file', 'path':'/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/retiga.yaml'},
      {'type': 'file', 'path':'/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/map.yaml' },
      {'type': 'file', 'path':'/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/pipeline.yaml' },
   ]}"
```

Add **NEXUS reconstructed** example:

```bash
DATASET_NAME=rolf-example-reconstructed
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/nfs/chess/scratch/user/rv43/2023-2/id3a/shanks-3731-a/ti-2-exsitu/reduced/reconstructed_data.nxs',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type': 'file', 'path':'/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/retiga.yaml'},
      {'type': 'file', 'path':'/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/map.yaml' },
      {'type': 'file', 'path':'/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/pipeline.yaml' },
   ]}"
```

Add **numpy** data:

```
DATASET_NAME=example-numpy
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/mnt/data1/nsdf/recon_combined_1_2_3_fullres.npy',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json'},
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par' }
   ]}"
```

Add a **near field**:

```bash
DATASET_NAME=example-near-field
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

Add a **tomo** (is it TOMO?)

```bash:
seq=18 # 
# 15: darkfield            W 2048 H 2048 D   26 dtype uint16
# 16: brightfield          W 2048 H 2048 D   26 dtype uint16
# 18: tomo rotation series W 2048 H 2048 D 1449 dtype uint16
# 19: darkfield            W 2048 H 2048 D   26 dtype uint16
# 20: brightfield          W 2048 H 2048 D   26 dtype uint16
Seq=18
DATASET_NAME="example-ti-2-exsitu/${Seq}"
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

Check modvisus (you shoud see the new dataset):

```bash
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```

Check group configs:

```
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"
```

Also you can run the dashboard:

- [DONE] fix problem with number of view changes (e.g. 3->1) 
- [DONE] range mode (*)  from metadata (*) user range (*) dynamic (*) dynamic-acc
- [DONE] palette choose between linear and log
- [DONE] METADATA
- [DONE] add *axis name*
- [DONE] colormap looses ticks
- [DONE] probe working
```
python -m bokeh serve examples/dashboards/run.py --dev --args ${NSDF_CONVERT_GROUP_CONFIG}
```

# Setup a new Dashboard Server

```bash

# ASSUMING ubuntu 22 here
sudo apt update
sudo  apt install -y python3.10-venv 

# MANUALLY copy id_nsdf* to ~/.ssh and rename to /.ssh/id_rsa*
chmod 700 ~/.ssh/id_rsa*

cat <<EOF >~/.screenrc
defscrollback 100000
termcapinfo xterm* ti@:te@EOF
EOF

mkdir -p github.com/sci-visus
cd github.com/sci-visus

git clone git@github.com:sci-visus/openvisuspy.git
cd openvisuspy

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2
python3 -m pip install --upgrade OpenVisusNoGui

screen -S nsdf-convert-workflow-dashboard
# screen -ls
# screen -r  2092897.nsdf-convert-workflow-dashboard  
# echo $STY 

# change as needed
export MODVISUS_USERNAME=xxxxx
export MODVISUS_PASSWORD=yyyyy
export VISUS_CACHE=/tmp/nsdf-convert-workflow/visus-cache
export VISUS_CPP_VERBOSE="1"
export VISUS_NETSERVICE_VERBOSE="1"
export BOKEH_ALLOW_WS_ORIGIN="*"
export BOKEH_LOG_LEVEL="info"
export PYTHONPATH=./src
export ADDRESS=$(curl -s https://ifconfig.me)
export BOKEH_PORT=10334 

source .venv/bin/activate
export NSDF_CONVERT_GROUP=test-group

# check you can reach the CHESS json file
curl -u $MODVISUS_USERNAME:$MODVISUS_PASSWORD https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json

# add `--dev` for debugging
python3 -m bokeh serve "examples/dashboards/run.py" --use-xheaders   --allow-websocket-origin="*" --address "${ADDRESS}" --port ${BOKEH_PORT} --args https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json
```


# CHESS Metadata

- `"DataLocationMeta": "/nfs/chess/aux/cycles/2023-2/id3a/shanks-3731-a/ti-2-exsitu/"` **500 files**

```
kinit -c krb5_ccache $USER 

# example
/nfs/chess/sw/chessdata/chess_client -krbFile krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"technique": "tomography"}' |  jq  

# EMPTY, problem here?
/nfs/chess/sw/chessdata/chess_client -krbFile krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"_id" : "65032a84d2f7654ee374db59"}' |  jq

# OK
/nfs/chess/sw/chessdata/chess_client -krbFile krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"Description" : "Test for Kate"}' | jq
```


## Debug Bokeh problems

Check if this is returning <script with the right address

```
curl -vvv "http://chpc3.nationalsciencedatafabric.org:10334/run"


# WRONG
<script type="text/javascript" src="http://0.0.0.0:10334/static/js/bokeh-widgets      WRONG

# GOOD
<script type="text/javascript" src="static/js/bokeh.min.js?v=

# GOOD
<script type="text/javascript" src="http://<servername>/...static/js/bokeh.min.js?v=  
```


# Debug Jupyter Notebooks/Visual Studio Code problems

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


# Simple PubSub

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
