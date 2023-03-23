# Instructions

Useful links:

- https://panel.holoviz.org/user_guide/Async_and_Concurrency.html
- https://github.com/holoviz/panel/pull/3381/files
- https://github.com/holoviz/panel/issues/4239
- https://github.com/holoviz/panel/issues/2261
- https://stackoverflow.com/questions/75279664/can-html-with-pyscript-run-python-files-without-freezing-everything-on-the-webpa
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html
- https://github.com/awesome-panel/examples
- https://github.com/holoviz/panel/issues/4089
- https://github.com/holoviz/panel/blob/main/panel/io/convert.py
- https://stackoverflow.com/questions/75279664/can-html-with-pyscript-run-python-files-without-freezing-everything-on-the-webpa
- https://gitlab.kitware.com/vtk/vtk/-/issues/18806 (vtk will not work)
- https://blog.jonlu.ca/posts/async-python-http
- https://blog.jonlu.ca/posts/async-python-http
- https://requests.readthedocs.io/en/latest/user/advanced/
- https://lwebapp.com/en/post/pyodide-fetch
- https://stackoverflow.com/questions/31998421/abort-a-get-request-in-python-when-the-server-is-not-responding
- https://developer.mozilla.org/en-US/docs/Web/API/fetch#options
- https://pyodide.org/en/stable/usage/packages-in-pyodide.html
- https://jeff.glass/post/whats-new-pyscript-2023-03-1/
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html
- https://pyodide.org/en/stable/project/about.html
- https://pyodide.org/en/stable/usage/packages-in-pyodide.html

See [https://github.com/sci-visus/OpenVisus]()

# Instructions

Setup:

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;C:\projects\openvisuspy\src

# this is needed for SealStorage (not supported for pure-python openvisuspy)
set AWS_ACCESS_KEY_ID=any
set AWS_SECRET_ACCESS_KEY=any
set AWS_ENDPOINT_URL=https://maritime.sealstorage.io/api/v0/s3

set VISUS_CPP_VERBOSE=1
set VISUS_NETSERVICE_VERBOSE=0

set BOKEH_ALLOW_WS_ORIGIN=*
set BOKEH_LOG_LEVEL=debug
```

Tests:

```
# [OK] cpp-bokeh-single 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --single

# [OK] cpp-bokeh-multi 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --multi

# [OK] cpp-panel-single 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --single

# [OK] cpp-panel-multi 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args -cpp --multi

# [OK] py-bokeh-single 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --single

# [OK] py-bokeh-multi 
python -m bokeh serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --multi

# [OK] py-panel-single 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --single

# [OK] py-panel-multi 
python -m panel serve "examples/dashboards/run.py"  --dev --address localhost --port 8888 --args --py --multi

# [OK] cpp-jupyter-notebooks
python -m jupyter notebook ./examples/notebooks 

# [OK] jupyter notebooks
set VISUS_BACKEND=py
python -m jupyter notebook ./examples/notebooks 

# [OK] pyscript
python3 examples/server.py --directory ./
# http://localhost:8000/examples/pyscript/index.html  (REMEMBER to resize the window)

```

# Upload wheel
- update `PROJECT_VERSION` in `pyproject.toml`

```
# 
rm -f dist/*  && python3 -m build .
python3 -m twine upload --username <your-username>  --password <your-password> --skip-existing   "dist/*.whl" 
# check on pyodide REPL `https://pyodide.org/en/stable/console.html` if you can import openvisus
```

# (TODO) JupyterLite

Links 
- https://panel.holoviz.org/user_guide/Running_in_Webassembly.html#setting-up-jupyterlite
- https://panelite.holoviz.org/lab/index.html
- see other directories with docs from openvisus=wasm



# BACKUP

```
set VISUS_BACKEND=py
python -m panel convert --skip-embed --to pyodide-worker --out "tmp/" --requirements ... --watch "./examples/dashboards/run.py"
python3 examples/pyscript/server.py --directory ./tmp
# http://localhost:8000/run.html 
```