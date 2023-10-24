# Introduction

Forder is `/mnt/data1/nsdf/openvisuspy`

# Convert Workflow

## Setup conda env

```bash
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

# I need to update the master mod_visus config so new datasets are automatically added
conda env config vars set MODVISUS_CONFIG="/nfs/chess/nsdf01/openvisus/lib64/python3.6/site-packages/OpenVisus/visus.config"

# for active directory dashboards login
conda env config vars set AD_SERVER="ldap.classe.cornell.edu"
conda env config vars set AD_DOMAIN="CLASSE.CORNELL.EDU"

# needed only for remote dashboards
conda env config vars set VISUS_CACHE="/tmp/nsdf-convert-workflow/visus-cache"

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

## Group setup

```bash

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# change as needed
export NSDF_GROUP=test-group-bitmask
export NSDF_CONVERT_DIR=/mnt/data1/nsdf-convert-workflow/${NSDF_GROUP}

# create the directory which will contain all the files
mkdir -p ${NSDF_CONVERT_DIR}

# DANGEROUS and commented, I am assuming the convert dir is empty
# CHANGE PULLER PATTERN AS NEEDED
rm -Rf ${NSDF_CONVERT_DIR}/*
python examples/chess/main.py tracker-init ${NSDF_CONVERT_DIR} "${NSDF_CONVERT_DIR}/jobs/*.json"

# check if the group has been added to the master mod_visus config
code ${MODVISUS_CONFIG}

# run a simple conversion, just for debugging
# CHANGE PULLER PATTERN AS NEEDED
cp ./examples/chess/json/image-stack.json ${NSDF_CONVERT_DIR}/jobs/
./examples/chess/tracker.sh ${NSDF_CONVERT_DIR} 

# check json files have been renamed
ls -alF ${NSDF_CONVERT_DIR}/jobs/

# check on the database what happened
sqlite3 ${NSDF_CONVERT_DIR}/sqllite3.db "SELECT * FROM datasets;"

# check JSON dashboard and group mod_visus config
code ${NSDF_CONVERT_DIR}/visus.config
code ${NSDF_CONVERT_DIR}/dashboards.json

# ___________________________________________________

#  HTTPD ssl configuration
code /etc/httpd/conf.d/ssl.conf

# restart httpd
sudo /usr/bin/systemctl restart httpd

# make a link to the JSON dashboards into the httpd directory so it can be server
rm -f /var/www/html/${NSDF_GROUP}.json
ln -s ${NSDF_CONVERT_DIR}/dashboards.json /var/www/html/${NSDF_GROUP}.json

# check httpd
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/${NSDF_GROUP}.json"
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/mod_visus?action=list"

# ___________________________________________________

# edit configuration file
code /etc/nginx/nginx.conf

# restart NGINX
sudo /usr/bin/systemctl restart nginx

# check NGINX logs
tail -f "/var/log/nginx/access.log" /var/log/nginx/error.log

# [NGINX -> HTTPD] check JSON dashboards files and mod_visus are working
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_GROUP}.json"
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"

# [NGINX -> bokeh] dashboards
# *** this will fail if the dashboards is not running ***
#    WRONG:  <script type="text/javascript" src="http://0.0.0.0"     ...
#    WRONG:  <script type="text/javascript" src="http:/localhost"    ...
#    GOOD:   <script type="text/javascript" src="http://<servername> ...
curl -vvv -L "https://nsdf01.classe.cornell.edu/dashboards/${NSDF_GROUP}/app"

# Check convert logs
tail -f ${NSDF_CONVERT_DIR}/convert.log

# Check dashboards logs
tail -f ${NSDF_CONVERT_DIR}/dashboards.log
```

# Run Tracker

Switch between manual and auto run:

```bash 
source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# remove cronjob line 
crontab -e
crontab -l

# you can run conversion
cp ./examples/chess/json/image-stack.json ${NSDF_CONVERT_DIR}/jobs/

# add   cronjob line , this runs every min
# CHANGE AS NEEDED the `convert_dir` argument
# * * * * * /mnt/data1/nsdf/openvisuspy/examples/chess/tracker.sh /mnt/data1/nsdf-convert-workflow/test-group-bitmask
crontab -e
crontab -l
```

Check logs

```
tail -f ${NSDF_CONVERT_DIR}/convert.log
```

# Run Dashboards


NOTE: 
- systemd is configured by CHESS, and cannot be changed directly. 
- see FILE `/etc/systemd/system/chess-dashboard.service`


Switch between manual and auto run:

```bash
sudo systemctl stop chess-dashboard
./examples/chess/run-dashboards.sh
sudo systemctl start chess-dashboard
```

Check logs:

```bash
tail -f ${NSDF_CONVERT_DIR}/dashboards.log 
```



# PubSub puller

```bash

# activate environment
source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# run PubSub puller (It runs until killed)
source "/nfs/chess/nsdf01/openvisus/.pubsub.sh"
QUEUE=nsdf-convert-queue-test
python examples/chess/main.py flush      --url "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}"
python examples/chess/main.py pub        --url "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}" --message ./examples/chess/puller/example.json 
```


# Windows External Dashboards

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;./src
set MODVISUS_USERNAME=xxxxx
set MODVISUS_PASSWORD=yyyyy
set VISUS_CPP_VERBOSE="1"
set VISUS_NETSERVICE_VERBOSE="1"
python -m bokeh serve examples/dashboards/app --dev --args "C:\big\visus_datasets\chess\test-group\config.json"
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/test-group.json"
```

# Linux External Dashboards

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
screen -S nsdf-convert-workflow-dashboards

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install   numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2
python3 -m pip install --upgrade OpenVisusNoGui

curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/test-group-bitmask.json"
curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=test-group-bitmask/example-image-stack&cached=arco"

# this is for local debugging access
python -m bokeh serve examples/dashboards/app --dev --args "/var/www/html/test-group-bitmask.json" --prefer local
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/test-group-bitmask.json"

# this is for public access
python3 -m bokeh serve "examples/dashboards/app" \
   --allow-websocket-origin="*" \
   --address "$(curl -s checkip.amazonaws.com)" \
   --port 10334 \
   --args https://nsdf01.classe.cornell.edu/test-group-bitmask.json
```

# Copy all blocks (must be binary compatible)

```bash

# test connection
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=test-group-bitmask/example-near-field"

# Copy the blocks using rclone (better), Will work only if the dataset has been created with ARCO
ssh -i ~/.nsdf/vault/id_nsdf gscorzelli@chess1.nationalsciencedatafabric.org
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/test-group-bitmask.json" | python3 ./examples/chess/rclone-openvisus-datasets.py > ./rclone-openvisus-datasets.sh
chmod a+x ./rclone-openvisus-datasets.sh
././rclone-openvisus-datasets.sh

# Copy the blocks using OpenVisus API (deprecated)
export DATASET_NAME=test-group-bitmask/example-near-field
export VISUS_DISABLE_WRITE_LOCK=1
SRC="https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=${DATASET_NAME}&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"
DST="${VISUS_CACHE}/DiskAccess/nsdf01.classe.cornell.edu/443/zip/mod_visus/test-group-bitmask/example-near-field/visus.idx"
python3 -m OpenVisus copy-blocks --num-threads 4 --num-read-per-request 16 --verbose --src "${SRC}" --dst "${DST}"
unset VISUS_DISABLE_WRITE_LOCK
```

# Debug or update CHESS mod_visus

- To enable multi-group security see [https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security](https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security
- See OpenVisus `Docker/group-security`` for details about how to add users

```
# make sure you have the official python3 (i.e. not the miniforge one)

# I guess we installed a python3 in this directory (accordingly to the `dirname`)
export PATH=/nfs/chess/nsdf01/openvisus/bin/:${PATH}
/nfs/chess/nsdf01/openvisus/bin/python3 -m OpenVisus dirname
which python3
python3 -m OpenVisus dirname

# make a copy of mod_visus config before doing this, it will overwrite the file
__MODVISUS_CONFIG__=/nfs/chess/nsdf01/openvisus/lib64/python3.6/site-packages/OpenVisus/visus.config
cp ${__MODVISUS_CONFIG__} ${__MODVISUS_CONFIG__}.$(date +"%Y_%m_%d_%I_%M_%p").backup
python3 -m pip install --upgrade OpenVisusNoGui

# Restart the server
sudo /usr/bin/systemctl restart httpd

# check if it works
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"

# If you want to know more about apache status:
apachectl -S

# If you want to know more about mod_visus 
`curl -vvvv --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=info"

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

