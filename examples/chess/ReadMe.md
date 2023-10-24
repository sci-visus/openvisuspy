# Setup

Forder is `/mnt/data1/nsdf/openvisuspy`

# Convert Workflow

**Before starting**:
- edit the file `setup.sh` to change the group

Prepare for the group acquisition:

```bash
if [[ "${NSDF_CONVERT_DIR}" == "" ]] ; then 
   echo "WRONG, missing NSDF_CONVERT_DIR" ; 
fi

# create the directory which will contain all the files
mkdir -p ${NSDF_CONVERT_DIR}

# DANGEROUS and commented, I am assuming the convert dir is empty
# rm -Rf   ${NSDF_CONVERT_DIR}/*

# creates the sqllite3 db; add an item to the master mod_visus config; create a group mod_visus config 
python examples/chess/main.py init-group ${NSDF_CONVERT_GROUP}

# if you want to check the db
sqlite3 ${NSDF_CONVERT_DIR}/sqllite3.db "select * from datasets"

# check JSON dashboard file
code ${NSDF_CONVERT_DIR}/dashboards.json 

# check master mod_visus config
code ${MODVISUS_CONFIG}

# check group mod_visus config
code ${NSDF_CONVERT_DIR}/visus.config 

# make a link to the JSON dashboard into the httpd directory so it can be server
rm -f /var/www/html/${NSDF_CONVERT_GROUP}.json
ln -s ${NSDF_CONVERT_DIR}/dashboards.json /var/www/html/${NSDF_CONVERT_GROUP}.json

# check proxy pass to NGINX for the group
code /etc/nginx/nginx.conf
# restart nginx
sudo /usr/bin/systemctl restart nginx
echo "https://nsdf01.classe.cornell.edu/dashboards/${NSDF_CONVERT_GROUP}/app"

# restart httpd (not needed)
# sudo /usr/bin/systemctl restart httpd

# check httpd is working
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"

# check NGINX app

```

Afer that you can do:


```bash

source ./setup.sh


# Check all logs
tail -f ${NSDF_CONVERT_DIR}/*.log

# Connect to modvisus  (this goes NGINX->http)
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"

# Check group configs (this goes NGINX->http)
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"

```


## CHESS Tracker

TODO:
- what happens when a conversion fails? discuss with Glenn

See file `./examples/chess/run-tracker.sh`

Check logs

```
tail -f ${NSDF_CONVERT_DIR}/convert.log
```

Manually run:
- cron job line: `* * * * * /mnt/data1/nsdf/openvisuspy/examples/chess/run-tracker.sh`

```
crontab -e
# remove cronjob line 

# run manually
./examples/chess/run-tracker.sh

crontab -e
# add   cronjob line 

```


## CHESS Dashboards 

See file `examples/chess/run-dashboards.sh`

Check logs:

```bash
tail -f /mnt/data1/nsdf-convert-workflow/test-group-bitmask/dashboards.log 
```

Manually run for debugging:

```bash
sudo systemctl stop chess-dashboard
./examples/chess/run-dashboards.sh
sudo systemctl start chess-dashboard
```


## Other convert commands

```bash

# Run local puller (on all JSON files created in local directory):
python examples/chess/main.py run-puller "examples/chess/json/*.json"

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

# run PubSub puller (It runs until killed)
QUEUE=nsdf-convert-queue-${NSDF_CONVERT_GROUP}
python examples/chess/main.py flush                                   --queue "${QUEUE}"
python examples/chess/main.py run-puller "${NSDF_CONVERT_PUBSUB_URL}" --queue "${QUEUE}" 
python examples/chess/main.py pub                                     --queue "${QUEUE}" --message ./examples/chess/puller/example.json 
```

# External Dashboards


