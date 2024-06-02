# Instructions

Important:

- use python `3.10` or `3.11`.  **DO NOT** use `python312` does not have a good match for `libzmq`
- use  JupyterLab v3 (**NOT v4**) because bokeh does not work (see https://github.com/bokeh/jupyter_bokeh/issues/197)

## Installation

In Windows:

```bash
set PATH=c:\Python310;%PATH%
where python

python.exe -m venv .venv
.venv\Scripts\activate

python.exe -m pip install --upgrade pip
python.exe -m pip install -r requirements.txt

# install the latest version of OpenVisus
python.exe -m pip install --upgrade OpenVisusNoGui openvisuspy
```

In MacOs/Linux:

```bash

python3 -m venv .venv
source .venv/Scripts/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# install the latest version of OpenVisus
python3 -m pip install --upgrade OpenVisusNoGui openvisuspy
```

## Dashboards 

In Windows:

```bash
.venv\Scripts\activate
python.exe -m panel serve ./app --dev --args ./json/dashboards.json
```

In MacOs/Linux:

```bash
source .venv/bin/activate
python.exe -m panel serve ./app --dev --args ./json/dashboards.json
```

## Notebooks

In Windows:

```bash
.venv\Scripts\activate
jupyter lab ./notebooks
```

In MacOs/Linux:

```bash
source .venv/bin/activate
jupyter lab ./notebooks
```

Important: if Panel is not working you may have to do:

```bash
pskill python
jupyter nbconvert --clear-output --inplace notebooks/test-panel.ipynb  
jupyter trust notebooks/test-panel.ipynb  
```




## Volume Rendering

```bash
python test/test-pyvista.py
python test/test-vtkvolume.py 
```

## Debug openvisuspy

Debug mode in Windows

```bash
.venv\Scripts\activate

set PATH=c:\Python310;%PATH%

set BOKEH_ALLOW_WS_ORIGIN=*
set BOKEH_LOG_LEVEL=debug
set VISUS_CPP_VERBOSE=1
set VISUS_NETSERVICE_VERBOSE=1
set VISUS_VERBOSE_DISKACCESS=0
set VISUS_CACHE=c:/tmp/visus-cache

set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;.\src

# dashboards
python.exe -m panel serve ./app --dev --args ./json/dashboards.debug.json

# jupyter lab
python.exe -m jupyter lab notebooks/ov-dashboards.ipynb

python.exe -m panel serve ./app --dev --args "https://atlantis.sci.utah.edu/mod_visus?action=readdataset&dataset=chess-intro&cached=arco" --probe
```

Deploy binaries

```bash
./scripts/new_tag.sh

# you may want to change the tag in docker-compose.yml too
```



