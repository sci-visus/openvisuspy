# Instructions


## Windows PIP installation

(OPTONAL) Remove old environment:

```bat
.venv\Scripts\deactivate
rmdir /s /q  .venv
rmdir /s /q  "%USERPROFILE%\.jupyter"
```

Install new version:
- use python `3.10` or `3.11`. 
- **DO NOT** use `python312` does not have a good match for `libzmq`
- use  JupyterLab v3 (**NOT v4**) because bokeh does not work
  - https://github.com/bokeh/jupyter_bokeh/issues/197

```bash
python -m venv .venv
.venv\Scripts\activate
where python

# OPTIONAL
# python.exe -m pip install --upgrade pip

# removed `itkwidgets`, since pyvista seems to be better maintained/compatible
#   see https://github.com/imjoy-team/imjoy-jupyterlab-extension/issues/6#issuecomment-1898703563
#      `imjoy` is needed for itkwidgets on jupyterlab
python -m pip install --verbose --no-cache --no-warn-script-location boto3 colorcet fsspec numpy imageio urllib3 pillow xarray xmltodict  plotly requests scikit-image scipy seaborn tifffile pandas tqdm matplotlib  zarr altair cartopy dash fastparquet folium geodatasets geopandas geoviews lxml numexpr scikit-learn sqlalchemy statsmodels vega_datasets xlrd yfinance pyarrow pydeck h5py hdf5plugin netcdf4 nexpy nexusformat nbgitpuller intake ipysheet ipywidgets bokeh==3.3.4 ipywidgets-bokeh panel==1.3.8 holoviews hvplot datashader vtk pyvista trame trame-vtk trame-vuetify notebook "jupyterlab==3.6.6" jupyter_bokeh jupyter-server-proxy  jupyterlab-system-monitor "pyviz_comms>=2.0.0,<3.0.0" "jupyterlab-pygments>=0.2.0,<0.3.0" 


# in debug just use local paths
# set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;.\src
python -m pip install OpenVisusNoGui openvisuspy

# test import 
python -c "import OpenVisus"
python -c "import openvisuspy"

# save the output for the future
pip freeze 
```

## Test Volume rendering

```bash
# test pyvista
python examples/python/test-pyvista.py

# test vtk volume
python examples/python/test-vtkvolume.py 
```


## Run Dashboards 


Change as needed:

```bash
.venv\Scripts\activate

# set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;.\src

set BOKEH_ALLOW_WS_ORIGIN=*
set BOKEH_LOG_LEVEL=debug
set VISUS_CPP_VERBOSE=1
set VISUS_NETSERVICE_VERBOSE=1
set VISUS_VERBOSE_DISKACCESS=0
set VISUS_CACHE=c:/tmp/visus-cache

python -m panel serve app --dev --args "D:/visus-datasets/david_subsampled/visus.idx"
python -m panel serve app --dev --args "D:/visus-datasets/2kbit1/zip/hzorder/visus.idx"
python -m panel serve app --dev --args "D:/visus-datasets/signal1d/visus.idx"
python -m panel serve app --dev --args "D:/visus-datasets/chess/nsdf-group/dashboards.json"
python -m panel serve app --dev --args "D:/visus-datasets/chess/nsdf-group/datasets/near-field-nexus/visus.idx"

# example sync view (works in 2d only)
python -m panel serve app --dev --args "D:/visus-datasets/david_subsampled/visus.idx" "D:/visus-datasets/microscope/bw/visus.idx"

# slac 
python -m panel serve app --dev --args c:\big\visus-datasets\signal1d_slac\visus.idx   

python -m panel serve app --dev --args "https://maritime.sealstorage.io/api/v0/s3/utah/visus-datasets/signal1d_slac/visus.idx?cached=arco&access_key=any&secret_key=any&endpoint_url=https://maritime.sealstorage.io/api/v0/s3"

# slac max
python -m panel serve app --dev --args c:\big\visus-datasets\signal1d_slac_max\visus.idx

python -m panel serve app --dev --args "https://maritime.sealstorage.io/api/v0/s3/utah/visus-datasets/signal1d_slac_max/visus.idx?cached=arco&access_key=any&secret_key=any&endpoint_url=https://maritime.sealstorage.io/api/v0/s3"

# single signals
python -m panel serve app --dev --args "https://maritime.sealstorage.io/api/v0/s3/utah/supercdms-data/CDMS/UMN/R68/Raw/07180816_1648/07180816_1648_F0006/events/00135/banks/SCD0/data.npz?profile=sealstorage_ro&endpoint_url=https://maritime.sealstorage.io/api/v0/s3"

python -m panel serve app --dev --args "https://raw.githubusercontent.com/nsdf-fabric/nsdf-slac/main/dashboards.json"

# not sure why I cannot cache in arco an IDX that is NON arco
python -m panel serve app --dev --args "https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=idx" 
python -m panel serve app --dev --args "https://atlantis.sci.utah.edu/mod_visus?dataset=2kbit1&cached=idx"
```

## Run notebooks

### Setup Jupyter Lab

```bash

# check jupyter paths
where jupyter
jupyter kernelspec list

# Check extensions:
#   **all extensions should show `enabled ok...`**
#   e.g you will need @bokeh/jupyter_bokeh    for bokeh   (installed by `jupyter_bokeh``)
#   e.g you will need @pyviz/jupyterlab_pyviz for panel   (installed by `pyviz_comms``)
#   avoid any message `is not compatible with the current JupyterLab` message at the bottom
jupyter labextension list

# Build recommended, please run `jupyter lab build`:
#   @plotly/dash-jupyterlab needs to be included in build
pip install nodejs-bin[cmd]
jupyter lab clean --all
jupyter lab build 
# rmdir /s /q C:\Users\scrgi\AppData\Local\Yarn 
# Look also for additional extensions loaded from here
# dir .venv\share\jupyter\lab\extensions\*
jupyter labextension list
```

```bash

# is this avoiding any caching/security problem? not sure
python scripts/run_command.py "jupyter nbconvert --clear-output --inplace {notebook}" "examples/notebooks/*.ipynb"
python scripts/run_command.py "jupyter trust {notebook}"                              "examples/notebooks/*.ipynb"

# 
# set BROWSER="C:\Program Files\Mozilla Firefox\firefox.exe"
jupyter lab .
```


## Developers only

Deploy new binaries

- **Update the `PROJECT_VERSION` inside `pyproject.toml`**

```bash
# source .venv/bin/activate
./scripts/new_tag.sh
```



<!-- Security scan triggered at 2025-09-01 20:12:46 -->