# Instructions


```
python -m pip install jupyter notebook numpy pandas bokeh panel boto3 requests colorcet vtk itkwidgets pyvista

set PYTHONPATH=C:\projects\OpenVisus\build\RelWithDebInfo;C:\projects\openvisus_py
set VISUS_BACKEND=cpp

python -m bokeh serve "python/bokeh-example.py"  --dev --log-level=debug --address localhost --port 8888 

python -m jupyter notebook ./notebooks
```