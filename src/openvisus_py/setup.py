# https://the-hitchhikers-guide-to-packaging.readthedocs.io/en/latest/quickstart.html
import os,sys,glob,shutil

PROJECT_VERSION="1.0.1"

from setuptools import setup
setup(
	name = "openvisus_py",
	description = "ViSUS multiresolution I/O, analysis, and visualization system",
	version=PROJECT_VERSION,
	url="https://github.com/sci-visus/openvisus_py",
	author="visus.net",
	author_email="support@visus.net",
	packages=["openvisus_py", ],
	package_dir={"openvisus_py": '.'},
	package_data={"openvisus_py":  [os.path.abspath(it) for it in 
	glob.glob("*.py") + \
	glob.glob("examples/notebooks/*.ipynb") +
	glob.glob("examples/python/*.py")]},
	license = "BSD",
	python_requires='>=3.6',
	install_requires=[
		'numpy','pandas','bokeh','panel','boto3','requests','colorcet',
		#  vtk itkwidgets pyvista only for 3d rendering,
	])


