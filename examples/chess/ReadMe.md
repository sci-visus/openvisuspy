# Setup

NOTE:
- Connect to the NSDF entrypoint
- `OPEN FOLDER` `/mnt/data1/nsdf/openvisuspy`

# Update NSDF-CHESS OpenVisus Server

```bash

# make sure you have the official python3 (i.e. not the miniforge one)

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
# conda info --envs

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
export NSDF_CONVERT_GROUP=test-group-bitmask
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

Some bash commands:

```bash

# Edit files in VSCode
code ${NSDF_CONVERT_DIR}/dashboards.json ${NSDF_CONVERT_DIR}/visus.config 

# Check modvisus (you shoud see the new dataset):
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"

# Check group configs:
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"

# Rum local dashboard:
python -m bokeh serve examples/dashboards/app --dev --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" --prefer local

# Run local puller (on all JSON files created in local directory):
python examples/chess/main.py run-puller "examples/chess/json/*.json"

# Check logs:
tail -f $NSDF_CONVERT_DIR/*.log

# Convert **TIFF image stack**
python examples/chess/main.py convert examples/chess/json/image-stack.json

# Convert **NEXUS**
python examples/chess/main.py convert examples/chess/json/nexus.json

# Convert **NEXUS reduced** 
python examples/chess/main.py convert examples/chess/json/rolf-reduced.json

# Convert **NEXUS reconstructed** 
python examples/chess/main.py convert rolf-reconstructed.json

# Convert **numpy** 
python examples/chess/main.py convert examples/chess/json/numpy.json

# Convert a **near field**
python examples/chess/main.py convert examples/chess/json/near-field.json

# Convert a **tomo**
python examples/chess/main.py convert examples/chess/json/ti-2-exsitu-18.json
```

## PubSub puller

It runs until killed:

```
QUEUE=nsdf-convert-queue-${NSDF_CONVERT_GROUP}
python examples/chess/main.py flush                                   --queue "${QUEUE}"
python examples/chess/main.py run-puller "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}" 
python examples/chess/main.py pub                                     --queue "${QUEUE}" --message ./examples/chess/puller/example.json 
```

# CHESS run-tracker

It runs once and must be a cron job:

```bash
python examples/chess/main.py run-tracker "exmples/chess/json/*.json"
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
sudo  apt install -y python3.10-venv rclone

# MANUALLY copy id_nsdf* to ~/.ssh and rename to /.ssh/id_rsa*

mkdir -p ~/.nsdf/vault/
cp ~/.ssh/id_rsa ~/.nsdf/vault/id_nsdf
chmod 700 ~/.ssh/* ~/.nsdf/vault/*

cat <<EOF >~/.screenrc
defscrollback 100000
termcapinfo xterm* ti@:te@EOF
EOF

# prepare for rclone
mkdir -p ~/.config/rclone/
cat << EOF > ~/.config/rclone/rclone.conf
[chess1]
type = sftp
host = chess1.nationalsciencedatafabric.org
user = gscorzelli
key_file = ~/.nsdf/vault/id_nsdf
EOF
chmod 700 ~/.config/rclone/rclone.conf

rclone lsd chess1:

mkdir -p github.com/sci-visus
cd github.com/sci-visus

git clone git@github.com:sci-visus/openvisuspy.git
cd openvisuspy

# if you are using cpython
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2
python3 -m pip install --upgrade OpenVisusNoGui

# if you are using conda/miniforge
conda create --name my-env  python=3.10  mamba
conda activate my-env 
mamba install -c conda-forge pip numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2 python-ldap 
python -m pip install OpenVisusNoGui
python -m pip install easyad

# create a screen session in case you want to keep it for debugging
screen -S nsdf-convert-workflow-dashboard

#  change as needed
cat <<EOF > ./setup.sh
export MODVISUS_USERNAME=xxxxx
export MODVISUS_PASSWORD=yyyyy

# to sign cookies
export BOKEH_COOKIE_SECRET=zzzz

# if you need Active Directory auth
export AD_SERVER="ldap.classe.cornell.edu"
export AD_DOMAIN="CLASSE.CORNELL.EDU"

export VISUS_CACHE=/tmp/nsdf-convert-workflow/visus-cache
export NSDF_CONVERT_GROUP=test-group-bitmask
export PYTHONPATH=./src
export BOKEH_ALLOW_WS_ORIGIN="*"
export BOKEH_LOG_LEVEL="debug"
export BOKEH_PORT=10334

# important to avoid bokeh response "localhost.."
# https://github.com/bokeh/bokeh/issues/13170
export BOKEH_RESOURCES=cdn  

source .venv/bin/activate
EOF

source ./setup.sh

# check you can reach the CHESS json file
curl -u $MODVISUS_USERNAME:$MODVISUS_PASSWORD https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json
curl -u $MODVISUS_USERNAME:$MODVISUS_PASSWORD "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=${NSDF_CONVERT_GROUP}/example-image-stack&cached=arco"

# this is for local debugging access
python -m bokeh serve examples/dashboards/app --dev --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" --prefer local
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"

# this is for public access
python3 -m bokeh serve "examples/dashboards/app" \
   --allow-websocket-origin="*" \
   --address "$(curl -s checkip.amazonaws.com)" \
   --port ${BOKEH_PORT} \
   --args https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json
```


## CHESS specific dashboard, NGINX, httpd

**IMPORTANT (READ CAREFULLY step by step)**
- **Do `source setup.sh` to setup your env**
- MAKE SURE VSCODE IS NOT FOWARDING PORTS OTHERWISE IS DIFFICULT TO DEBUG
- you need to run the bokeh dashboard to have links working
- now HTTPD is listening on port 8443
- NGINX disabled http to avoid collisions with httpd
- NGINX and httpd are using the same ssl certificates
- without `export BOKEH_RESOURCES=cdn` it will not work and you will get bokeh problems with localhost (https://github.com/bokeh/bokeh/issues/13170)

```
NGINX:443 

   # https://nsdf01.classe.cornell.edu/hello
   /hello        (BOKEH TEST DASHBOARD) PORT 5006

   # https://nsdf01.classe.cornell.edu/app
   /app          (BOKEH NSDF DASHBOARD) PORT 5007
   /app/login
   /app/logout

   <anything else will go to nsdf01.classe.cornell.edu:8443> (HTTPD)
```

hpttd configuration:

```bash

# change ports as needed
code /etc/httpd/conf.d/ssl.conf

# restart
sudo /usr/bin/systemctl restart httpd

# NOTE: the following will work only inside the CHESS network since port 8443 is not exposed outside

# check if mod_visus is working
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/mod_visus?action=list"

# check is json files are accessible
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/${NSDF_CONVERT_GROUP}.json"

```

nginx configuration:

```bash

# edit configuration file
code /etc/nginx/nginx.conf

# restart nginx
sudo /usr/bin/systemctl restart nginx

# if you want ot check the logs
tail -f "/var/log/nginx/access.log" /var/log/nginx/error.log

# check modvisus connecting directly to httpd
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}"  https://nsdf01.classe.cornell.edu:8443/mod_visus?action=list
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/test-group-bitmask.json"

# access mod_visus via nginx
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}"  "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/test-group-bitmask.json"

# run a simple hello
python -m bokeh serve examples/chess/hello.py --port 5006 --use-xheaders --dev --allow-websocket-origin='nsdf01.classe.cornell.edu'

# OPEN URL in a browser outside CHESS
# https://nsdf01.classe.cornell.edu/hello

# connect to the dashboard directly (and check `<script type="text/javascript" src="https://cdn.bokeh.org/...`)
curl -vvv -L http://localhost:5006/hello

# check from outside chess or OPEN THE URL in a brower
curl -vvv -L https://nsdf01.classe.cornell.edu/hello

# run dashboard
python -m bokeh serve examples/dashboards/app \
   --port 5007 \
   --use-xheaders \
   --allow-websocket-origin='nsdf01.classe.cornell.edu' \
   --dev  \
   --auth-module=./examples/chess/chess_auth.py \
   --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" \
   --prefer local

# OPEN URL in a browser outside CHESS
# https://nsdf01.classe.cornell.edu/app

```

## Debug Bokeh problems


Check if this is returning <script with the right address

```bash
curl -vvv "http://chpc3.nationalsciencedatafabric.org:10334/run"

# if you get this, it is WRONG:
#   <script type="text/javascript" src="http://0.0.0.0:10334/static/js/bokeh-widgets" ... />

# if you get this, then GOOD:
#   <script type="text/javascript" src="static/js/bokeh.min.js?v=" ... />

# if you get this, then GOOD:
#   <script type="text/javascript" src="http://<servername>/...static/js/bokeh.min.js?v=  " ... />
```


## Copy all blocks (must be binary compatible)

Rest if permissions works


```bash
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=test-group-bitmask/example-near-field"
```

### Copy the blocks using OpenVisus API (deprecated)

```bash
export DATASET_NAME=test-group-bitmask/example-near-field
export VISUS_DISABLE_WRITE_LOCK=1
SRC="https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=${DATASET_NAME}&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"
DST="${VISUS_CACHE}/DiskAccess/nsdf01.classe.cornell.edu/443/zip/mod_visus/test-group-bitmask/example-near-field/visus.idx"
python3 -m OpenVisus copy-blocks --num-threads 4 --num-read-per-request 16 --verbose --src "${SRC}" --dst "${DST}
unset VISUS_DISABLE_WRITE_LOCK
```

### Copy the blocks using rclone (better)

NOTE:
- Will work only if the dataset has been created with ARCO

```bash
# check if the identity is working
ssh -i ~/.nsdf/vault/id_nsdf gscorzelli@chess1.nationalsciencedatafabric.org
```

Create a script to get a list of all datasets:

```bash
cat <<EOF > rclone-all.py
import os,sys,json
VISUS_CACHE=os.environ['VISUS_CACHE']
data = json.load(sys.stdin)
print("#!/bin/bash")
for dataset in data['datasets']:
	dataset_name=dataset["name"]
	src_urls=dataset["urls"]
	src_remote_url,src_local_url=[it['url'] for it in src_urls]
	src_local_url=os.path.dirname(src_local_url)
	# note IDX file must be created
	print(f"rclone sync chess1:{src_local_url} {VISUS_CACHE}/DiskAccess/nsdf01.classe.cornell.edu/443/zip/mod_visus/{dataset_name} -v --size-only --exclude='*.idx'")
EOF
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json" | python3 rclone-all.py > rclone-all.sh

chmod a+x rclone-all.sh 
./rclone-all.sh
```


# NGINX

You can run `nginx` in Docker:
- NOTEL sharing the network so it's easier to debug
- see the *.conf file
- `httpd` configuration file is in `/etc/httpd/conf.d/ssl.conf`

```bash

#if you change any path, change proxy.conf too

CER_FILE=/etc/pki/tls/certs/nsdf01_classe_cornell_edu_cert.cer
KEY_FILE=/etc/pki/tls/private/nsdf01.classe.cornell.edu.key
sudo docker run --name mynginx1 --rm --network host \
   -v ${PWD}/examples/chess/nginx/proxy.conf:/etc/nginx/nginx.conf \
   -v ${CER_FILE}:${CER_FILE} \
   -v ${KEY_FILE}:${KEY_FILE} \
   nginx 
```

Test if you can reach either httpd and nginx from another shell:

```bash

# to be changed (NGNIX should be listening on 443 and httpd on )
HTTPD_URL=https://nsdf01.classe.cornell.edu:443
NGINX_URL=https://nsdf01.classe.cornell.edu:8443

# httpd 
curl  -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} ${HTTPD_URL}/
curl  -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} ${NGINX_URL}
curl  -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} ${NGINX_URL}/mod_visus?action=list
curl  -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} ${NGINX_URL}/${NSDF_CONVERT_GROUP}.json
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


# Debug Jupyter Notebooks/Visual Studio Code problems

When you open Jupyter Notebooks.,..
You should see `my-env` as a Python Kernel on the top-right of the Visual code
If you do not see it, do:

```
conda install ipykernel
python -m ipykernel install --user --name my-env --display-name "my-env" and

conda activate my-env

# then just `Reload` in Visual Code, it should detect the `my-env` conda environment now
```

