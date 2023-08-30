import os ,sys, time, logging,shutil,glob
from datetime import datetime
import numpy as np
import scipy
import json
from skimage import io

import OpenVisus as ov


# ///////////////////////////////////////////////////////////////////
def Touch(filename):
    with open(filename, 'a') as f:
        pass 


# ///////////////////////////////////////////////////////////////////
def Convert(idx_filename, modvisus_url, aquire_data=None, enable_compression=False, arco="modvisus"):
    
    os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
    logger= logging.getLogger("OpenVisus")

    connection,channel=None,None
    PUBSUB_URL=os.environ.get("PUBSUB_URL",None)
    if PUBSUB_URL:
        import pika
        params = pika.URLParameters(PUBSUB_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='nsdf-channel')

    db=None
    for timestep in range(num_timesteps):

        done_filename=os.path.join(os.path.dirname(idx_filename),f".done.{timestep:04d}")

        if os.path.isfile(done_filename):
            print(f"Timestep={timestep} already generated, skipping")
            continue

        t1 = time.time()
        data=aquire_data(timestep=timestep)
        D,H,W=data.shape
        m,M=np.min(data),np.max(data)
        acquire_sec=time.time()-t1
        print(f"Timestep {timestep} loaded in {acquire_sec} seconds dtype={data.dtype} shape={data.shape} c_size={W*H*D*4:,} m={m} M={M}")

        if not db:
            D,H,W=data.shape
            db=ov.CreateIdx(url=idx_filename, dims=[W,H,D], fields=[ov.Field("data",str(data.dtype),"row_major")], compression="raw", time=[0,num_timesteps,"time_%02d/"], arco=arco)
            print(db.getDatasetBody().toString())
            print("Dataset created")

        t1 = time.time()
        db.write(data,time=timestep)
        write_sec=time.time() - t1
        print(f"Wrote new timestep={timestep} done in {write_sec} seconds")

        compress_sec=0.0
        if enable_compression:
            t1 = time.time()
            db.compressDataset(["zip"],timestep=timestep)
            compress_sec=time.time()-t1
            print(f"Compressed timestep={timestep} done in {compress_sec} seconds")

        # send the timestep is ready
        if channel:
            channel.basic_publish(exchange='', routing_key='hello',body=json.dumps({
                "url":modvisus_url,
                "timestep":timestep,
                "arco":arco,
                "acquire-sec":acquire_sec, 
                "write-sec":write_sec, 
                "compress-sec":compress_sec, 
            }))                

        Touch(done_filename)



    if connection:
        connection.close()            

# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":

    """
    ./examples/chess/run-server.sh

    source ./credentials.sh

    # NUMPY    912*816*2025*float32 Each timestep is  5 GiB. if we had 900 timesteps it would be  5T
    rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy
    watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy
    python3 examples/chess/convert-data.py \
        900 \
        /mnt/data1/DemoNSDF-feb-2023/recon_combined_1_2_3_fullres.npy \
        /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy/visus.idx \
        "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=chess-timeseries-numpy&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"

     # TIFF   2048*2048*1447*float32 Each timestep is 22 GiB. if we had 900 timesteps it would be 20TB
    rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff
    watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff
    python3 examples/chess/convert-data.py \
        900 \
        "/nfs/chess/nsdf01/vpascucci/allison-1110-3/mg4al-sht/11/nf/*.tif" \
        /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff/visus.idx \
        "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=chess-timeseries-tiff&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"

    # NEXUS  1420*1420* 310*float32 Each timestep is  2 GiB. if we had 900 timesteps it would be  2TB
    rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus
    watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus
    python3 examples/chess/convert-data.py \
        900  \
        /mnt/data1/nsdf/20230317-demo/3scans_HKLI/3scans_HKLI.nxs \
        /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus/visus.idx \
        "https://nsdf01.classe.cornell.edu/mod_visus?action=readdataset&dataset=chess-timeseries-nexus&~auth_username=${MODVISUS_USERNAME}&~auth_password=${MODVISUS_PASSWORD}"

    """

    t1=time.time()
    print("sys.argv",sys.argv)
    num_timesteps=int(sys.argv[1])
    src_filename=sys.argv[2]
    idx_filename=sys.argv[3]
    modvisus_url=sys.argv[4]
    print(f"Convert daa num_timesteps={num_timesteps} src_filename={src_filename} idx_filename={idx_filename} modvisus_url modvisus_url={modvisus_url}...")

    ext=os.path.splitext(src_filename)[1]

    if ext==".npy":
        first=np.load(src_filename)

    elif ext==".nxs":
        from nexusformat.nexus import nxload 
        from nexusformat.nexus.tree import NX_CONFIG    
        NX_CONFIG['memory']=4000   
        nexus_file=nxload(src_filename)
        first=nexus_file.entry.data.counts.nxdata   

    else:
        filenames=list(sorted(glob.glob(src_filename)))
        img = io.imread(filenames[0])
        D=len(filenames)
        H,W=img.shape
        first=np.zeros((D,H,W),dtype=img.dtype)
        for Z,filename in enumerate(filenames):
            first[Z,:,:]=io.imread(filename)
        first=np.clip(first,0,70)

    first=first.astype(np.float32)
    print(f"Loaded first 3D volume in {time.time() - t1} seconds shape={first.shape} dtype={first.dtype}")
    D,H,W=first.shape

    def AcquireData(timestep):
        x=min(W,timestep*3)
        y=min(H,timestep*2)
        ret=np.empty_like(first)
        ret[:, y:H, x:W]=first[:, 0:H-y, 0:W-x]
        # for Z in range(D): ret[Z,:,:]=scipy.ndimage.rotate(ret[Z,:,:], angle=timestep*3, reshape=False, order=0) TOO SLOW
        return ret

    Convert(idx_filename=idx_filename, modvisus_url=modvisus_url, aquire_data=AcquireData)