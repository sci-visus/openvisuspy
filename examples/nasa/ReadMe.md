# Instructions

Links:
- http://chpc1.nationalsciencedatafabric.org:10888/nasa
- http://chpc2.nationalsciencedatafabric.org:10888/nasa
- http://chpc3.nationalsciencedatafabric.org:10888/nasa
- https://github.com/sci-visus/openvisuspy/blob/main/examples/notebooks/10-bokeh-nasa-200tb.ipynb


```
# ssh chpc1 | chpc2 | chpc3

python3 -m pip install --upgrade pip
python3 -m pip install bokeh panel boto3 xmltodict colorcet

python3 -m pip uninstall OpenVisus    
python3 -m pip uninstall OpenVisusNoGui

sudo python3 -m pip uninstall OpenVisus    
sudo python3 -m pip uninstall OpenVisusNoGui

python3 -m pip install --upgrade OpenVisusNoGui openvisuspy
python3 -m OpenVisus configure
python3 -m OpenVisus dirname

curl -o ~/nasa/__init__.py "https://raw.githubusercontent.com/sci-visus/openvisuspy/main/examples/dashboards/nasa/__init__.py"
curl -o ~/nasa/main.py     "https://raw.githubusercontent.com/sci-visus/openvisuspy/main/examples/dashboards/nasa/main.py"

screen -S nasa-demo-20tb
# echo $STY 
# screen -ls
# screen -d -r 1262204.nasa-demo-20tb

df -h /

export VISUS_CACHE=/tmp/visus/cache
mkdir -p ${VISUS_CACHE}

export BOKEH_ALLOW_WS_ORIGIN=*
export BOKEH_LOG_LEVEL=debug

python3 -m panel serve "nasa"  \
    --dev \
    --address="0.0.0.0" \
    --port 10888 \
    --args -cpp --single
```

Check cache by `du -hs ${VISUS_CACHE}`

# NASA- bellows (ver 1)

```
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade OpenVisusNoGui openvisuspy

screen -S nasa-demo-bellows
export VISUS_CACHE=/tmp/visus/cache-demo-bellows
mkdir -p ${VISUS_CACHE}
export BOKEH_ALLOW_WS_ORIGIN=*
export BOKEH_LOG_LEVEL=debug

curl -o ~/nasa-bellows.py "https://raw.githubusercontent.com/sci-visus/openvisuspy/main/examples/dashboards/app"

python3 -m panel serve \
    ~/nasa-bellows.py \
    --dev \
    --address="0.0.0.0" \
    --port 10889 \
    --args \
    --dataset "http://atlantis.sci.utah.edu/mod_visus?dataset=bellows_CT_NASA_JHochhalter&cached=idx" \
    --palette Greys256 \
    --palette-range "(0,65536)" \
    --num-views 3
```

Then you can open the url:

- http://chpc1.nationalsciencedatafabric.org:10889/nasa-bellows


# NASA bellows (ver 2)

Connect to `chpc2` and open folder `/tmp/visus-datasets/bellows1_H`


Create a `convert.py` file with the following body:

```
import os,time,glob,logging,sys,shutil,argparse
import numpy as np
from skimage import io
import OpenVisus as ov

src_pattern=sys.argv[1]
idx_filename=sys.argv[2]

print("finding files ",src_pattern)
filenames=list(sorted(glob.glob(src_pattern)))

D=len(filenames)
print("Found #filenames",D)
img = io.imread(filenames[D//2])
H,W=img.shape
print("W",W,"H",H,"D",D,"dtype",img.dtype)

os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
logger= logging.getLogger("OpenVisus")
ov.SetupLogger(logger, output_stdout=True) 

fields=[ov.Field("data",str(img.dtype),"row_major")]
db=ov.CreateIdx(url=idx_filename,dims=[W,H,D],fields=fields,compression="raw")
print("Created IDX file",idx_filename)

def generateSlices():
    for Z in range(D): 
        print(f"Writing {Z}/{D}...")
        yield io.imread(filenames[Z])

t1=time.time()
db.writeSlabs(generateSlices())
print(f"db.write done in {time.time() - t1} seconds")
```

Run the conversion:

```
python3 convert.py "./src/*.tiff" "./visus.idx"
```

Serve the data:

```
mkdir -p cd /tmp/visus-datasets/bellows1_H
cd /tmp/visus-datasets/bellows1_H
screen -S nasa-demo-bellows-ver2

python3 -c "import openvisuspy;print(openvisuspy.__path__)"

export BOKEH_ALLOW_WS_ORIGIN=*
export BOKEH_LOG_LEVEL=debug

curl -o ./nasa-bellows-ver2.py "https://raw.githubusercontent.com/sci-visus/openvisuspy/main/examples/dashboards/app"

python3 -m panel serve ./nasa-bellows-ver2.py    \
   --dev    \
   --address="0.0.0.0"    \
   --port 10902    \
   --args    \
   --dataset "$PWD/visus.idx"    \
   --palette "colorcet.coolwarm"     \
   --palette-range "(0,65536)"    \
   --num-views 3 \
   --resolution 24 \
   --show-options '["palette", "view_dep", "resolution", "num_refinements" ]' \
   --slice-show-options '["direction", "offset", "view_dep"]'
```

Open the URL:

- http://chpc1.nationalsciencedatafabric.org:10902/nasa-bellows-ver2
- http://chpc2.nationalsciencedatafabric.org:10902/nasa-bellows-ver2
- http://chpc3.nationalsciencedatafabric.org:10902/nasa-bellows-ver2





