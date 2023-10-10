
import os,sys,time,logging
import numpy as np

import OpenVisus as ov

logger = logging.getLogger("nsdf-convert")

# # ///////////////////////////////////////////////////////////////////
def ConvertNumPy(src, dst, compression="raw", arco="modvisus"):

	logger.info(f"ConvertNumPy src={src} dst={dst} compression={compression} arco={arco} start...")

	logger.info(f"Loading {src}...")
	t1=time.time()
	data=np.load(src)
	D,H,W=data.shape
	m,M=np.min(data),np.max(data)

	# why I am forcing it to be float32? I don't rememeber, maybe for openvisus/bokeh?
	data=data.astype(np.float32)

	vmin,vmax=np.min(data),np.max(data)
	D,H,W=data.shape
	logger.info(f"numpy loaded in {time.time() - t1} seconds shape={data.shape} dtype={data.dtype} c_size={W*H*D*4:,} vmin={vmin} vmax={vmax}")
	D,H,W=data.shape

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
		arco=arco)

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
		logger.info(f"Compressing dataset to {compression}")
		db.compressDataset([compression])
		logger.info(f"Compressed dataset to {compression} in {time.time()-t1} seconds")

	logger.info(f"ConvertNumPy src={src} dst={dst} compression={compression} arco={arco} done")

