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
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;./src
set MODVISUS_USERNAME=xxxxx
set MODVISUS_PASSWORD=yyyyy
python -m bokeh serve examples/dashboards/app --dev --args C:\big\visus_datasets\chess\test-group\config.json
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/test-group-2.json"
```

# Run NSDF Convert Workflow

Open **two terminals** on the NSDF entrypoint and type:

```bash
export NSDF_CONVERT_GROUP=test-group-33
source examples/chess/setup.sh

# if you need to update OpenVisus
# python -m pip install --upgrade OpenVisusNoGui
# git pull
```

Group setup:

```bash

# remove the OLD group convert directory
rm -Rf ${NSDF_CONVERT_DIR}

# local
python examples/chess/convert.py convert-loop init "./*.json" 

# PubSub
python examples/chess/convert.py convert-loop init pubsub
```

if you want to debut the db:

```bash
sqlite3 ${NSDF_CONVERT_DIR}/sqllite3.db ".schema"
sqlite3 ${NSDF_CONVERT_DIR}/sqllite3.db "select * from datasets"
```

Init Kerberos ticket for CHESS metadata system:

```
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli
```

To run a **single convert**:

```
DATASET_NAME=test-now-33
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
   ]
}
EOF
python ./examples/chess/convert.py run-single-convert ${DATASET_NAME}.json
```

Convert an **image-stack** using loop:

```bash
DATASET_NAME=test-now-3
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

# loop using local storage
python examples/chess/convert.py convert-loop run "./*.json"

# loop using PubSub
python examples/chess/convert.py convert-loop run pubsub
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_PUBSUB_QUEUE} --message ./${DATASET_NAME}.json

```

Add **NEXUS**:

```bash
DATASET_NAME=example-nexus
cat <<EOF > job.json
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

python examples/chess/convert.py run-single-convert job.json
```

Add **NEXUS reduced** example:

```bash
DATASET_NAME=rolf-example-reduced
cat <<EOF > job.json
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
python examples/chess/convert.py run-single-convert job.json
```

Add **NEXUS reconstructed** example:

```bash
DATASET_NAME=rolf-example-reconstructed
cat <<EOF > job.json
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
python examples/chess/convert.py run-single-convert job.json
```

Add **numpy** data:

```
DATASET_NAME=example-numpy
cat <<EOF > job.json
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
python examples/chess/convert.py run-single-convert job.json
```

Add a **near field**:

```bash
DATASET_NAME=example-near-field
cat <<EOF > job.json
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
python examples/chess/convert.py run-single-convert job.json
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
cat <<EOF > job.json
{
   "group": "${NSDF_CONVERT_GROUP}",
   "name":"${DATASET_NAME}",
   "src":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/${Seq}/nf/nf_*.tif",
   "dst":"${NSDF_CONVERT_DIR}/data/${DATASET_NAME}/visus.idx",
   "compression":"zip",
   "arco":"1mb",
   "metadata": [
      {"type":"file","path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.json"},
      {"type":"file","path":"/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.par"}
   ]
}
EOF
python examples/chess/convert.py run-single-convert job.json
```

Check modvisus (you shoud see the new dataset):

```bash
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```

Check group configs:

```
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"
```

```
python -m bokeh serve examples/dashboards/app --dev --args ${NSDF_CONVERT_GROUP_CONFIG}
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
export ADDRESS=$(curl -s checkip.amazonaws.com)
export BOKEH_PORT=10334

source .venv/bin/activate
export NSDF_CONVERT_GROUP=test-group

# check you can reach the CHESS json file
curl -u $MODVISUS_USERNAME:$MODVISUS_PASSWORD https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json

# add `--dev` for debugging
python3 -m bokeh serve "examples/dashboards/app" --allow-websocket-origin="*" --address "${ADDRESS}" --port ${BOKEH_PORT} --args https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json
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
