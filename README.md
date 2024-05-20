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
python.exe -m panel serve ./app --dev --args ./dashboards.json
```

In MacOs/Linux:

```bash
source .venv/bin/activate
python.exe -m panel serve ./app --dev --args dashboards.json
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

## Volume rendering

```bash
python test/test-pyvista.py
python test/test-vtkvolume.py 
```

## Developers only

Use env variables as needed

```bash
export PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;.\src
export BOKEH_ALLOW_WS_ORIGIN=*
export BOKEH_LOG_LEVEL=debug
export VISUS_CPP_VERBOSE=1
export VISUS_NETSERVICE_VERBOSE=1
export VISUS_VERBOSE_DISKACCESS=0
export VISUS_CACHE=c:/tmp/visus-cache
```

Deploy new binaries

- **Update the `PROJECT_VERSION` inside `pyproject.toml`**

```bash

# commit a new tagget version
VERSION=$(python3 ./scripts/new_tag.py)

# GitHub
git commit -a -m "New tag ($VERSION)" 
git tag -a ${VERSION} -m "${VERSION}"
git push origin ${VERSION}
git push origin

# PyPi (upload does not work in WSL2, use windows to just to the upload)
rm -f dist/*  
python3 -m build .
python3 -m twine upload --username "${PYPI_USERNAME}"  --password "${PYPI_PASSWORD}" --non-interactive --verbose  --skip-existing --verbose "dist/*.whl" 

# Docker
sudo docker build --build-arg="OPENVISUS_VERSION=2.2.133" --build-arg="OPENVISUSPY_VERSION=${VERSION}" --tag nsdf/openvisuspy:${VERSION} ./
sudo docker run -it --rm -p 8888:8888 -v ./notebooks:/home/notebooks nsdf/openvisuspy:${VERSION}
sudo docker push nsdf/openvisuspy:${VERSION}
```

