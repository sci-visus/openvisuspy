# Instructions

See [https://github.com/sci-visus/OpenVisus]()

```
python -m pip install --upgrade openvisuspy
```

# Setup

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;C:\projects\openvisuspy\src

set AWS_ACCESS_KEY_ID=any
set AWS_SECRET_ACCESS_KEY=any
set AWS_ENDPOINT_URL=https://maritime.sealstorage.io/api/v0/s3

set VISUS_CPP_VERBOSE=1
set VISUS_NETSERVICE_VERBOSE=0

set BOKEH_ALLOW_WS_ORIGIN=*
set BOKEH_LOG_LEVEL=debug
```

# Dashboards and notebooks

Bokeh:

```
python -m bokeh serve "examples/dashboards/00-dashboards.py"  --dev --address localhost --port 8888 
```

Panel:

```

python -m panel serve --autoreload --show "examples/dashboards/00-dashboards.py" --panel
```

Jupyter:

```
python -m jupyter notebook ./examples/notebooks
```

# Upload wheel

```

# update PROJECT_VERSION in setup.py
export PYPI_USER=scrgiorgio
export PYPI_TOKEN="..."
python3 -m build .

python3 -m twine upload --username ${PYPI_USER}  --password ${PYPI_TOKEN} --skip-existing   "dist/*.whl" 
python3 -m twine upload dist/*
```

Check on `https://pyodide.org/en/stable/console.html` if you can import openvisus


```
import os,sys,micropip
await micropip.install(['openvisuspy','numpy','requests','xmltodict','bokeh','xyzservices','colorcet'])
import openvisuspy
```

# (TODO) Panel dashboards

Panel seems to have already a lot of fixes/support for WASM, so probably better to use Panel instead of pure Bokeh (?!)

Links:
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html
- https://github.com/awesome-panel/examples
- https://github.com/holoviz/panel/issues/4089
- https://github.com/holoviz/panel/blob/main/panel/io/convert.py


```
python ./convert.py

# in another cell
cd tmp
python -m http.server 
# http://localhost:8000/00-dashboards.html 
```


# (TODO) JupyterLite

Links 
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html#setting-up-jupyterlite
- https://panelite.holoviz.org/lab/index.html
- see other directorh with docs from openvisus=wasm


# Misc (just for reference)

- vtk will not work https://gitlab.kitware.com/vtk/vtk/-/issues/18806
