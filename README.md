# OpenViSUS Visualization project

The official OpenVisus C++ GitHub repository is [here](https://github.com/sci-visus/OpenVisus).

## Install openvisuspy

Create a virtual environment. This step is optional, but best to avoid conflicts:

- for windows users you can do `doskey python3=python $*` and `.venv/Scripts/activate.bat`

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

Install python packages, technically only `numpy` is stricly needed, but to access cloud storage and show dashboards/notebooks, you need additional packages too.

```bash
python3 -m pip install numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh panel itkwidgets[all] pyvista vtk jupyter
```

Next, install Openvisus packages. 


If you **do not need the OpenVisus viewer** (or if you are in Windows WSL):

```bash
python3 -m pip install --upgrade OpenVisusNoGui
python3 -m pip install --upgrade openvisuspy 
```

if **you do need the OpenVisus viewer**:

```bash
python3 -m pip install --upgrade OpenVisus
python3 -m OpenVisus configure 
python3 -m pip install --upgrade openvisuspy 
```

## Bokeh Dashboards 


```bash
# export BOKEH_ALLOW_WS_ORIGIN=*
# export BOKEH_LOG_LEVEL=debug
# export VISUS_CPP_VERBOSE=0
# export VISUS_NETSERVICE_VERBOSE=0
# export PYTHONPATH=./src;/projects/OpenVisus/build/RelWithDebInfo

python -m bokeh serve "examples/dashboards/app"  --dev --args --dataset  "https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=arco" 

python -m bokeh serve "examples/dashboards/app"  --dev --args --dataset  "https://atlantis.sci.utah.edu/mod_visus?dataset=2kbit1&cached=arco"
```

## Developers only


Deploy new binaries

- **Update the `PROJECT_VERSION` inside `pyproject.toml`**

```bash
# source .venv/bin/activate
./scripts/new_tag.sh
```


## (EXPERIMENTAL) Pure Python Backend

This version may be used for cpython too in case you cannot install C++ OpenVisus (e.g., WebAssembly).

It **will not work with S3 cloud-storage blocks**.

Bokeh dashboards:

```
python3 -m bokeh serve "examples/dashboards/app"  --dev --address localhost --port 8888 --args --py  --single
python3 -m bokeh serve "examples/dashboards/app"  --dev --address localhost --port 8888 --args --py  --multi
```

Panel dashboards:

```
python -m panel serve "examples/dashboards/app"  --dev --address localhost --port 8888 --args --py --single
python -m panel serve "examples/dashboards/app"  --dev --address localhost --port 8888 --args --py --multi
```

Jupyter notebooks:

```
export VISUS_BACKEND=py
python3 -m jupyter notebook ./examples/notebooks
```

## Demos

REMEMBER to resize the browswe  window, **otherwise it will not work**:

- https://scrgiorgio.it/david_subsampled.html
- https://scrgiorgio.it/2kbit1.html
- https://scrgiorgio.it/chess_zip.html

DEVELOPERS notes:
- grep for `openvisuspy==` and **change the version consistently**.

### PyScript

Serve local directory

```
export VISUS_BACKEND=py
python3 examples/server.py --directory ./
```

Open the urls in your Google Chrome browser:

- http://localhost:8000/examples/pyscript/index.html 
- http://localhost:8000/examples/pyscript/2kbit1.html 
- http://localhost:8000/examples/pyscript/chess_zip.html 
- http://localhost:8000/examples/pyscript/david_subsampled.html

### JupyterLite

```
export VISUS_BACKEND=py
ENV=/tmp/openvisuspy-lite-last
python3 -m venv ${ENV}
source ${ENV}/bin/activate

# Right now jupyter lite seems to build the output based on installed packages. 
# There should be other ways (e.g., JSON file or command line) for specifying packages, but for now creating a virtual env is good enough\
# you need to have exactly the same package version inside your jupyter notebook (see `12-jupyterlite.ipynb`)
python3 -m pip install \
    jupyterlite==0.1.0b20 pyviz_comms numpy pandas requests xmltodict xyzservices pyodide-http colorcet \
    https://cdn.holoviz.org/panel/0.14.3/dist/wheels/bokeh-2.4.3-py3-none-any.whl \
    panel==0.14.2 \
    openvisuspy==1.0.100 \
    jupyter_server 

rm -Rf ${ENV}/_output 
jupyter lite build --contents /mnt/c/projects/openvisuspy/examples/notebooks --output-dir ${ENV}/_output

# change port to avoid caching
PORT=14445
python3 -m http.server --directory ${ENV}/_output --bind localhost ${PORT}

# or serve
jupyter lite serve --contents ./examples/notebooks --output-dir ${ENV}/_output --port ${PORT} 

# copy the files somewhere for testing purpouse
rsync -arv ${ENV}/_output/* <username>@<hostname>:jupyterlite-demos/
```

