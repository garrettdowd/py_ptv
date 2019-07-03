import os
# import math
import datetime as dt
import random

from ptv_veh import car as vcar
from ptv_veh import uav as vuav
from ptv_comm import network as vnet

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MIT"
__version__ = "0.0.1"
'''
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler('comm_test log.txt')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

###################################### NOTES
""" Need to install Python 2.7, pywin, x264vfw, pandas, py_ptv (custom package)
  -  http://vision-traffic.ptvgroup.com/nl/training-support/support/ptv-vissim/faqs/visfaq/show/VIS25413/
Ensure that this file is in the same directory as the VISSIM files
May need to register VISSIM as COM Server
May need to manually start recording of avi
Can manually adjust quality of avi recordings - see Vissim manual and search for "x264"
"""


######################
# General Parameters
######################
vissim_filename = 'Drone Follow'  # no filename extension
sim_length_sec = 120  # number of seconds to run the simulation


######################
# Sim Specific Functions
######################
def Initialization():
    print("Initializing")
    # This should be done at the start of the simulation
    global custom_veh_type
    global num_uavs
    global model_directory
    global results_directory

    global uavs
    global cars
    global comms

    global SIM_TIME
    global SIM_RES

    custom_veh_type = 111
    num_uavs = 8 # must determine apriori due to limitations with the 3D models (static objects)
    num_cameras = 1 # how many uavs should have cameras on them
    results_directory = "Script.results" # the subdirectory where you want results saved
    model_directory = "3D Models" # the subdirectory where the 3D model files are stored

    #################################################################################
    #################################################################################
    uavs = [] # list of vuav objects
    cars = [] # list of Car objects
    comms = [] # list of Comm objects

    # save this time to use for file naming
    SIM_TIME = str(dt.datetime.now().strftime("%y-%m-%d-%H-%M"))

    # Get timestep resolution of simulation
    SIM_RES = Vissim.Simulation.AttValue('SimRes')

    # make sure that the necessary folder structure exists
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)
    if not os.path.exists(results_directory+"\\Data"):
        os.makedirs(results_directory+"\\Data")
    if not os.path.exists(results_directory+"\\Video"):
        os.makedirs(results_directory+"\\Video")

    # Delete existing stuff to start with clean slate
    all_models = Vissim.Net.Static3DModels.GetAll()
    for model in all_models:
        Vissim.Net.Static3DModels.RemoveStatic3DModel(model)
    all_cameras = Vissim.Net.CameraPositions.GetAll()
    for camera in all_cameras:
        Vissim.Net.CameraPositions.RemoveCameraPosition(camera)
    all_storyboards = Vissim.Net.Storyboards.GetAll()
    for storyboard in all_storyboards:
        Vissim.Net.Storyboards.RemoveStoryboard(storyboard)


    vcar.setup(Vissim)
    vuav.setup(Vissim, num_uavs, num_cameras)
    vnet.setup(Vissim)

    # define a unique id
    if not comms:
        id_num = 0
    else:
        max_id = max([comm.id for comm in comms])
        id_num = max_id + 1
    comms.append(vnet.Comm(id_num, [uavs,cars]))

    random.seed(Vissim.Simulation.AttValue('RandSeed')) # set random seed from PTV Vissim in order to be able to replicate the results.



# a function to determine when vehicles have left the simulation
def deactivate(veh_type):
    # When a car exits the simulation then deactivate it and any uavs currently assigned to follow it
    all_veh_attributes = Vissim.Net.Vehicles.GetMultipleAttributes(('No', 'VehType'))
    new_car_nums = [int(veh[0]) for veh in all_veh_attributes if int(veh[1])==veh_type]
    old_car_nums = [car.id for car in cars]

    for num in old_car_nums:
        if num not in new_car_nums:
            car = next((car for car in cars if car.id==num), None)
            car.deactivate()
            assigned_uavs = [uav for uav in uavs if uav.car_num == num]
            for uav in assigned_uavs:
                if uav.mission == 1:
                    uav.deactivate()


# a function to determine when vehicles have entered the simulation
def findNewCars(veh_type):
    # Find new vehicles of given vehicle type not in current cars list
    all_veh_attributes = Vissim.Net.Vehicles.GetMultipleAttributes(('No', 'VehType'))
    new_car_nums = [int(veh[0]) for veh in all_veh_attributes if int(veh[1])==veh_type]
    current_car_nums = [car.id for car in cars]

    for num in current_car_nums:
        if num in new_car_nums:
            new_car_nums.remove(num)

    new_cars = []
    for car_num in new_car_nums:
        new_car = vcar.Car(car_num)
        cars.append(new_car)
        new_cars.append(new_car)

    return new_cars



# the container function that will be called by VISSIM every step
def runSingleStep():

    # Deactivate out of scope cars and uavs
    deactivate(custom_veh_type)

    # Add new Vissim generated vehicles to backend
    new_cars = findNewCars(custom_veh_type)

    # Update current vehicles
    # active_cars = [car for car in cars if car.active == 1]
    for car in (car for car in cars if car.active == 1):
        car.update()

    # Simulate uavs
    # active_uavs = [uav for uav in uavs if uav.active == 1]
    for uav in (uav for uav in uavs if uav.active == 1):
        # find location of car its tracking. This should be implemented as messages
        x = next((car.x[-1] for car in cars if car.id==uav.car_num), None)
        y = next((car.y[-1] for car in cars if car.id==uav.car_num), None)
        uav.car_pos = [x, y]
        uav.update()


    # Logic for uavs and vehicles choices
    # for now lets just assign one uav to follow every custom vehicle
    for car in new_cars:
        # if there is an available drone then assign it to this new car
        if len(uavs) < num_uavs:
            # define a unique id
            if len(uavs) == 0:
                id_num = 0
            else:
                max_id = max([uav.id for uav in uavs])
                id_num = max_id + 1
            print("Creating vuav with id = "+str(id_num))
            uav = vuav.vuav(id_num)
            uav.setCar(car.id)
            uavs.append(uav)
            print("Camera number is "+str(uav.camera))

    


# the function that will be called when the simulation is ended/stopped
def saveSimulationResults():
    import pandas as pd

    print("Saving Simulation Results")

    column_uavs = ['uavID', 'time', 'x', 'y', 'z']
    column_cars = ['carID', 'time', 'x', 'y']
    column_comms = ['sender_id', 'recipient_id', 'msg_type', 'payload', 'delay', 'dropped']

    df = []
    for uav in uavs:
        for t in range(len(uav.time)):
            df_d = {
                'uavID': uav.id,
                'time': uav.time[t],
                'x': uav.x[t],
                'y': uav.y[t],
                'z': uav.z[t]
            }
            df.append(df_d)

    df = pd.DataFrame(df)
    df = df.reindex(columns=column_uavs)  # ensure columns are in correct order
    # df = df.iloc[::-1] # reverse order of rows
    df.to_csv(results_directory+"\\Data\\"+SIM_TIME+" Uavs.csv", encoding='utf-8', index=False)

    df = []
    for car in cars:
        for t in range(len(car.time)):
            df_d = {
                'carID': car.id,
                'time': car.time[t],
                'x': car.x[t],
                'y': car.y[t]
            }
            df.append(df_d)

    df = pd.DataFrame(df)
    df = df.reindex(columns=column_cars)  # ensure columns are in correct order
    # df = df.iloc[::-1] # reverse order of rows
    df.to_csv(results_directory+"\\Data\\"+SIM_TIME+" Cars.csv", encoding='utf-8', index=False)


    df = []
    for comm in comms:
        for msg in comm.all_messages:
            df_d = {
                'sender_id': msg.sender_id,
                'recipient_id': msg.recipient_id,
                'msg_type': msg.msg_type,
                'payload': msg.payload,
                'delay': msg.delay,
                'dropped': msg.dropped
            }
            df.append(df_d)

    df = pd.DataFrame(df)
    df = df.reindex(columns=column_comms)  # ensure columns are in correct order
    # df = df.iloc[::-1] # reverse order of rows
    df.to_csv(results_directory+"\\Data\\"+SIM_TIME+" Comms.csv", encoding='utf-8', index=False)



######################
# Boilerplate Code
######################
def StartVissim():
    # Function to start PTV Vissim via COM Interface.
    # COM-Server
    import win32com.client as com
    ## Connecting the COM Server => Open a new Vissim Window:
    global Vissim

    print("Starting Vissim")
    ## once the cache has been generated, its faster to call Dispatch which also creates the connection to Vissim.
    Vissim = com.gencache.EnsureDispatch("Vissim.Vissim")
    # Vissim = com.Dispatch("Vissim.Vissim")
    current_directory = os.getcwd()
    filename = os.path.join(current_directory, vissim_filename+'.inpx')
    Vissim.LoadNet(filename,False)
    filename = os.path.join(current_directory, vissim_filename+'.layx')
    Vissim.LoadLayout(filename)



def SimulateExternally():
    # Function to run this script from external and not using internal scripts.
    # Running the script externally makes debugging easier.
    # Internal scripts run faster and are easier to use from within the PTV Vissim GUI.

    print("Beginning Simulation")
    # set all scripts to run manually:
    Vissim.Net.Scripts.SetAllAttValues('RunType', 1) # 1 == Manually

    for i in range(sim_length_sec*SIM_RES): # to run every single time step
        Vissim.ResumeUpdateGUI() # allow updating of the complete Vissim workspace (network editor, list, chart and signal time table windows)
        Vissim.Simulation.RunSingleStep()
        Vissim.SuspendUpdateGUI() # stop updating of the complete Vissim workspace (network editor, list, chart and signal time table windows)
        runSingleStep()

    saveSimulationResults()


# This is conditionally called at the end of the script
def main():
    # If this script is started externally, this functions calls the required sub-functions to run the example externally.
    print("This script called was called externally. Running the setup methods")
    StartVissim() # Start PTV Vissim via COM
    Initialization()
    SimulateExternally()


# This should be at the end to avoid any declaration or "not defined" problems
if __name__ == '__main__':
    main()