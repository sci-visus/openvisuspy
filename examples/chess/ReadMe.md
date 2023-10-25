# Introduction

Directories

```bash

# official nsdf directory on the entrypoint
/mnt/data1/nsdf/

# needed to get a recent version of Python (3.10)
/mnt/data1/nsdf/miniforge3

# binaries used by httpd
/mnt/data1/nsdf/OpenVisus

# directory for inline editing of code (vscode open folder)
/mnt/data1/nsdf/openvisuspy

# some data needed for conversion
/mnt/data1/nsdf/examples

# all the convert-workflow generated data
/mnt/data1/nsdf/workflow

# openvisu cache if needed
/mnt/data1/nsdf/visus-cache
```


# Convert Workflow Group setup

Note: here I am assuming that some env variables are already configured in the conda env. 
See `Setup conda env` section below about how configure an environment

Setup a screen session for the tracker:

```bash

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# needed by tracker and group dependent
export NSDF_GROUP=nsdf-group
export NSDF_CONVERT_DIR=/mnt/data1/nsdf/workflow/${NSDF_GROUP}
export NSDF_TRACKER_GLOB="${NSDF_CONVERT_DIR}/jobs/*.json"

for it in $(screen -ls | grep tracker-${NSDF_GROUP} | awk '{print $1}'); do 
   screen -S ${it} -X kill
done
screen -S tracker-${NSDF_GROUP}
```

Prepare for group conversions

```bash

# change group as needed
screen -d -r  tracker-nsdf-group

# (!!!) DANGEROUS, do only when you know group directory is NOT IMPORTANT 
rm -Rf ${NSDF_CONVERT_DIR}/*
mkdir -p ${NSDF_CONVERT_DIR}
ln -s /mnt/data1/nsdf/OpenVisus/visus.config ${NSDF_CONVERT_DIR}/visus.config 

# init
python  ./examples/chess/tracker.py init

# make a link to the JSON dashboards into the httpd directory so it can be server
rm -f /var/www/html/${NSDF_GROUP}.json
ln -s ${NSDF_CONVERT_DIR}/dashboards.json /var/www/html/${NSDF_GROUP}.json

# check httpd (should be already working)
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/${NSDF_GROUP}.json"
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/mod_visus?action=list"

# [NGINX -> HTTPD] check JSON dashboards files and mod_visus are working
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_GROUP}.json"
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```

Run some conversion:


```bash
# inplace conversion (NOTE: it will not update `visus.group.config``)
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli
python  ./examples/chess/tracker.py "./examples/chess/json/image-stack-1.json"

# run some conversions with the tracker loop (NOTE: it will update `visus.group.config``)
python ./examples/chess/tracker.py  loop # | next | <N>
cp "./examples/chess/json/image-stack-1.json" $(dirname ${NSDF_TRACKER_GLOB})/
```

Set Dashboards screen session:

```bash

export NSDF_GROUP=nsdf-group
export NSDF_CONVERT_DIR=/mnt/data1/nsdf/workflow/${NSDF_GROUP}

# note: this must be the same of nginx
export BOKEH_PORT=5007

# remove old screen session
for it in $(screen -ls | grep dashboards-${NSDF_GROUP} | awk '{print $1}'); do 
   screen -S ${it} -X kill
done

# create a new screen session
screen -S dashboards-${NSDF_GROUP}

# so that I not need to setup again
source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# run dashboard (change port as needed; each group will have its own port)
export OPENVISUSPY_DASHBOARDS_LOG_FILENAME=${NSDF_CONVERT_DIR}/dashboards.log
```

Next time:

```

# edit configuration file, and **add the group app for the choosen port**
code /etc/nginx/nginx.conf

# restart NGINX to get the new bokeh app exposed
sudo /usr/bin/systemctl restart nginx

# change as needed
screen -r -d dashboards-nsdf-group

# run bokeh
python -m bokeh serve examples/dashboards/app \
   --port ${BOKEH_PORT} \
   --use-xheaders \
   --allow-websocket-origin='nsdf01.classe.cornell.edu' \
   --dev \
   --auth-module=./examples/chess/auth.py \
   --args "${NSDF_CONVERT_DIR}/dashboards.json" \
   --prefer local

# https://nsdf01.classe.cornell.edu/dashboards/nsdf-group/app
```


# (BROKEN) Run Tracker Using crontab 


```bash 

# list cron jobs
crontab -l

# add / remove cronjob line 
# * * * * * /mnt/data1/nsdf/openvisuspy/examples/chess/tracker.sh convert /mnt/data1/nsdf/workflow/nsdf-group
crontab -e
```


# (BROKEN) Run Dashboards Using systemd 

NOTE: 
- systemd is configured by CHESS, and cannot be changed directly. 
- how to have one dashboard per group?
- see FILE `/etc/systemd/system/chess-dashboard.service`

Switch between manual and auto run:

```bash
sudo systemctl stop chess-dashboard

# manual run for debugging
./examples/chess/run-dashboards.sh

sudo systemctl start chess-dashboard

# Check logs:
tail -f ${NSDF_CONVERT_DIR}/dashboards.log 
```


## CHESS/NSDF Setup Conda env

```bash

# avoid problems with screen command
cat <<EOF >~/.screenrc
defscrollback 100000
termcapinfo xterm* ti@:te@EOF
EOF

conda create --name nsdf-env  python=3.10  mamba
conda activate nsdf-env 
mamba install -c conda-forge pip numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2 nexusformat python-ldap filelock
python -m pip install OpenVisusNoGui
python -m pip install easyad
python -m pip install chessdata-pyclient

# setup your environment, choose what needs to be kepy/modified
conda env config vars set MODVISUS_USERNAME="xxxxx"
conda env config vars set MODVISUS_PASSWORD="yyyyy"

