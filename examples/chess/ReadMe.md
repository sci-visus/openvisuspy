# CHESS Examples


## Setup

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
python3 -m pip install --upgrade OpenVisusNoGui
```

## mod_visus 

To enable multi-group security see [https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security](https://github.com/sci-visus/OpenVisus/tree/master/Docker/mod_visus/group-security

- [TO-ASK] rights to edit `${APACHE_PASSWORD_FILE}`
- [TO-ASK] rights to edit `${APACHE_OPENVISUS_CONF_FILE}`
- [TO-ASK] rights to view `${APACHE_LOG_DIR}/*.log`
- [TO-ASK] rights to write on `/mnt/data/nsdf` (e.g. `rm -Rf  /mnt/data1/nsdf/remove-me` permission denied) 


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


## Streamable NEXUS


Run the `convert-nexus-data.ipynb` to convert data to a streamable format 
- metadata will still be in the NEXUS file
- volumetric big data will be automatically stored in a OpenVisus file

To show the data in a bokeh dashboard

```bash
set PYTHONPATH=./src;C:\projects\OpenVisus\build\RelWithDebInfo
python -m bokeh serve examples/dashboards/run.py --dev --args --dataset C:/visus_datasets/3scans_HKLI.streamable.nxs  --num-views 1 --color-mapper log --palette Viridis256 
```


## Dashboard DEMO

NOTE:
- ports are not opened to the outside, but visual code can automatically forward them (just ffor debugging)

```bash
BOKEH_PORT=10077 
DST=/mnt/data1/nsdf/visus-datasets/allison-1110-3-mg4al-sht-11-nf/visus.idx
python3 -m bokeh serve "examples/dashboards/run.py" \
   --dev --address 0.0.0.0 --port ${BOKEH_PORT} --args \
   --dataset "${DST}" \
   --palette Viridis256  \
   --palette-range "[0, 70]" \
   --multi
```

```bash
PANEL_PORT=10077
DST=/mnt/data1/nsdf/visus-datasets/chess/recon_combined_1_fullres/modvisus/zip/visus.idx
python3 -m panel serve "examples/dashboards/run.py"  \
   --dev --address 0.0.0.0 --port ${PANEL_PORT} --args \
   --dataset "${DST}" \
   --palette Viridis256  \
   --palette-range "[-0.017141795, 0.012004322]" \
   --multi
```

To test from inside CHESS network:
- change port as needed

```bash
ssh -i ~/.nsdf/vault/id_nsdf lnx201.classe.cornell.edu
curl -L "http://lnx-nsdf01.classe.cornell.edu:10077/run"
```

If you want to test from outside CHESS network you need to use ssh-tunneling.

But if you are on Windows VS Code, ports are automaticall forward and you can open (change port as needed) `http://localhost:10077/run`

# PubSub

Links:
- https://customer.cloudamqp.com/instance
- https://www.cloudamqp.com/docs/index.html
- https://www.cloudamqp.com/docs/python.html

Little Lemur - For deplyment is Free

On Terminal 1:

```bash
python ./examples/chess/pubsub.py --action pub --queue my-queue --message '{"key1":"value1","key2":"value2"}'
```

On Terminal 2:

```bash
python ./examples/chess/pubsub.py --action sub --queue my-queue
```

to flush a queue

```bash
python ./examples/chess/pubsub.py --action flush --queue my-queue
```


## Run single image-stack conversion

```bash
python examples/chess/convert.py  \
   --src "/nfs/chess/nsdf01/vpascucci/allison-1110-3/mg4al-sht/11/nf/*.tif" \
   --dst "/mnt/data1/nsdf/tmp/merif2023/timeseries/tiff/visus.idx" \
   --compression raw \
   --arco modvisus
```

# Convert Workflow

Reset the convert queues and db:

```bash
python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_IN}
python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_OUT}
python examples/chess/convert.py init-db
```

Note: the db schema is:

```sql
CREATE TABLE IF NOT EXISTS datasets (
   id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
   
   name TEXT NOT NULL,
   src TEXT NOT NULL,
   dst TEXT NOT NULL,
   compression TEXT,
   arco TEXT,

   insert_time timestamp NOT NULL, 
   conversion_start timestep ,
   conversion_end   timestamp 
)
```

Show the convert db

```bash

# .schema  datasets;
sqlite3 ${CONVERT_SQLITE3_FILENAME} "select * from datasets;" ".exit"
```

Convert the db to a `convert.config`


```bash
python examples/chess/convert.py dump-datasets
more ${VISUS_CONVERT_CONFIG}
```

Send an event for image-stack conversion 

```bash


for i in {1..5} ; do
python ./examples/chess/pubsub.py --action pub --queue ${CONVERT_QUEUE_IN} --message "{
   'name':'my-chess-group-${i}',
   'src':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif',
   'dst':'/mnt/data1/nsdf/tmp/remove-me/my-chess-group-${i}/visus.idx',
   'compression':'zip',
   'arco':'1mb'}"
done

# still the db is empty if the converter is not running
sqlite3 ${CONVERT_SQLITE3_FILENAME} "select * from datasets;" ".exit"
```

In terminal 2 watch for event in out queue:

```bash
python ./examples/chess/pubsub.py --action sub  --queue ${CONVERT_QUEUE_OUT}
```

In terminal 1, run the converter loop

```bash
python examples/chess/convert.py run-convert-loop
```

Soon or later the NSDF OpenVisus server will serve it:

```bash
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```


# 20231209 Near field

Specs:

```
W 2048 H 2048 D 366 dtype uint16
```

```bash

python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_IN}
python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_OUT}
python examples/chess/convert.py init-db

name="scrgiorgio-near-field-20230912-01"
python ./examples/chess/pubsub.py --action pub --queue ${CONVERT_QUEUE_IN} --message "{
   'name':'${name}',
   'src':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/21/nf/nf_*.tif',
   'dst':'/mnt/data1/nsdf/tmp/${name}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.json'},
      {'type': 'file', 'path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_nf_scan_layers-retiga-ti-2-exsitu.par' }
   ]}"

python examples/chess/convert.py run-convert-loop
```

# 20231209 Tomo

Specs:

```
# W 2048 H 2048 D 26 dtype uint16 dtype uint16
# 15: darkfield            W 2048 H 2048 D   26 dtype uint16
# 16: brightfield          W 2048 H 2048 D   26 dtype uint16
# 18: tomo rotation series W 2048 H 2048 D 1449 dtype uint16
# 19: darkfield            W 2048 H 2048 D   26 dtype uint16
# 20: brightfield          W 2048 H 2048 D   26 dtype uint16
```

bash:

```
python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_IN}
python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_OUT}
python examples/chess/convert.py init-db

seq=18 # [15, 16, 18, 19, 20]
name="scrgiorgio-tomo-20230912-${seq}"
python ./examples/chess/pubsub.py --action pub --queue ${CONVERT_QUEUE_IN} --message "{
   'name':'${name}',
   'src':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/${seq}/nf/nf_*.tif',
   'dst':'/mnt/data1/nsdf/tmp/${name}/visus.idx',
   'compression':'zip',
   'arco':'1mb',
   'metadata': [
      {'type':'file','path':'/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.json'},
      {'type':'file','path':/nfs/chess/raw/2023-2/id3a/shanks-3731-a/ti-2-exsitu/id3a-rams2_tomo_scan_layers-retiga-ti-2-exsitu.par''},
   ]}"

python examples/chess/convert.py run-convert-loop

```