## Windows

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;./src
set MODVISUS_USERNAME=xxxxx
set MODVISUS_PASSWORD=yyyyy
set VISUS_CPP_VERBOSE="1"
set VISUS_NETSERVICE_VERBOSE="1"
python -m bokeh serve examples/dashboards/app --dev --args "C:\big\visus_datasets\chess\test-group\config.json"
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/test-group.json"
```

## Linux

Example about how to setup an external dashboard (getting data from chess and caching it):

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

# if you are using cpython
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2 nexusformat flock
python3 -m pip install --upgrade OpenVisusNoGui

# if you are using conda/miniforge
conda create --name my-env  python=3.10  mamba
conda activate my-env 
mamba install -c conda-forge pip numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh==3.2.2 python-ldap  nexusformat flock
python -m pip install OpenVisusNoGui
python -m pip install easyad

# create a screen session in case you want to keep it for debugging
screen -S nsdf-convert-workflow-dashboard

#  change as needed
cat <<EOF > ./setup.sh
export MODVISUS_USERNAME=xxxxx
export MODVISUS_PASSWORD=yyyyy
export VISUS_CACHE=/tmp/nsdf-convert-workflow/visus-cache
export PYTHONPATH=./src
export BOKEH_ALLOW_WS_ORIGIN="*"
export BOKEH_LOG_LEVEL="debug"
export BOKEH_RESOURCES=cdn  
source .venv/bin/activate
EOF

source ./setup.sh

export NSDF_CONVERT_GROUP=test-group-bitmask

# check you can reach the CHESS json file
curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"
curl -u ${MODVISUS_USERNAME}:${MODVISUS_PASSWORD} "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=${NSDF_CONVERT_GROUP}/example-image-stack&cached=arco"

# this is for local debugging access
python -m bokeh serve examples/dashboards/app --dev --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" --prefer local
python -m bokeh serve examples/dashboards/app --dev --args "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json"

# this is for public access
python3 -m bokeh serve "examples/dashboards/app" \
   --allow-websocket-origin="*" \
   --address "$(curl -s checkip.amazonaws.com)" \
   --port 10334 \
   --args https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json
```


[OPTIONAL] Copy all blocks (must be binary compatible)

```bash

# test connection
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=test-group-bitmask/example-near-field"

# Copy the blocks using rclone (better)
# Will work only if the dataset has been created with ARCO
ssh -i ~/.nsdf/vault/id_nsdf gscorzelli@chess1.nationalsciencedatafabric.org
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/${NSDF_CONVERT_GROUP}.json" | python3 ./examples/chess/rclone-openvisus-datasets.py > ./rclone-openvisus-datasets.sh
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

# Dev notes

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

## Debug Jupyter Notebooks/Visual Studio Code problems

When you open Jupyter Notebooks.,..
You should see `my-env` as a Python Kernel on the top-right of the Visual code
If you do not see it, do:

```
conda install ipykernel
python -m ipykernel install --user --name my-env --display-name "my-env" and

conda activate my-env

# then just `Reload` in Visual Code, it should detect the `my-env` conda environment now
```


## Debug CHESS HTTPD

hpttd:

```bash

source setup.sh

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

## Debug or update mod_visus

- To enable multi-group security see [https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security](https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security
- See OpenVisus `Docker/group-security`` for details about how to add users

```
# make sure you have the official python3 (i.e. not the miniforge one)

# I guess we installed a python3 in this directory (accordingly to the `dirname`)
export PATH=/nfs/chess/nsdf01/openvisus/bin/:${PATH}
/nfs/chess/nsdf01/openvisus/bin/python3 -m OpenVisus dirname
which python3
python3 -m OpenVisus dirname

# make a copy of ${MODVISUS_CONFIG} before doing this, it will overwrite the file
__MODVISUS_CONFIG__=/nfs/chess/nsdf01/openvisus/lib64/python3.6/site-packages/OpenVisus/visus.config
cp ${MODVISUS_CONFIG} ${MODVISUS_CONFIG}.$(date +"%Y_%m_%d_%I_%M_%p").backup
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

## Debug NGINX

```bash

source setup.sh

# edit configuration file
code /etc/nginx/nginx.conf

# restart nginx
sudo /usr/bin/systemctl restart nginx

# check the logs
tail -f "/var/log/nginx/access.log" /var/log/nginx/error.log

# check modvisus connecting directly to httpd
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/mod_visus?action=list"
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu:8443/test-group-bitmask.json"

# connect using nginx proxy
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
curl -vvv -L --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/test-group-bitmask.json"

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
   --auth-module=./examples/chess/auth.py \
   --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" \
   --prefer local

# OPEN IN A BROWSER 
echo "Open in a browser https://nsdf01.classe.cornell.edu/app"
```

## CHESS Metadata system

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




