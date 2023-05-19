# Instructions

# Preliminary setup

on the NSDF entrypoint:

```
conda activate my-env
cd /mnt/data1/nsdf/openvisuspy
source examples/chess/credentials.sh
```


# OpenVisus modvisus server

if you want to restart the modvisus server:

```
./examples/chess/run-server.sh
```


Config file is here

```
/nfs/chess/nsdf01/openvisus/lib64/python3.6/site-packages/OpenVisus/visus.config
```

Credentials are here:


```
/nfs/chess/nsdf01/openvisus/.mod_visus.identity.sh
```

# Timeseries convert

Setup credentials:

```
source ./examples/chess/credentials.sh
```
## NumPy

- 912*816*2025*float32 Each timestep is  5 GiB. 
- if we had 900 timesteps it would be  5T

```
rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy
watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy
python3 examples/chess/convert-data.py \
    900 \
    /mnt/data1/DemoNSDF-feb-2023/recon_combined_1_2_3_fullres.npy \
    /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy/visus.idx \
    "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=chess-timeseries-numpy&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"
```

## Tiff 

- 2048*2048*1447*float32 Each timestep is 22 GiB
- if we had 900 timesteps it would be 20TB

```
rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff
watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff
python3 examples/chess/convert-data.py \
    900 \
    "/nfs/chess/nsdf01/vpascucci/allison-1110-3/mg4al-sht/11/nf/*.tif" \
    /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff/visus.idx \
    "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=chess-timeseries-tiff&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"
```

## Nexus

- 1420*1420* 310*float32 Each timestep is  2 GiB
- if we had 900 timesteps it would be  2TB

```
rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus
watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus
python3 examples/chess/convert-data.py \
    900  \
    /mnt/data1/nsdf/20230317-demo/3scans_HKLI/3scans_HKLI.nxs \
    /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus/visus.idx \
    "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=chess-timeseries-nexus&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"
```