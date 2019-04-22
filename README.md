# vissim_adl
A collection of useful Vissim interfaces for autonomous and connected traffic

# Modules
## car
This module provides a python object to easily interact with vehicles in Vissim. 
Documentation on the provided methods needs to be written

## uav
This module allows you to add a UAV to your Vissim simulation environment. 
Decision logic and dynamics are fully handled within this class. 
The UAV can be visualized as a 3D model during simulation.  
Documentation on the provided methods needs to be written

## comm
This module provides a generic method for one agent to send a message to other agents


# Installation notes
This package is currently in an alpha state. It is meant to be locally installed for development purposes.

## Prerequisites
- PTV Vissim
- Python 2.7
- PyWin32 (For Vissim COM connection)
- x264vfw codec (For avi recording)

## Download
1) Clone or download this repository somewhere in your Vissim project directory. The location should not change.
1) In command prompt `cd` to the downloaded directory with the `setup.py` file
1) Install the package with pip `pip install -e .`

## Use
1) Import the car module using `import car`
1) Import the uav module using `importuav`
1) Import the comm module using `import comm`
