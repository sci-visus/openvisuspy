
# Developers only

Setup:


```
# dangerous
export BOKEH_ALLOW_WS_ORIGIN=*
export BOKEH_LOG_LEVEL=debug

# chnange as needed
export VISUS_CPP_VERBOSE=0
export VISUS_NETSERVICE_VERBOSE=0

# debug current code
export PYTHONPATH=${PWD}/src
```

# Deploy new binaries


**Update the `PROJECT_VERSION` inside `pyproject.toml`**

```
export PYPI_USERNAME="scrgiorgio"
export PYPI_PASSWORD="..."
rm -f dist/*  
python3 -m build .
python3 -m twine upload --username "${PYPI_USERNAME}"  --password "${PYPI_PASSWORD}" --skip-existing "dist/*.whl" --verbose 
```

