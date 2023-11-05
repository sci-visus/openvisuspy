
import os,sys,glob,time,logging
import numpy as np

logger = logging.getLogger("nsdf-convert")

import OpenVisus as ov

#  ///////////////////////////////////////////////////////////////////
def ConvertHDF5(src, dst, compression="raw",arco="modvisus", expression="/imageseries/images"):

	logger.info(f"ConvertHDF5 src={src} dst={dst} compression={compression} arco={arco} expression={expression} start...")

	import h5py
	f = h5py.File(src, 'r')

	images=f
	for it in expression.split("/")[1:]:
		images=images[it]

	logger.info(f"HDF5 file shape={images.shape} dtype={images.dtype}")
	D,H,W=images.shape

	# why I am forcing it to be float32? I don't rememeber, maybe for openvisus/bokeh?
	t1=time.time()
	data=images[0:D,0:H,0:W].astype(np.float32)
	vmin,vmax=np.min(data),np.max(data)
	logger.info(f"hdf5 loaded in {time.time() - t1} seconds shape={data.shape} dtype={data.dtype} vmin={vmin} vmax={vmax}")
	
	# write uncompressed
	idx_filename=dst
	field=ov.Field.fromString(f"""DATA {str(data.dtype)} format(row_major) min({vmin}) max({vmax})""")

	# TODO: I can I get this information from image stack???
	idx_physic_box=ov.BoxNd.fromString(f"0 {W} 0 {H} 0 {D}")
	idx_axis="X Y Z"
	db=ov.CreateIdx(
		url=idx_filename, 
		dims=[W,H,D], 
		fields=[field], 
		compression="raw", 
		arco=arco, 
		axis=idx_axis, 
		physic_box=idx_physic_box)

	# print(db.getDatasetBody().toString())
	logger.info(f"IDX file={idx_filename} created")

	os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
	logger.info(f"Writing IDX data...")
	t1 = time.time()
	db.write(data, time=0)
	write_sec=time.time() - t1
	logger.info(f"Wrote IDX data in {write_sec} seconds")

	if compression and compression!="raw":
		t1 = time.time()
		logger.info(f"Compressing dataset to {compression}...")
		db.compressDataset([compression])
		logger.info(f"Compressed dataset to {compression} in {time.time()-t1} seconds")

	logger.info(f"ConvertHDF5 src={src} dst={dst} compression={compression} arco={arco} done")