# this is for bokeh dashboards if you need security (like Active Directory)
conda env config vars set BOKEH_COOKIE_SECRET="zzzzz"

# modify the openvisuspy code inline
conda env config vars set PYTHONPATH="${PWD}/src"

# for external dashboards, I need to know how to produce the JSON file with 'remote'
conda env config vars set REMOTE_URL_TEMPLATE="https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset={group}/{name}&cached=arco"

# for active directory dashboards login
conda env config vars set AD_SERVER="ldap.classe.cornell.edu"
conda env config vars set AD_DOMAIN="CLASSE.CORNELL.EDU"

# needed only for remote dashboards
conda env config vars set VISUS_CACHE="/mnt/data1/nsdf/visus-cache"

# avoid problems with localhost (bokeh bug!)
conda env config vars set BOKEH_RESOURCES="cdn"

# check all variables
conda env config vars list 

# TEST CHESS metadata (see `Setup` section below)
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='pi:verberg'                           | jq
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"technique": "tomography"}'          | jq
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"_id" : "65032a84d2f7654ee374db59"}' | jq
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"Description" : "Test for Kate"}'    | jq
```

# (OLD) PubSub puller

```bash

# activate environment
source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# run PubSub puller (It runs until killed)
source "/nfs/chess/nsdf01/openvisus/.pubsub.sh"
QUEUE=nsdf-convert-queue-test
python examples/chess/pubsub.py --action flush      --url "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}"
python examples/chess/pubsub.py --action pub        --url "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}" --message ./examples/chess/puller/example.json 
```

# Windows Dashboards

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;./src
set MODVISUS_USERNAME=xxxxx
set MODVISUS_PASSWORD=yyyyy
set VISUS_CPP_VERBOSE="1"
set VISUS_NETSERVICE_VERBOSE="1"
python -m bokeh serve examples/dashboards/app --dev --args "C:\big\visus_datasets\chess\test-group\config.json"
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/test-group.json"
```

# Linux Dashboards

Example about how to setup an external dashboards (getting data from chess and caching it):

```bash

# ASSUMING ubuntu 22 here
sudo apt update
sudo apt install -y python3.10-venv rclone

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

# create a screen session in case you want to keep it for debugging
screen -S nsdf-dashboards

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install   numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2
python3 -m pip install --upgrade OpenVisusNoGui

# TODO HERE
# setup all the environment variables
cat <<EOF > ./setup.sh
export MODVISUS_USERNAME="xxxxx"
export MODVISUS_PASSWORD="yyyyy"
export PYTHONPATH="./src"
export VISUS_CACHE="/tmp/visus-cache"
export BOKEH_RESOURCES="cdn"
export BOKEH_ALLOW_WS_ORIGIN="*"
export BOKEH_LOG_LEVEL="debug"
export OPENVISUSPY_DASHBOARDS_LOG_FILENAME"/tmp/openvisuspy/logs.dashboards.log"
source .venv/bin/activate
EOF

source ./setup.sh

curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/nsdf-group.json"
curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=nsdf-group/example-image-stack&cached=arco"

# this is for local debugging access
python -m bokeh serve examples/dashboards/app --dev --args "/var/www/html/nsdf-group.json" --prefer local
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/nsdf-group.json"

# this is for public access
python3 -m bokeh serve "examples/dashboards/app" \
   --allow-websocket-origin="*" \
   --address "$(curl -s checkip.amazonaws.com)" \
   --port 10334 \
   --args https://nsdf01.classe.cornell.edu/nsdf-group.json
```

# Copy all blocks (must be binary compatible)

```bash

# test connection
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=nsdf-group/example-near-field"

# Copy the blocks using rclone (better), Will work only if the dataset has been created with ARCO
ssh -i ~/.nsdf/vault/id_nsdf gscorzelli@chess1.nationalsciencedatafabric.org
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/nsdf-group.json" | python3 ./examples/chess/rclone.py > ./rclone.sh
chmod a+x ./rclone.sh
././rclone.sh

# Copy the blocks using OpenVisus API (deprecated)
export DATASET_NAME=nsdf-group/example-near-field
export VISUS_DISABLE_WRITE_LOCK=1
SRC="https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=${DATASET_NAME}&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"
DST="${VISUS_CACHE}/DiskAccess/nsdf01.classe.cornell.edu/443/zip/mod_visus/nsdf-group/example-near-field/visus.idx"
python3 -m OpenVisus copy-blocks --num-threads 4 --num-read-per-request 16 --verbose --src "${SRC}" --dst "${DST}"
unset VISUS_DISABLE_WRITE_LOCK
```

# CHESS mod_visus

- To enable multi-group security see [https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security](https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security
- See OpenVisus `Docker/group-security`` for details about how to add users

```bash

# edit httpd file
code /etc/httpd/conf.d/openvisus.conf

#  configuration
code /etc/httpd/conf.d/ssl.conf

# using official CHESS python
which python3.6
python3.6 -m pip install --upgrade OpenVisusNoGui --target /mnt/data1/nsdf
ls -alF /mnt/data1/nsdf/OpenVisus/bin/libmod_visus.so

PYTHONPATH=/mnt/data1/nsdf python3.6 -m OpenVisus dirname

# Restart the server
sudo /usr/bin/systemctl restart httpd

# check if it works
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"

# If you want to know more about mod_visus 
curl -vvvv --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=info"

# If you want to know more about apache status:
apachectl -S

# Inspect apache logs
tail -f  /var/log/httpd/*.log
```


# Setup Kerberos for CHESS Metadata system

Setup *persistent* kerneros tickets:

```bash
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

