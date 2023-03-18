from panel.io.convert import convert_app
from pathlib import Path
from bokeh.application import application
from logging import Logger

class MockLogger(Logger):
	def error(self, *args, **kwargs):
		error_message = args[3]
		raise Exception(error_message)

import os
os.environ["VISUS_BACKEND"]="py"
original_log = application.log
application.log=MockLogger("bokeh.application.application")
os.makedirs("tmp",exist_ok=True)
requirements=['openvisuspy','numpy','requests','xmltodict','bokeh','panel','xyzservices','colorcet']
convert_app("./examples/dashboards/00-dashboards.py", dest_path="tmp/", runtime = 'pyodide-worker',requirements=requirements)
application.log=original_log

import sys
sys.exit(0)
