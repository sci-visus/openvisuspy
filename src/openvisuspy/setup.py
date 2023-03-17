# https://the-hitchhikers-guide-to-packaging.readthedocs.io/en/latest/quickstart.html
import os,sys,glob,shutil

PROJECT_VERSION="1.0.7"

from setuptools import setup
setup(
	name = "openvisuspy",
	description = "ViSUS multiresolution I/O, analysis, and visualization system",
	version=PROJECT_VERSION,
	url="https://github.com/sci-visus/openvisuspy",
	author="visus.net",
	author_email="support@visus.net",
	packages=["openvisuspy", ],
	package_dir={"openvisuspy": '.'},
	package_data={"openvisuspy":  [os.path.abspath(it) for it in 
	glob.glob("*.py") + \
	glob.glob("examples/notebooks/*.ipynb") +
	glob.glob("examples/python/*.py")]},
	license = "BSD",
	python_requires='>=3.6',
	install_requires=[
		'numpy','pandas','bokeh','panel','boto3','requests','colorcet',
		#  vtk itkwidgets pyvista only for 3d rendering,
	])


