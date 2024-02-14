# Introduction


Landing page:

- https://nsdf01.classe.cornell.edu       (from outside CHESS)
- https://lnx-nsdf01.classe.cornell.edu   (from inside CHESS)

Dashboards (one per group):

- https://nsdf01.classe.cornell.edu/dashboards/app?group=${NSDF_GROUP}

Statistics (one per group):

- https://nsdf01.classe.cornell.edu/stats/${NSDF_GROUP}.html


## Run Convert Tracker (one per group)

In the first terminal, init the tracker:

```bash

# assuming to use a specific directory on the entrypoint
cd /mnt/data1/nsdf/openvisuspy

# **change the group name** as needed
export NSDF_GROUP="nsdf-group"

# creating a screen session is not strictly necessary, but allows to reconnect in case of problems
screen -S ${NSDF_GROUP}-tracker

# use the existing NSDF conda environment with all python packages installed
conda activate nsdf-env

# init kerberos ticket in case there is the need to get metadata from the CHESS metadata system
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache ${USER}

# create a function which creates a specific directory for the group
function init_tracker() {

   convert_dir=${1? Error need a directory argument}

   if [ -d ${convert_dir} ]; then

      read -p "Are you sure you want to remove directory=${convert_dir}? (Y/n) " yn
      case ${yn} in 
         Y ) 
            echo ok, we will proceed
            ;;
         * ) 
            echo "skipping"
            return;;
      esac

      # remove directory
      rm  -Rf ${convert_dir} 
   fi

   # create the conversion directory
   mkdir -p ${convert_dir}

   # create emtpy files
   touch "${convert_dir}/convert.log"
   touch "${convert_dir}/dashboards.log"
   touch "${convert_dir}/visus.group.config"
   touch "${convert_dir}/dashboards.json"

   # link the master visus config to the workflow directory (the tracker assume this name under the workflow folder)
   ln -f -s /mnt/data1/nsdf/OpenVisus/visus.config ${convert_dir}/visus.config #

   # add the dashboard json to Apache httpd so it can be served (for dashboards)
   group_name=$(basename ${convert_dir})
   ln  -f -s ${convert_dir}/dashboards.json ${WWW}/${group_name}.json 

   # make the job directory
   mkdir -p ${convert_dir}/jobs

   # create the db
   python  ./examples/chess/tracker.py create-db --convert-dir ${convert_dir} 
}

# call the function (NOTE:call the `init_tracker` just once since it will `rm -rf` any prexisting directory
init_tracker "/mnt/data1/nsdf/workflow/${NSDF_GROUP}"

# Apache HTTPD serves an HTML landing page here `https://nsdf01.classe.cornell.edu/`
# every time there is a new group, please add the group to the HTML
code /var/www/html/index.html 


# run the tracker
# the tracker is a loop which will watch for JSON jobs and automatically convert incoming data to OpenVisus data format
while [[ "1" == "1" ]] ; do
  python ./examples/chess/tracker.py run-loop --convert-dir "/mnt/data1/nsdf/workflow/${NSDF_GROUP}" --jobs "/mnt/data1/nsdf/workflow/${NSDF_GROUP}/jobs/*.json"
