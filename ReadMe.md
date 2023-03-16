# Instructions

See [https://github.com/sci-visus/OpenVisus]()

```
python -m pip install --upgrade openvisus_py
```


Run bokeh dashboard:

```
python -m bokeh serve "examples/python/bokeh-example.py"  --dev --log-level=debug --address localhost --port 8888 
```

Run notebooks:

```
python -m jupyter notebook ./examples/notebooks
```


# PyPi distribution

```
python3 setup.py sdist 
export PYPI_USER=
export PYPI_TOKEN=
python3 -m twine upload --username ${PYPI_USER}  --password ${PYPI_TOKEN} --skip-existing   "dist/*.tar.gz" 


python3 -m twine upload dist/*
```

# Internal debugging

example in Windows prompt:

```
set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;C:\projects\openvisus_py\src
set VISUS_BACKEND=cpp
```