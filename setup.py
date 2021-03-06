from setuptools import setup

""" General notes on packages can be found 
https://python-packaging.readthedocs.io/en/latest/minimal.html
https://the-hitchhikers-guide-to-packaging.readthedocs.io/en/latest/quickstart.html
https://realpython.com/python-application-layouts/
"""
setup(name='py_ptv',
      version='0.0.1',
      description='A collection of useful Vissim interfaces for autonomous and connected traffic',
      url='xxxxxxxxxxxx',
      author='Garrett Dowd',
      author_email='me@garrettdowd.com',
      license='MIT',
      packages=[
          'ptv_veh',
          'ptv_comm',
      ],
      install_requires=[
          'pandas',
      ],
      zip_safe=False)