done
```

Edit the file `examples/chess/group_permissions.json` and setup the allowed LDAP group for each dashboard
- [dev] see `examples/chess/auth.py` file


If the tracker is up and running, just just copy the JSON jobs to `.workflow/${NSDF_GROUP}/jobs/`:

```bash
cp ./examples/chess/json/* .workflow/${NSDF_GROUP}/jobs/
```

If the tracker is NOT up and running, you can still run conversions manually. For example

```bash

# this is for 3a, it's a simple script which will scrape some directory for fields to convert
cp .workflow/umich/run-convert.py .workflow/${NSDF_GROUP}/

# this is for 4b, it's a simple script which will scrape some directory for fields to convert
# cp .workflow/pokharel-3828-a/run-convert.py .workflow/${NSDF_GROUP}/
```

Edit the `.workflow/${NSDF_GROUP}/run_convert.py` and change paths as needed.
You will need to change some paths.

Run `.workflow/${NSDF_GROUP}/run_convert.py`. Instructions will follow.


## Run Convert Statistics (one per group)

For each group you need to:

```bash

# change group name as needed
export NSDF_GROUP="nsdf-group"

# creating a screen session is not strictly necessary, but allows to reconnect in case of problems
screen -S ${NSDF_GROUP}-stats

# use the existing NSDF conda environment with all python packages installed
conda activate nsdf-env

# copy a staticis jupyter notebook template as a starter
# in general statistics are different depending on the beamline (e.g. 3a vs 4b) so you may want to start with something already created crfore
cp .workflow/umich/stats.ipynb .workflow/${NSDF_GROUP}/stats.ipynb

# *** Edit the notebook to point to the group directory *** 

# customize the statistics as needed

# continuos produce statistics, and copy the new stats to a directory that Apache HTTP can serve
while [[ "1" == "1" ]] ; do   
   jupyter nbconvert --to html .workflow/${NSDF_GROUP}/stats.ipynb --no-input --execute 
   mv .workflow/${NSDF_GROUP}/stats.html ${WWW}/stats/${NSDF_GROUP}.html
   sleep 30
done

```




## [DEV] NSDF directories


- `/mnt/data1/nsdf/`                 official nsdf directory on the entrypoint
- `/mnt/data1/nsdf/datasets`         some Visus datasets 
- `/mnt/data1/nsdf/miniforge3`       needed to get a recent version of Python (3.10)
- `/mnt/data1/nsdf/OpenVisus`        binaries used by httpd
- `/mnt/data1/nsdf/openvisuspy`      openvisuspy used by CHESS (branch chess-v0.1)
- `/mnt/data1/nsdf/openvisuspy-dev`  experimental new openvisus viewer
- `/mnt/data1/nsdf/examples`         some data needed for conversion
- `/mnt/data1/nsdf/workflow`         all the convert-workflow generated data (symbolic linked to .workflow)
- `/mnt/data1/nsdf/visus-cache`      openvisus cache if needed


## [ONCE ONLY] Run Dashboards

Note:
- now that a dashboard is serving all groups (the URL must contains the group argument i.e. https://nsdf01.classe.cornell.edu/dashboards/app?group=umich) there is no need to:
- `code /etc/nginx/nginx.conf` 
- `sudo /usr/bin/systemctl restart nginx`

```bash

# this is the screen to run all dashboards
screen -S all-dashboards

conda activate nsdf-env

# needed for AD security
export BOKEH_COOKIE_SECRET=$(echo $RANDOM | md5sum | head -c 32)

while [[ "1" == "1" ]] ; do
python -m bokeh serve examples/dashboards/app \
   --port 6011 \
   --use-xheaders \
   --allow-websocket-origin='*.classe.cornell.edu' \
   --dev \
   --auth-module=./examples/chess/auth.py \
   --args --prefer local
done
```

## [ONCE ONLY] Setup Conda env 

```bash

# avoid problems with screen command
cat <<EOF >~/.screenrc
defscrollback 100000
termcapinfo xterm* ti@:te@EOF
EOF

# TEST CHESS metadata (see `Setup` section below)
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='pi:verberg'                           | jq
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"technique": "tomography"}'          | jq
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"_id" : "65032a84d2f7654ee374db59"}' | jq
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"Description" : "Test for Kate"}'    | jq

# create a conda env
conda create --name nsdf-env  python=3.10  mamba
conda activate nsdf-env 

mamba install -c conda-forge pip numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2 nexusformat python-ldap filelock nbformat ipykernel plotly dash pandas nbconvert panel jupyter_bokeh  sqlalchemy 

# in case you need CBF file 
pip install fabio

# in case you need hexrd
mamba install -c hexrd -c conda-forge hexrd

python -m pip install OpenVisusNoGui
python -m pip install easyad

# see /mnt/data1/nsdf/miniforge3/envs/nsdf-env/lib/python3.10/site-packages/chessdata/__init__.py  line 49 if you need to disable `verify=False`
python -m pip install chessdata-pyclient

# for curl tests
conda env config vars set MODVISUS_USERNAME="xxxxx"
conda env config vars set MODVISUS_PASSWORD="yyyyy"

# for inline openvisuspy code modification
conda env config vars set PYTHONPATH="${PWD}/src"

# httpd root doc directory
conda env config vars set WWW="/var/www/html"

#  how to get data from the NSDF entrypoint
conda env config vars set REMOTE_URL_TEMPLATE="https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset={group}/{name}&cached=arco"

# (NEEDED by `auth.py`) for active directory CHESS authentication 
conda env config vars set AD_SERVER="ldap.classe.cornell.edu"
conda env config vars set AD_DOMAIN="CLASSE.CORNELL.EDU"

   # avoid problems with localhost (bokeh bug!)
conda env config vars set BOKEH_RESOURCES="cdn"

# to access chess metadata system
conda env config vars set NSDF_CONVERT_CHESSDATA_URI="https://chessdata.classe.cornell.edu:8244"

# otherwise CHESS metadata queries will not work
conda env config vars set REQUESTS_CA_BUNDLE="/etc/pki/tls/certs/nsdf01_classe_cornell_edu.pem"

# check all variables
conda env config vars list 

# is thi needed?
conda install ipykernel
```


## [DEV] Inspect the DB 

```bash

for group in $(ls .workflow/* -d1); do 
  todo=$(sqlite3 ${group}/sqllite3.db "SELECT count(*) from datasets WHERE conversion_start is     NULL")
  finished=$(sqlite3 ${group}/sqllite3.db "SELECT count(*) from datasets WHERE conversion_end   is NOT NULL")
  minutes=$(sqlite3 ${group}/sqllite3.db "SELECT (JULIANDAY( conversion_end) - JULIANDAY(conversion_start)) * 60*24 AS difference from datasets WHERE conversion_end is NOT NULL")
  echo ${group} todo $todo finished $finished 
  echo $minutes
  echo
done

```

## [DEV] Check if httpd and nginx are working

```bash
source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# check httpd is serving json dashboards and dataset list
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/nsdf-group.json"
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/mod_visus?action=list"

# [NGINX -> HTTPD] check JSON dashboards files and mod_visus are working
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/nsdf-group.json"
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```


## [BROKEN] Run Tracker Using crontab 

Disabled cronjob. ref Dan Riley

- *There's an issue with gmail rejecting cron jobs delivery reports from our systems that I'm working on finding a workaround.  Until then, if you have a non-gmail address we could use as your forwarding address, that would simplify things.  If not, please don't create any more every-minute cron jobs, as they're all generating mail that's ending up bouncing to postmaster.*

```bash 

# list cron jobs
crontab -l

# add / remove cronjob line 
# * * * * * /mnt/data1/nsdf/openvisuspy/examples/chess/<todo>.sh convert /mnt/data1/nsdf/workflow/nsdf-group
crontab -e
```


## [BROKEN] Run Dashboards Using systemd 

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

```

## [DEV] PubSub puller

```bash

# activate environment
source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# run PubSub puller (It runs until killed)
source "/nfs/chess/nsdf01/openvisus/.pubsub.sh"
QUEUE=nsdf-convert-queue-test
python examples/chess/pubsub.py --action flush      --url "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}"
python examples/chess/pubsub.py --action pub        --url "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}" --message ./examples/chess/puller/example.json 
```

## [DEV] Windows External Dashboards

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;./src
set MODVISUS_USERNAME=xxxxx
set MODVISUS_PASSWORD=yyyyy
set VISUS_CPP_VERBOSE="1"
set VISUS_NETSERVICE_VERBOSE="1"
python -m bokeh serve examples/dashboards/app --dev --args "C:\big\visus_datasets\chess\test-group\config.json"
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/test-group.json"
```

## [DEV] Linux External Dashboards

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
export WWW=/var/www/html
source .venv/bin/activate
EOF

source ./setup.sh

curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/nsdf-group.json"
curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=nsdf-group/nexus&cached=arco"

# this is for local debugging access
python -m bokeh serve examples/dashboards/app --dev --args "${WWW}/nsdf-group.json" --prefer local
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/nsdf-group.json"

# this is for public access
python3 -m bokeh serve "examples/dashboards/app" \
   --allow-websocket-origin="*" \
   --address "$(curl -s checkip.amazonaws.com)" \
   --port 10334 \
   --args https://nsdf01.classe.cornell.edu/nsdf-group.json

# in case you have a local json
python3 -m bokeh serve "examples/dashboards/app" \
   --allow-websocket-origin="*" \
   --address "$(curl -s checkip.amazonaws.com)" \
   --port 10334 \
   --args ./test-group-bitmask.json \
   --prefer local

```

# [DEV] Copy all blocks (must be binary compatible)

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

# [DEBUG] CHESS uppdate and debug mod_visus

- To enable multi-group security see [https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security](https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security
- See OpenVisus `Docker/group-security`` for details about how to add users

```bash

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# edit httpd file
code /etc/httpd/conf.d/openvisus.conf

#  configuration
code /etc/httpd/conf.d/ssl.conf

# using official CHESS python
which python3.6
python3.6 -m pip install --upgrade OpenVisusNoGui --target /mnt/data1/nsdf

# check if it works (NOTE libmodvisus will change sys.path so that it can do `import OpenVisuss`)
PYTHONPATH=/mnt/data1/nsdf python3.6 -c "import OpenVisus as ov"
PYTHONPATH=/mnt/data1/nsdf python3.6 -m OpenVisus dirname

# add `os.environ["VISUS_CPP_VERBOSE"]="1"` to see OpenVisus log (going to be resolved from 2.2.126)
# code /mnt/data1/nsdf/OpenVisus/__init__.py

# Restart the server
sudo /usr/bin/systemctl restart httpd

# Inspect apache logs
tail -f  /var/log/httpd/*

# check if it works
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"

# If you want to know more about mod_visus 
curl -vvvv --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=info"

# If you want to know more about apache status:
apachectl -S
```

To debug if `visus.config` is ok:

```bash
PYTHONPATH=/mnt/data1/nsdf python3.6

import os,sys
os.environ["VISUS_CPP_VERBOSE"]="1"
import OpenVisus as ov
config=ov.ConfigFile()
config.load("/mnt/data1/nsdf/OpenVisus/visus.config")
modvisus = ov.ModVisus()
modvisus.configureDatasets(config)
server=ov.NetServer(10000, modvisus)
server.runInThisThread()
```

## [DEV] CHESS Setup Kerberos for Metadata

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

