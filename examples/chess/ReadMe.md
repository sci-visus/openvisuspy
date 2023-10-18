# Setup

NOTE:
- Connect to the NSDF entrypoint
- `OPEN FOLDER` `/mnt/data1/nsdf/openvisuspy`

# Update NSDF-CHESS OpenVisus Server

```bash

# this is to get env variables
source examples/chess/setup.sh

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
# CHESS visus config file (just an include)
__MODVISUS_CONFIG__=/nfs/chess/nsdf01/openvisus/lib64/python3.6/site-packages/OpenVisus/visus.config
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
tail -f  /var/log/httpd/*.log
```

See OpenVisus `Docker/group-security`` for details about how to add users


# Run NSDF Convert Workflow

Open **two terminals** on the NSDF entrypoint:

```bash

# OPTIONAL: activate conda if needed
conda activate my-env
conda info --envs

# OPTIONAL: use local openvisuspy code
export PYTHONPATH=${PWD}/src

# OPTIONAL: if you need to test modvisus. export `MODVISUS_USERNAME` and `MODVISUS_PASSWORD``
source "/nfs/chess/nsdf01/openvisus/.mod_visus.identity.sh"

# OPTIONAL: if you need PubSub. export `NSDF_CONVERT_PUBSUB_URL``
source "/nfs/chess/nsdf01/openvisus/.pubsub.sh"

# (OPTIONAL) if you need to retrieve CHESS metadata
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli
export NSDF_CONVERT_CHESSDATA_URI="https://chessdata.classe.cornell.edu:8244"

# this is the mandatory environment variables
export NSDF_CONVERT_GROUP=test-group-11
export MODVISUS_CONFIG=/nfs/chess/nsdf01/openvisus/lib64/python3.6/site-packages/OpenVisus/visus.config
export NSDF_CONVERT_DIR=/mnt/data1/nsdf-convert-workflow/${NSDF_CONVERT_GROUP}
export NSDF_CONVERT_REMOTE_URL_TEMPLATE="https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=${NSDF_CONVERT_GROUP}/{name}&cached=arco"

# init db: to call at the beginning of any group acquisition
function InitDb() {
   rm -Rf   ${NSDF_CONVERT_DIR}
   mkdir -p ${NSDF_CONVERT_DIR}
   python examples/chess/main.py init-db ${NSDF_CONVERT_GROUP}
   sqlite3 ${NSDF_CONVERT_DIR}/sqllite3.db "select * from datasets"
   rm -f /var/www/html/${NSDF_CONVERT_GROUP}.json
   ln -s ${NSDF_CONVERT_DIR}/dashboards.json /var/www/html/${NSDF_CONVERT_GROUP}.json
   curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"
}

