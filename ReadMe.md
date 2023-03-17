# Instructions

See [https://github.com/sci-visus/OpenVisus]()

```
python -m pip install --upgrade openvisuspy
```


Run bokeh dashboard:

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

# BOKEH
set VISUS_UI=bokeh
python -m bokeh serve "examples/dashboards/00-dashboards.py"  --dev --address localhost --port 8888 

# PANEL
set VISUS_UI=panel
python -m panel serve --autoreload --show "examples/dashboards/00-dashboards.py"

```

Run notebooks:

```
python -m jupyter notebook ./examples/notebooks
```


# PyPi distribution

```

# update PROJECT_VERSION in setup.py
export PYPI_USER=
export PYPI_TOKEN=
python3 -m build .

python3 -m twine upload --username ${PYPI_USER}  --password ${PYPI_TOKEN} --skip-existing   "dist/*.whl" 


python3 -m twine upload dist/*
```


# Panel dashboards


Start from here:
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html

Also see https://github.com/awesome-panel/examples

```
git clone https://github.com/awesome-panel/examples

python3 -m venv awesome-panel
source ./awesome-panel/bin/activate
python3 -m pip install -r requirements.txt -U

panel serve src/hello-world/app.py --autoreload

panel convert src/hello-world/app.py --to pyodide-worker --out docs/hello-world --requirements requirements.txt --watch 
python3 -m http.server
# http://localhost:8000/docs/hello-world/app.html
```


# JupyterLite

see 
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html#setting-up-jupyterlite

Online version is here https://panelite.holoviz.org/lab/index.html

TODO see docs from openvisus=wasm


# misc

- vtk will not work https://gitlab.kitware.com/vtk/vtk/-/issues/18806
