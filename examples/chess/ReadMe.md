# How to run CHESS convert


## Setup your shell

```
source setup.sh 
```

## mod_visus specific

Restart the server

```
source "/nfs/chess/nsdf01/openvisus/.mod_visus.identity.sh"

sudo /usr/bin/systemctl restart httpd

# test if it works
curl --user "${MODVISUS_USERNAME}:${MODVISUS_PASSWORD}" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"
```

Inspect apache logs
- right now: permission denied

```
more  /var/log/apache/error.log
```

## Run single image-stack conversion

```
python examples/chess/convert.py  \
   --src "/nfs/chess/nsdf01/vpascucci/allison-1110-3/mg4al-sht/11/nf/*.tif" \
   --dst "/mnt/data1/nsdf/tmp/merif2023/timeseries/tiff/visus.idx" \
   --compression raw \
   --arco modvisus
```

## Reset the convert queues and db:

```
python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_IN}
python ./examples/chess/pubsub.py --action flush --queue ${CONVERT_QUEUE_OUT}
python examples/chess/convert.py init-db
```

# Show the convert db


```
sqlite3 ${CONVERT_SQLITE3_FILENAME} "select * from datasets;" ".exit"
```

# convert the db to a convert.config 

Note: OpenVisus is automatically wathing for changes for that file


```
python examples/chess/convert.py dump-datasets
more ${VISUS_CONVERT_CONFIG}
```

# Run the conversion loop

THis will:
- wait for a message from the input queue
- add the pending conversion to the db
- execute the conversion
- update the db with conversion end timing
- send an event to the output queue 

Note:
- the conversion loop can crash. if so it will restart where it left 

Todo:
- cronjob to restart?
- multiple convert?

```
python examples/chess/convert.py run-convert-loop
```


# Send an event for image-stacl conversion 

Note:
- the conversion loop can be offline

```
python ./examples/chess/pubsub.py --action pub --queue ${CONVERT_QUEUE_IN} --message "{
   'name':'test',
   'src':'/nfs/chess/nsdf01/vpascucci/allison-1110-3/mg4al-sht/11/nf/*.tif',
   'dst':'/mnt/data1/nsdf/tmp/remove-me/test-1111/visus.idx',
   'compression':'raw',
   'arco':'modvisus'
}"
```

