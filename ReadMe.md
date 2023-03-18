# Instructions

See [https://github.com/sci-visus/OpenVisus]()

```
python -m pip install --upgrade openvisuspy
```

# Setup

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;C:\projects\openvisuspy\src
set VISUS_BACKEND=cpp

set AWS_ACCESS_KEY_ID=any
set AWS_SECRET_ACCESS_KEY=any
set AWS_ENDPOINT_URL=https://maritime.sealstorage.io/api/v0/s3

set VISUS_CPP_VERBOSE=1
set VISUS_DASHBOARDS_VERBOSE=1
set VISUS_NETSERVICE_VERBOSE=0

set BOKEH_ALLOW_WS_ORIGIN=*
set BOKEH_LOG_LEVEL=debug
```

# Bokeh Dashboard

```
set VISUS_UI=bokeh
python -m bokeh serve "examples/dashboards/00-dashboards.py"  --dev --address localhost --port 8888 
```

# Holoviz panel Dashboard

```
set VISUS_UI=panel
python -m panel serve --autoreload --show "examples/dashboards/00-dashboards.py"

```

# Jupyter Notebooks

```
python -m jupyter notebook ./examples/notebooks
```

# Upload wheel

```

# update PROJECT_VERSION in pyproject.toml
export PYPI_USER=
export PYPI_TOKEN=
python3 -m build .

python3 -m twine upload --username ${PYPI_USER}  --password ${PYPI_TOKEN} --skip-existing   "dist/*.whl" 
python3 -m twine upload dist/*
```


# (TODO) Panel dashboards

Links:
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html
- https://github.com/awesome-panel/examples

Note:
- Panel seems to have already a lot of fixes for Bokeh running in WASM, so probably better to use Panel instead of pure Bokeh?

```

python -m panel convert ./script.py --to pyodide-worker --out ./tmp 

# see https://github.com/holoviz/panel/issues/4089
# see https://github.com/holoviz/panel/blob/main/panel/io/convert.py

# need to push to pypi o

set VISUS_BACKEND=py
python ./convert.py

# http://localhost:8000/00-dashboards.html 

# https://pyodide.org/en/stable/console.html

import micropip
await micropip.install(['openvisuspy','numpy','requests','xmltodict','bokeh','panel','xyzservices','colorcet'])

import os,sys
os.environ['VISUS_BACKEND']="py"
import openvisuspy


python -m panel convert ./examples/dashboards/00-dashboards.py --to pyodide-worker --out ./tmp --requirements openvisuspy 

cd python -m http.server 
python -m http.server 
```

# (TODO) JupyterLite

Links 
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html#setting-up-jupyterlite
- https://panelite.holoviz.org/lab/index.html
- see other directorh with docs from openvisus=wasm


# Misc (just for reference)

- vtk will not work https://gitlab.kitware.com/vtk/vtk/-/issues/18806
