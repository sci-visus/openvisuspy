# How to run CHESS convert


## Setup

NOTE:
- COnnect to the NSDF entrypoint
- `OPEN FOLDER` `/mnt/data1/nsdf/openvisuspy`


```bash
source setup.sh 
```

## mod_visus specific

Restart the server

```bash
source "/nfs/chess/nsdf01/openvisus/.mod_visus.identity.sh"

sudo /usr/bin/systemctl restart httpd

# test if it works
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```

Inspect apache logs
- right now: permission denied

```bash
more  /var/log/apache/error.log
```

See OpenVisus `Docker/group-security`` for details about how to add users

# Solve Jupyter notebook Visual Code problems


When you open Jupyter Notebooks.,..
You should see `my-env` as a Python Kernel on the top-right of the Visual code
If you do not see it, do:

```bash
conda install ipykernel
python -m ipykernel install --user --name my-env --display-name "my-env" and
```

Reload Visual Code




## Dashboard DEMO

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

### STREAMABLE Nexus 


Run the `convert-nexus-data.ipynb` to convert data to a streamable format 
- metadata will still be in the NEXUS file
- volumetric big data will be automatically stored in a OpenVisus file

To show the data in a bokeh dashboard

```bash
set PYTHONPATH=./src;C:\projects\OpenVisus\build\RelWithDebInfo
python -m bokeh serve examples/dashboards/run.py --dev --args --dataset C:/visus_datasets/3scans_HKLI.streamable.nxs  --multi --color-mapper log --palette Viridis256
```


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

Show the convert db

```bash
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
     'src':'/nfs/chess/nsdf01/vpascucci/allison-1110-3/mg4al-sht/11/nf/*.tif',
     'dst':'/mnt/data1/nsdf/tmp/remove-me/my-chess-group-${i}/visus.idx',
     'compression':'raw',
     'arco':'modvisus'
}"  
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
