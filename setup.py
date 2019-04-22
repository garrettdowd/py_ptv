from setuptools import setup

setup(name='vissim_adl',
      version='0.0.1',
      description='A collection of useful Vissim interfaces for autonomous and connected traffic',
      url='xxxxxxxxxxxx',
      author='Garrett Dowd',
      author_email='me@garrettdowd.com',
      license='MIT',
      packages=[
          'car',
          'comm',
          'uav',
      ],
      install_requires=[
          'pandas',
      ],
      zip_safe=False)