# (DANGEROUS! since it remove the convert dir) 
# call once and only if you are sure
InitDb
```

Edit files in VSCode

```bash
code ${NSDF_CONVERT_DIR}/dashboards.json ${NSDF_CONVERT_DIR}/visus.config 
```


Check modvisus (you shoud see the new dataset):

```bash
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```

Check group configs:

```bash
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"
```

Rum local dashboard:

```bash
python -m bokeh serve examples/dashboards/app --dev --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" --prefer local
```

Run local puller (on all JSON files created in local directory):

```bash
python examples/chess/main.py run-puller "./*.json"
```

Check logs:

```bash
tail -f $NSDF_CONVERT_DIR/*.log
```


## Convert **TIFF image stack**

```
DATASET_NAME=example-image-stack
cat <<EOF > ./${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {
         "type": "chess-metadata", 
         "query": {
            "_id": "65032a84d2f7654ee374db59"
         } 
      }
   ]}
EOF

python examples/chess/main.py convert ./${DATASET_NAME}.json
```

## Convert **NEXUS**

```bash
DATASET_NAME=example-nexus
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/mnt/data1/nsdf/3scans_HKLI.nxs",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {"type": "file", "path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json"},
      {"type": "file", "path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par" }
   ]
}
EOF

python examples/chess/main.py convert ${DATASET_NAME}.json
```

## Convert **NEXUS reduced** 

```bash
DATASET_NAME=example-rolf-reduced
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/scratch/user/rv43/2023-2/id3a/shanks-3731-a/ti-2-exsitu/reduced/reduced_data.nxs",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {"type": "file", "path":"/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/retiga.yaml"},
      {"type": "file", "path":"/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/map.yaml" },
      {"type": "file", "path":"/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/pipeline.yaml"}
   ]}
EOF

python examples/chess/main.py convert ${DATASET_NAME}.json
```

## Convert **NEXUS reconstructed** 

```bash
DATASET_NAME=example-rolf-reconstructed
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/scratch/user/rv43/2023-2/id3a/shanks-3731-a/ti-2-exsitu/reduced/reconstructed_data.nxs",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {"type": "file", "path":"/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/retiga.yaml"},
      {"type": "file", "path":"/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/map.yaml" },
      {"type": "file", "path":"/nfs/chess/user/rv43/Tomo_Sven/shanks-3731-a/ti-2-exsitu/pipeline.yaml"}
   ]}
EOF

python examples/chess/main.py convert ${DATASET_NAME}.json
```

## Convert **numpy** 

```bash
DATASET_NAME=example-numpy
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/mnt/data1/nsdf/recon_combined_1_2_3_fullres.npy",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {"type": "file", "path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json"},
      {"type": "file", "path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par" }
   ]}
EOF

python examples/chess/main.py convert ${DATASET_NAME}.json
```

## Convert a **near field**

```bash
DATASET_NAME=example-near-field
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {"type": "file", "path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json"},
      {"type": "file", "path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par" }
   ]}
EOF

python examples/chess/main.py convert ${DATASET_NAME}.json
```

## Convert a **tomo**

```bash:

# 15: darkfield            W 2048 H 2048 D   26 dtype uint16
# 16: brightfield          W 2048 H 2048 D   26 dtype uint16
# 18: tomo rotation series W 2048 H 2048 D 1449 dtype uint16
# 19: darkfield            W 2048 H 2048 D   26 dtype uint16
# 20: brightfield          W 2048 H 2048 D   26 dtype uint16
SEQ=18 # 
DATASET_NAME="example-ti-2-exsitu-${SEQ}"
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/${SEQ}/nf/nf_*.tif",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {"type":"file","path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.json"},
      {"type":"file","path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.par"}
   ]
}
EOF

python examples/chess/main.py convert ${DATASET_NAME}.json
```

## PubSub puller

It runs until killed:

```
QUEUE=nsdf-convert-queue-${NSDF_CONVERT_GROUP}
python examples/chess/pubsub.py --action flush --queue ${QUEUE}
python examples/chess/main.py run-puller "${NSDF_CONVERT_PUBSUB_URL}" "${QUEUE}"
DATASET_NAME=pubsub-simple-test
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {
         "type": "chess-metadata", 
         "query": {
            "_id": "65032a84d2f7654ee374db59"
         } 
      }
   ]}
EOF

python ./examples/chess/pubsub.py --action pub --queue ${QUEUE} --message ./${DATASET_NAME}.json # send message to pubsub
```

# CHESS run-tracker

It runs once and must be a cron job:

```
DATASET_NAME=simple-test-local
cat <<EOF > ${DATASET_NAME}.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {
         "type": "chess-metadata", 
         "query": {
            "_id": "65032a84d2f7654ee374db59"
         } 
      }
   ]}
EOF
python examples/chess/main.py run-tracker "./*.json"
```



# Dashboards


## Windows

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;./src
set MODVISUS_USERNAME=xxxxx
set MODVISUS_PASSWORD=yyyyy
set VISUS_CPP_VERBOSE="1"
set VISUS_NETSERVICE_VERBOSE="1"
python -m bokeh serve examples/dashboards/app --dev --args C:\big\visus_datasets\chess\test-group\config.json
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/test-group.json"
```


## Linux

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

source .venv/bin/activate

# check you can reach the CHESS json file
curl -u $MODVISUS_USERNAME:$MODVISUS_PASSWORD https://nsdf01.classe.cornell.edu/test-group.json

# add `--dev` for debugging
export PYTHONPATH=./src
export BOKEH_ALLOW_WS_ORIGIN="*"
export BOKEH_LOG_LEVEL="info"

python -m bokeh serve examples/dashboards/app --dev --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" --prefer local
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"


python3 -m bokeh serve "examples/dashboards/app" \
   --allow-websocket-origin="*" \
   --address "$(curl -s checkip.amazonaws.com)" \
   --port 10334 \
   --args https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json
```


# CHESS Metadata


Once only:

```
kinit -f gscorzelli
ldapsearch sAMAccountName=$USER -LLL msDS-KeyVersionNumber 2>/dev/null | grep KeyVersionNumber | awk "{print $2}"
ktutil
addent -password -p gscorzelli@CLASSE.CORNELL.EDU -k KVNO -e aes256-cts-hmac-sha1-96
# type gscorzelli
# type <password>
# type wkt /home/gscorzelli/krb5_keytab
# type quit
ls -la ~/krb5_keytab
```

Then you can run the queries 
```
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache  -uri https://chessdata.classe.cornell.edu:8244 -query="pi:verberg"  | jq

# example
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query="{"technique": "tomography"}" |  jq  

# EMPTY, problem here?
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query="{"_id" : "65032a84d2f7654ee374db59"}" |  jq

# OK
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query="{"Description" : "Test for Kate"}" | jq
```

You can use the python client https://github.com/CHESSComputing/chessdata-pyclient`:

```
python -m pip install chessdata-pyclient

# modified /mnt/data1/nsdf/miniforge3/envs/my-env/lib/python3.9/site-packages/chessdata/__init__.py added at line 49 `verify=False`
# otherwise I need a certificate `export REQUESTS_CA_BUNDLE=`

kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli

python 
from chessdata import query, insert
records = query("""{"technique":"tomography"}""")
print(records)

insert("record.json", "test")
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
cat <<EOF > message.json
{"key1":"value1","key2":"value2"}
EOF

python ./examples/chess/pubsub.py --action pub --queue test-queue --message message.json
```

SUBSCRIBER - On Terminal 2:

```bash
python ./examples/chess/pubsub.py --action sub --queue test-queue
```

to flush a queue

```bash
python ./examples/chess/pubsub.py --action flush --queue test-queue
```
