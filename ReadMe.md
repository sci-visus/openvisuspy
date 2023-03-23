# Instructions

Preliminary setup:

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;C:\projects\openvisuspy\src

# this is needed for SealStorage (https://www.sealstorage.io/). The key is meant for public read-only access 
set AWS_ACCESS_KEY_ID=any
set AWS_SECRET_ACCESS_KEY=any
set AWS_ENDPOINT_URL=https://maritime.sealstorage.io/api/v0/s3

# in case you want verbose logs
set VISUS_CPP_VERBOSE=0
set VISUS_NETSERVICE_VERBOSE=0

# dangerous for debugging-only settings
set BOKEH_ALLOW_WS_ORIGIN=*
set BOKEH_LOG_LEVEL=debug
```

# Bokeh (cpp or py)

```
# [OK] cpp-bokeh-single 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --single

# [OK] cpp-bokeh-multi 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --multi

# [OK] py-bokeh-single 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --single

# [OK] py-bokeh-multi 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --multi

# [OK] jupyter-notebooks
set VISUS_BACKEND=cpp
python -m jupyter notebook ./examples/notebooks 

# [OK] py-jupyter notebooks
set VISUS_BACKEND=cpp
python -m jupyter notebook ./examples/notebooks 
```

# Panel (cpp or py)

```
# [OK] cpp-panel-single 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --single

# [OK] cpp-panel-multi 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --multi

# [OK] py-panel-single 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --single

# [OK] py-panel-multi 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --multi

# [OK] cpp-jupyter-notebooks
set VISUS_BACKEND=cpp
python -m jupyter notebook ./examples/notebooks 

# [OK] py-jupyter notebooks
set VISUS_BACKEND=py
python -m jupyter notebook ./examples/notebooks 

```

# PyScript (py only)

Just open http://localhost:8000/examples/pyscript/index.html  
- will work only with VISUS_BACKEND=py
- REMEMBER to resize the window, otherwise it will not work

```
# [OK] pyscript
python3 examples/server.py --directory ./
```

# JupyterLite (py only)

It seems that jupyter lite builds the output based on installed packages.
There should be other ways (by JSON file or command line) but for now creating a virtual env is good enough

```
ENV=/tmp/openvisuspy-lite2

python3 -m venv ${ENV}
source ${ENV}/bin/activate
python3 -m pip install \
    jupyterlite==0.1.0b20 pyviz_comms numpy pandas requests xmltodict xyzservices pyodide-http colorcet \
    https://cdn.holoviz.org/panel/0.14.3/dist/wheels/bokeh-2.4.3-py3-none-any.whl \
    panel==0.14.2 \
    openvisuspy==0.0.20 \
    jupyter_server # this is needed to see the list of files

rm -Rf ${ENV}/_output
jupyter lite build --contents ./examples/notebooks --output-dir ${ENV}/_output


# change port for avoiding caching
python3 -m http.server --directory ${ENV}/_output --bind localhost 10722
# jupyter lite serve --contents ./examples/notebooks --output-dir ${ENV}/_output --port 19722 
```


# Upload wheel

**IMPORTANT: update `PROJECT_VERSION` in `pyproject.toml`**

```
rm -f dist/*  
python3 -m build .
python3 -m twine upload --username <your-username>  --password <your-password> --skip-existing   "dist/*.whl" 
# check on pyodide REPL `https://pyodide.org/en/stable/console.html` if you can import the pure python wheel
```


# Useful/Inspiring links:

List:

- https://blog.jonlu.ca/posts/async-python-http
- https://blog.jonlu.ca/posts/async-python-http
- https://blog.jupyter.org/mamba-meets-jupyterlite-88ef49ac4dc8
- https://developer.mozilla.org/en-US/docs/Web/API/fetch#options
- https://github.com/awesome-panel/examples
- https://github.com/holoviz/panel/blob/main/panel/io/convert.py
- https://github.com/holoviz/panel/issues/2261
- https://github.com/holoviz/panel/issues/4089
- https://github.com/holoviz/panel/issues/4239
- https://github.com/holoviz/panel/pull/3381/files
- https://github.com/jupyterlite/demo/blob/main/.github/workflows/deploy.yml
- https://github.com/jupyterlite/jupyterlite/issues/67
- https://github.com/jupyter-widgets/tutorial-jupyterlite/blob/main/requirements.txt
- https://github.com/widgetti/ipyvolume/issues/427
- https://gitlab.kitware.com/vtk/vtk/-/issues/18806 (vtk will not work)
- https://jeff.glass/post/whats-new-pyscript-2023-03-1/
- https://jupyterlite.github.io/demo
- https://jupyterlite.readthedocs.io/en/latest/#try-it-in-your-browser
- https://jupyterlite.readthedocs.io/en/latest/howto/configure/simple_extensions.html
- https://jupyterlite.readthedocs.io/en/latest/howto/content/filesystem-access.html
- https://jupyterlite.readthedocs.io/en/latest/quickstart/deploy.html
- https://jupyterlite.readthedocs.io/en/latest/reference/cli.html
- https://lwebapp.com/en/post/pyodide-fetch
- https://medium.com/geekculture/run-jupyter-notebooks-on-a-web-browser-using-jupyterlite-18e3bd25bd97
- https://panel.holoviz.org/user_guide/Async_and_Concurrency.html
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html
- https://panelite.holoviz.org/lab/index.html
- https://pyodide.org/en/stable/project/about.html
- https://pyodide.org/en/stable/usage/packages-in-pyodide.html
- https://requests.readthedocs.io/en/latest/user/advanced/
- https://stackoverflow.com/questions/31998421/abort-a-get-request-in-python-when-the-server-is-not-responding
- https://stackoverflow.com/questions/75279664/can-html-with-pyscript-run-python-files-without-freezing-everything-on-the-webpa


