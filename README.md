# Instructions

**Panel problems under Chrome**


- `notebooks/vtkvolume.ipynb`  does NOT work in chrome
- `notebooks/vtk_slicer.ipynb` does NOT work in chrome
  - see https://github.com/holoviz/panel/issues/6171

Removed `itkwidgets`, at the end pyvista seems to be better maintained
- see https://github.com/imjoy-team/imjoy-jupyterlab-extension/issues/6#issuecomment-1898703563
- this is needed for itkwidgets on jupyterlab

Using `python3.10`
- maybe python3.11 too? To test
- **DO NOT** use `python312` does not have a good match for libzmq 

Using JupyterLab3 (vs 4) because some (itkwidgets|bokeh) extensions do not yet work
- jupyter_bokeh (needed by bokeh inside jupyter lab) is not working in JupyterLab 4.x.y
  - https://github.com/bokeh/jupyter_bokeh/issues/197


for JupyterLab extensions see:
- [Jupyter 4 extensions](https://github.com/jupyterlab/jupyterlab/issues/14590)  
- [Jupyter 3 extensions](https://github.com/jupyterlab/jupyterlab/issues/9461) 


## PIP

Remove old installations:

```bash
.venv\Scripts\deactivate
rmdir /s /q  .venv
rmdir /s /q  "%USERPROFILE%\.jupyter"
```

```bat
c:\Python310\python.exe -m venv .venv
.venv\Scripts\activate
where python

# maybe *dangerous* to update pip
python.exe -m pip install --upgrade pip

python -m pip install --verbose --no-cache --no-warn-script-location boto3 colorcet fsspec numpy imageio urllib3 pillow xarray xmltodict  plotly requests scikit-image scipy seaborn tifffile pandas tqdm matplotlib  zarr altair cartopy dash fastparquet folium geodatasets geopandas geoviews lxml numexpr scikit-learn sqlalchemy statsmodels vega_datasets xlrd yfinance pyarrow pydeck h5py hdf5plugin netcdf4 nexpy nexusformat nbgitpuller intake ipysheet ipywidgets bokeh ipywidgets-bokeh panel holoviews hvplot datashader vtk pyvista trame trame-vtk trame-vuetify  notebook "jupyterlab==3.6.6" jupyter_bokeh jupyter-server-proxy  jupyterlab-system-monitor "pyviz_comms>=2.0.0,<3.0.0" "jupyterlab-pygments>=0.2.0,<0.3.0" OpenVisusNoGui openvisuspy

# save for the future
pip freeze 
 
python python/test-pyvista.py
python python/test-vtkvolume.py 

.venv\Scripts\deactivate
```

## Jupyter 

Trust notebooks

```bash
python scripts/trust_notebooks.py "examples/notebooks/**/*.ipynb"
```

check the python kernel:

```bash
where jupyter
jupyter kernelspec list
```

Check extensions:
- **all extensions should show `enabled ok...`**
- @bokeh/jupyter_bokeh    for bokeh   (installed by `jupyter_bokeh``)
- @pyviz/jupyterlab_pyviz for panel (installed by `pyviz_comms``)
- avoid any message `is not compatible with the current JupyterLab` message at the bottom

```bash
jupyter labextension list
pip install nodejs-bin[cmd]
jupyter lab clean --all
jupyter lab build 
# rmdir /s /q   C:\Users\scrgi\AppData\Local\Yarn 
```

Look also for additional extensions loaded from here

```bash
dir .venv\share\jupyter\lab\extensions\*
```

Run:

```bash
jupyter lab .
```

# OpenViSUS Visualization project

The official OpenVisus C++ GitHub repository is [here](https://github.com/sci-visus/OpenVisus).

## Install openvisuspy

Create a virtual environment. 

his step is optional, but it is best to avoid conflicts:

for Linux/OS users

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

For Windows users

```bat

python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
```

Install minimal dependencies:

```bash
python -m pip install numpy boto3 xmltodict colorcet requests scikit-image matplotlib bokeh panel jupyter
```

Next, install Openvisus and openvisuspy packages. 


If you **DO NOT NEED the OpenVisus viewer** (or if you are in Windows WSL):

```bash
python -m pip install --upgrade OpenVisusNoGui
python -m pip install --upgrade openvisuspy
```

if you **DO NEED the OpenVisus viewer**:

```bash
python -m pip install --upgrade OpenVisus
python -m OpenVisus configure 
python -m pip install --upgrade openvisuspy
```

if you **DO need OpenVisus debugging** you can use your binaries/local python code:

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;.\src

```

check the two packages import fine:

```bash
python -c "import OpenVisus   as ov"
python -c "import openvisuspy as ovy"
```


## Dashboards 


Change as needed:

```bash
set BOKEH_ALLOW_WS_ORIGIN=*
set BOKEH_LOG_LEVEL=debug
set VISUS_CPP_VERBOSE=1
set VISUS_NETSERVICE_VERBOSE=1
# set VISUS_CACHE=c:/tmp/visus-cache

# example with a single file
python -m panel serve dashboards --dev --args --dataset D:\visus-datasets\david_subsampled\visus.idx 
python -m panel serve dashboards --dev --args --dataset D:\visus-datasets\2kbit1\zip\hzorder\visus.idx 

python -m panel serve dashboards --dev --args --dataset "https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=arco" 

python -m panel serve dashboards --dev --args --dataset "https://atlantis.sci.utah.edu/mod_visus?dataset=2kbit1&cached=arco"
```

## Developers only

Deploy new binaries

- **Update the `PROJECT_VERSION` inside `pyproject.toml`**

```bash
# source .venv/bin/activate
./scripts/new_tag.sh
```

