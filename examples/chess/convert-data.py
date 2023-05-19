import os ,sys, time, logging,shutil,glob
from datetime import datetime
import numpy as np
import scipy
from skimage import io

import OpenVisus as ov


# ///////////////////////////////////////////////////////////////////
def Touch(filename):
    with open(filename, 'a') as f:
        pass 

# ///////////////////////////////////////////////////////////////////
def Convert(idx_filename, aquire_data=None, enable_compression=False, arco="modvisus"):
    
    os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
    logger= logging.getLogger("OpenVisus")

    for timestep in range(num_timesteps):
        t1 = time.time()
        data=aquire_data(timestep=timestep)
        D,H,W=data.shape
        m,M=np.min(data),np.max(data)
        print(f"Timestep {timestep} loaded in {time.time()-t1} seconds dtype={data.dtype} shape={data.shape} c_size={W*H*D*4:,} m={m} M={M}")

        if timestep==0:
            D,H,W=data.shape
            db=ov.CreateIdx(url=idx_filename, dims=[W,H,D], fields=[ov.Field("data",str(data.dtype),"row_major")], compression="raw", time=[0,num_timesteps,"time_%02d/"], arco=arco)
            print(db.getDatasetBody().toString())
            print("Dataset created")

        done_filename=os.path.join(os.path.dirname(idx_filename),f".done.{timestep:04d}")

        if os.path.isfile(done_filename):
            print(f"Timestep={timestep} already generated, skipping")
        else:
            t1 = time.time()
            db.write(data,time=timestep)
            print(f"Wrote new timestep={timestep} done in {time.time() - t1} seconds")

            if enable_compression:
                t1 = time.time()
                db.compressDataset(["zip"],timestep=timestep)
                print(f"Compressed timestep={timestep} done in {time.time()-t1} seconds")

            Touch(done_filename)

# ///////////////////////////////////////////////////////////////////
if __name__ == "__main__":

    """
    ./examples/chess/run-server.sh

    # NUMPY    912*816*2025*float32 Each timestep is  5 GiB. if we had 900 timesteps it would be  5T
    rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy
    watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy
    python3 examples/chess/convert-data.py 900 /mnt/data1/DemoNSDF-feb-2023/recon_combined_1_2_3_fullres.npy /mnt/data1/nsdf/tmp/merif2023/timeseries/numpy/visus.idx

     # TIFF   2048*2048*1447*float32 Each timestep is 22 GiB. if we had 900 timesteps it would be 20TB
    rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff
    watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff
    python3 examples/chess/convert-data.py 900 "/nfs/chess/nsdf01/vpascucci/allison-1110-3/mg4al-sht/11/nf/*.tif" /mnt/data1/nsdf/tmp/merif2023/timeseries/tiff/visus.idx   

    # NEXUS  1420*1420* 310*float32 Each timestep is  2 GiB. if we had 900 timesteps it would be  2TB
    rm -Rf /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus
    watch du -hs /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus
    python3 examples/chess/convert-data.py 900  /mnt/data1/nsdf/20230317-demo/3scans_HKLI/3scans_HKLI.nxs /mnt/data1/nsdf/tmp/merif2023/timeseries/nexus/visus.idx

    """

    t1=time.time()
    print("sys.argv",sys.argv)
    num_timesteps,src_filename,idx_filename=sys.argv[1:]
    num_timesteps=int(num_timesteps)
    print(f"Loading first 3D volume num_timesteps={num_timesteps} src_filename={src_filename} idx_filename={idx_filename}...")

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

    Convert(idx_filename=idx_filename, aquire_data=AcquireData)