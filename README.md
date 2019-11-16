# py_ptv
A collection of useful Vissim command wrappers and functions for autonomous and connected traffic

[See UAV example here](https://youtu.be/OhUeE0oGQSM)

# Modules
## car
**ptv_veh.car**  
This module provides a python object to easily interact with vehicles in Vissim. 
*Documentation on the provided methods needs to be written*  
### 

## uav
**ptv_veh.uav**  
This module allows you to add a UAV to your Vissim simulation environment. 
Decision logic and dynamics are fully handled within this module. 
The UAV can be visualized as a 3D model during simulation.  
Video recordings can be taken from the persepctive of the UAV.  
*Documentation on the provided methods needs to be written*  

## network
**ptv_comm.network**  
This module provides a generic class for one agent to send a message to other agents  
*Documentation on the provided methods needs to be written*  
*Documentation on the requirements of the message handlers needs to be written*  

# Installation notes
This package is currently in an alpha state. It is meant to be locally installed for development purposes.

## Prerequisites
- PTV Vissim
- Python 2.7
- PyWin32 (For Vissim COM connection)
- x264vfw codec (For avi recording)

## Download
1) Clone or download this repository somewhere in your Vissim project directory (or somewhere safe). The location should not change.
1) In command prompt `cd` to the downloaded directory with the `setup.py` file
1) Install the package with pip `pip install -e .`

## Use
**See example.py** for a good starting point.
1) Import the car module using `from ptv_veh import car`
1) Import the uav module using `from ptv_veh import uav`
1) Import the network module using `from ptv_comm import network`

# Examples

Example Simulation

Message handler


# Details
## car
**ptv_veh.car**  
*Documentation on the provided methods needs to be written* 
### Use

### Parameters

### Methods

### Vissim Updates

## uav
**ptv_veh.uav**  
*Documentation on the provided methods needs to be written*  

## network
**ptv_comm.network**  
*Documentation on the provided methods needs to be written*  
*Documentation on the requirements of the message handlers needs to be written*  


# To Do
- ptv_comm.network transition to IP addressing 
- pull out and modularize some generic functions - _dist, saveResults,
- add reference coordinates to saveResults, allowing for conversion to global coordinates (mercator/decimal)