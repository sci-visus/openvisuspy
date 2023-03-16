# https://the-hitchhikers-guide-to-packaging.readthedocs.io/en/latest/quickstart.html

from setuptools import setup

setup(
	name='openvisus_py',
	description = "ViSUS multiresolution I/O, analysis, and visualization system",
	version='1.0.0',
	author="visus.net",
	author_email="support@visus.net",
	license='BSD',
	long_description='openvisus_py',
	url='https://github.com/sci-visus/OpenVisus',
	packages=["openvisus_py",],
	package_dir = {'openvisus_py': 'src/openvisus_py'},
	include_package_data=True,
	install_requires=['numpy','pandas','bokeh','panel','boto3','requests','colorcet'], #  vtk itkwidgets pyvista only for 3d rendering,
)

