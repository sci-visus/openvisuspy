Links:

- https://github.com/jupyterlite/jupyterlite/issues/67\
- https://jupyterlite.readthedocs.io/en/latest/reference/cli.html
- https://medium.com/geekculture/run-jupyter-notebooks-on-a-web-browser-using-jupyterlite-18e3bd25bd97


```
 # will be faster for WSL
cd /tmp

VENV=.lite-env
rm -Rf ${VENV}
python3 -m venv ${VENV}
source ${VENV}/bin/activate
python3 -m pip install \
    jupyterlite==0.1.0b20 \
    pyviz_comms \
    numpy \
    pandas \
    requests \
    xmltodict \
    xyzservices \
    pyodide-http \
    colorcet \
    https://cdn.holoviz.org/panel/0.14.3/dist/wheels/bokeh-2.4.3-py3-none-any.whl \
    panel==0.14.2 \
    openvisuspy==0.0.20 

python3 -c "import bokeh;print(bokeh.__version__)"
python3 -c "import panel;print(panel.__version__)"

rm -Rf _output

mkdir files
cp /mnt/c/projects/openvisuspy/examples/lite/*.ipynb ./files/

jupyter lite init  --contents=./files
jupyter lite build --contents=./files
jupyter lite serve --contents=./files --port 10709







# I have no ide why I have to do this, there is some confusion between bokeh version
import shutil,os,sys,micropip
for it in os.listdir("/lib/python3.10/site-packages"):
    if it.startswith("bokeh"):
        shutil.rmtree(f"/lib/python3.10/site-packages/{it}", ignore_errors=True)

await micropip.install("https://cdn.holoviz.org/panel/0.14.3/dist/wheels/bokeh-2.4.3-py3-none-any.whl")
await micropip.install("bokeh==2.4.3")

import shutil,os,sys,micropip
await micropip.install([
    "pyviz_comms",
    "numpy",
    "pandas",
    "requests",
    "xmltodict",
    "xyzservices",
    "pyodide-http",
    "colorcet",
    "https://cdn.holoviz.org/panel/0.14.3/dist/wheels/bokeh-2.4.3-py3-none-any.whl",
    "panel==0.14.2",
    "openvisuspy==0.0.20",
])

import bokeh
print(bokeh.__version__)

import os,sys,logging,time,piplite
await piplite.install(['panel', 'pyodide-http', 'openvisuspy','xmltodict','requests','colorcet'])
import panel as pn
pn.extension('vega')

import bokeh
button = bokeh.models.widgets.Button(label="Panel is working? Push...", sizing_mode='stretch_width')
def OnClick(evt=None): button.label="YES!"
button.on_click(OnClick)    
pn.pane.Bokeh(button) # NOTE: bokeh will not work (complaining about tornado)




import openvisuspy
from openvisuspy import Slice, Slices, GetBackend, SetupLogger
logger=SetupLogger()
logger.info(f"GetBackend={GetBackend()}")

view=Slice(show_options=["palette","timestep","field","direction","offset"]) 
view.setDataset(f"https://atlantis.sci.utah.edu/mod_visus?dataset=david_subsampled&cached=1" )   
view.setDirection(2)
view.setPalette("Greys256")
view.setPaletteRange((0,255))
view.setTimestep(view.getTimestep())
view.setField(view.getField()) 

view.getPanelLayout()

```


