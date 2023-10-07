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
NSDF_CONVERT_GROUP=test-group-99
source examples/chess/setup.sh

# if you need to update OpenVisus
# python -m pip install --upgrade OpenVisusNoGui
# git pull
```

Group setup:

```bash
rm -Rf ${NSDF_CONVERT_DATA}
rm -f ${NSDF_CONVERT_GROUP_CONFIG}
mkdir -p ${NSDF_CONVERT_DATA}
touch ${NSDF_CONVERT_MODVISUS_CONFIG}
python ./examples/chess/pubsub.py --action flush --queue ${NSDF_CONVERT_QUEUE}
python examples/chess/convert.py init-db

# MANUAL OPERATION
# Add this to ${MODVISUS_CONFIG} (do not remove the group, otherwise it will not work)
# <group name="${NSDF_CONVERT_MODVISUS_CONFIG}"><include url='/mnt/data1/nsdf-convert-workflow/${NSDF_CONVERT_MODVISUS_CONFIG}/visus.config' /></group> 


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

# for CHESS metadata
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli

DATASET_NAME=test-now-3
python ./examples/chess/pubsub.py --action pub --queue ${NSDF_CONVERT_QUEUE} --message "{
   'group': '${NSDF_CONVERT_GROUP}',
   'name':'${DATASET_NAME}',
   'src':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif',
   'dst':'${NSDF_CONVERT_DATA}/${DATASET_NAME}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type': 'chess-metadata', 'query': '{\"BTR\": \"1111-a\"}' }, 
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
   'metadata': [
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json'},
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par' },
   ]}"
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

- [FIXED] 2 views, 2 datasets
- [FIXED] probe - viewport problem (ratio)
- [FIXED] remove the targes on show/hide probes
- [FIXED] add colormap to child Slice
- [FIXED] offset in logic vs physic coordinates
- [FIXED] bokeh button stylesheet
- [TODO] bokeh -export and import status
- [TODO] TODO: Tabs 1 simple viewer, 2 double dataset, 3 probe 

- 
```
python -m bokeh serve examples/dashboards/app --dev --args ${NSDF_CONVERT_GROUP_CONFIG}
```

Example of import-export, maybe a schema could be this:

```
{
  "datasets": [
    {
      "name" : "name to show in the list box",
      "url" : "url for loaddataset", 
      "color-mapper-type": "linear",
      "resolution" : 24,
      "physic-box": [[-3.0,3.0],[-7.0,7.0],[-7.0,7.0]],
      "palette": "Viridis256",
      "palette-range" : [0.0,100.0],
      "num-views": 1,
      "timestep": 0,
      "timestep-delta": 1,
      "field" : "DATA",
      "num-refinements" : 2,
      "view-dep" : true,
      "show-options" : [["palette","show-probe"],["offset","direction"]],

      "direction" : 2,
      "offset": 3.1,
      "viewport" : [[-1.0,1.0],[-3.0,3.0]],

      "children" : [

		],

      "probes": [
        {
          "direction": 2,
          "color": "red",
          "pos": [1.0,4.0],
        }
      ],
     "metadata" : [
        {"type": "json-object", "filename": "generated-nsdf-convert.json",  "object": {} },
        {"type": "b64encode", "filename": "...", "encoded": "xxxxx="}
      ]
    }
  ]
}
```

To add:

```

diff --git a/src/openvisuspy/probes.py b/src/openvisuspy/probes.py
index f098636..d071b61 100644
--- a/src/openvisuspy/probes.py
+++ b/src/openvisuspy/probes.py
@@ -36,8 +36,10 @@ class ProbeTool(Slice):
 	colors = ["lime", "red", "green", "yellow", "orange", "silver", "aqua", "pink", "dodgerblue"] 
 

 		N=len(self.colors)
@@ -96,6 +98,37 @@ class ProbeTool(Slice):
 			self.slider_z_op = RadioButtonGroup(labels=["avg","mM","med","*"], active=0)
 			self.slider_z_op.on_change("active",lambda attr,old, new: self.refreshAll()) 	
 
+	# getProbes
+	def getProbes(self):
+		ret=[]
+		for dir in range(3):
+			for probe in self.probes[dir]:
+				if probe.pos is not None and probe.enabled:
+					ret.append(
+						{
+							"direction": dir,
+							"pos": probe.pos
+
+							# TODO....not sure this is the right level...
+							# "range" : [self.slider_z_range.start,self.slider_z_range.end],
+							# "res" : self.slider_z_res.value,
+							# "op": self.slider_z_op.value,
+							# "num_points": self.slider_num_points.value
+						}
+					)
+		return ret
+
+	# setProbes
+	def setProbes(self,value):
+		self.disableAllProbes()
+		for it in value:
+			dir,pos,color=it["direction"],it["pos"],it["color"]
+			slot=self.colors.index(color)
+			assert(slot>=0 and slot<len(self.colors))
+			probe=self.probes[dir][slot]
+			probe.pos=pos
+			self.enableProbe(probe)
+		self.updateButtons()
 
 	# updateButtons
 	def updateButtons(self):
@@ -152,6 +185,12 @@ class ProbeTool(Slice):
 		probe.enabled=False
 		self.updateButtons()
 
+	# disableAllProbes
+	def disableAllProbes(self):
+		for dir in range(3):
+			for probe in self.probes[dir]:
+				self.disableProbe(self)
+	

-  
 	# getQueryLogicBox
 	def getQueryLogicBox(self):
-		x1,y1,x2,y2=self.canvas.getViewport()
+		(x1,x2),(y1,y2)=self.canvas.getViewport()
 		return self.toLogic([(x1,y1),(x2,y2)])
 
 	# setQueryLogicBox (NOTE: it ignores the coordinates on the direction)
 	def setQueryLogicBox(self,value,):
 		logger.info(f"[{self.id}]::setQueryLogicBox value={value}")
 		proj=self.toPhysic(value) 
-		self.canvas.setViewport(*(proj[0] + proj[1]))
+		x1,y1,x2,y2=proj[0] + proj[1]
+		self.setViewport([[x1,x2],[y1,y2]])
 		self.refresh()
   

+
+# getViewport
+def getViewport(self):
+	return self.canvas.getViewport() if self.canvas is not None else [(0,0),(0,0)]
+
+# setViewport
+def setViewport(self,value):
+	self.canvas.setViewport(value) if self.canvas is not None else None
+
-

"name":name, "url": name }]})
@@ -351,8 +385,9 @@ class Widgets:
 		self.setDirections(axis)
 
 		# physic box
-		physic_box=self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
-		physic_box=[(float(physic_box[I]),float(physic_box[I+1])) for I in range(0,pdim*2,2)]
+		default_physic_box=self.db.inner.idxfile.bounds.toAxisAlignedBox().toString().strip().split()
+		default_physic_box=[(float(physic_box[I]),float(physic_box[I+1])) for I in range(0,pdim*2,2)]
+		physic_box=config.get("physic-box", default_physic_box)
 		self.setPhysicBox(physic_box)
 
 		# field
@@ -364,9 +399,13 @@ class Widgets:
 		self.setField(field.name) 
   
 		# direction
-		self.setDirection(2)
-		for I,it in enumerate(self.children):
-			it.setDirection((I % 3) if pdim==3 else 2)
+		direction=config.get("direction",2)
+		self.setDirection(direction)
+
+		# offset
+		offset=config.get("offset",None)
+		if offset is not None:
+			self.setOffset(offset)
 
 		# palette 
 		palette=config.get("palette","Viridis256")
@@ -399,13 +438,53 @@ class Widgets:
 		self.setNumberOfRefinements(num_refinements)
 
 		# metadata
-		metadata=config.get("metadata",None)
-		if metadata:
+		self.setMetadata(config.get("metadata",None))
+
+		# show_options
+		show_options=config.get("show-options",None)
+		if show_options:
+			self.setShowOptions(show_options)
+
+		# view_mode
+		view_mode=config.get("view-mode",None)
+		if view_mode:
+			self.setViewMode(view_mode)
+
+		# viewport
+		viewport=config.get("viewport",None)
+		if viewport is not None:
+			self.setViewport(viewport)
+
+		# probes
+		probes=config.get("probes",None)
+		if probes is not None:
+			self.setProbes(probes)
+
+		self.refresh() 
+
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
ldapsearch sAMAccountName=$USER -LLL msDS-KeyVersionNumber 2>/dev/null | grep KeyVersionNumber | awk '{print $2}'
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
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"technique": "tomography"}' |  jq  

# EMPTY, problem here?
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"_id" : "65032a84d2f7654ee374db59"}' |  jq

# OK
/nfs/chess/sw/chessdata/chess_client -krbFile ~/krb5_ccache -uri https://chessdata.classe.cornell.edu:8244 -query='{"Description" : "Test for Kate"}' | jq
```

You can use the python client https://github.com/CHESSComputing/chessdata-pyclient`:

```
python -m pip install chessdata-pyclient

# modified /mnt/data1/nsdf/miniforge3/envs/my-env/lib/python3.9/site-packages/chessdata/__init__.py added at line 49 `verify=False`
# otherwise I need a certificate `export REQUESTS_CA_BUNDLE=`

kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli

python 
from chessdata import query, insert
records = query('{"technique":"tomography"}')
print(records)

insert('record.json', 'test')
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
