import os
# import math
import datetime as dt
import random
import logging
# import numpy as np
# the structure of the package might need to be refined. car.car is not intuitive and awkward
from ptv_veh import car as vcar
from ptv_comm import network as vnet
from ptv_comm import dsrc


###################################### NOTES
""" Need to install Python 2.7, pywin, x264vfw, pandas, py_ptv (custom package)
  -  http://vision-traffic.ptvgroup.com/nl/training-support/support/ptv-vissim/faqs/visfaq/show/VIS25413/
Ensure that this file is in the same directory as the VISSIM files
May need to register VISSIM as COM Server
May need to manually start recording of avi
Can manually adjust quality of avi recordings - see manual and search for "x264"
"""

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("[%(asctime)s - %(levelname)s] [%(filename)s:%(lineno)s - %(funcName)s]  %(message)s")

fh = logging.FileHandler('comm_test log.txt')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)


######################
# General Parameters
######################
vissim_filename = 'Comm Test'  # no filename extension
sim_length_sec = 30  # simulation length in seconds
num_cores = 12

######################
# Sim Specific Functions
######################
def Initialization():
    logger.info("Initializing")
    # This should be done at the start of the simulation
    global RESULTS_DIR
    global SIM_TIME

    custom_veh_types = [111,112,113]
    RESULTS_DIR = "Script.results" # the subdirectory where you want results saved

    # Can define own car skills (below is default)
    # car_skills = [
    #     Skill(0,'dsrc',1),
    #     Skill(10,'dsrc',2),
    #     Skill(20,'dsrc',3),
    #     Skill(100,'bt',50),
    #     Skill(200,'cell',100),
    #     Skill(300,'web',150)
    # ]
    #################################################################################
    # No parameter definitions below
    #################################################################################
    # save this time to use for file naming
    SIM_TIME = str(dt.datetime.now().strftime("%y-%m-%d-%H-%M"))

    # make sure that the necessary folder structure exists
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
    if not os.path.exists(RESULTS_DIR+"\\Data"):
        os.makedirs(RESULTS_DIR+"\\Data")
    if not os.path.exists(RESULTS_DIR+"\\Video"):
        os.makedirs(RESULTS_DIR+"\\Video")

    vnet.setup(Vissim)
    try:
        car_skills
    except NameError:
        vcar.setup(Vissim,custom_veh_types)
    else:
        vcar.setup(Vissim,custom_veh_types,car_skills)

    # Create a comm network to use. Can create multiple isolated networks for C-V2X, Bluetooth, etc
    vnet.Net('dsrc',[vcar.Car.all_cars])

    random.seed(Vissim.Simulation.AttValue('RandSeed')) # set random seed from PTV Vissim in order to be able to replicate the results.



# the container function that will be called by VISSIM every step
def runSingleStep():

    ctime = Vissim.Simulation.AttValue('SimSec') # get current simulation second

    # Deactivate out of scope cars and get new info from Vissim for all active cars
    vcar.update() # Do this every loop at the beginning
    cars = vcar.getCars() # returns dict of lists of car objects [all_cars, active_cars, new_cars, null_cars]

    # Handle cars that have been deactivted
    null_cars = cars['null']
    logger.debug("There are "+str(len(null_cars))+" recently deactivated cars")
    for car in null_cars:
        link = car.link # get Vissim link where vehicle exited simulation

    # Handle new vehicles that just entered the network
    # Comms, skills, and message logic need to be set for new vehicles
    new_cars = cars['new']
    logger.debug("There are "+str(len(new_cars))+" new cars")
    for car in new_cars:
        car.setComms(vnet.id(0))
        car.setSkill(0) # might be useful to have this set via a distribution
        car.setMsgLogic(dsrc)

    # Handle cars that are currently active in simulation
    active_cars = cars['active']
    logger.debug("There are "+str(len(active_cars))+" active cars")
    for car in active_cars:
        car.sendMsg() #broadcast location to everyone within range

    # Simulate a brekdown on the highway at 50 seconds
    if ctime >= 50:
        dcar = active_cars[0] # car to be disabled
        if int(ctime) == 50: # at 50 seconds
            dcar.set_desired_speed(0) # simulate a breakdown 

        if dcar.dspeed == 0: # if vehicle is disabled
            logger.debug("Car # "+str(dcar.id)+" is disabled and sending RSA")
            # payload = dcar.RSA() # create a road side alert with the required data
            # dcar.sendMsg(-1,'RSA',payload) # send the message 
            dcar.sendMsg(-1,'RSA') # send the message 


    logger.debug("There are "+str(len(cars['all']))+" total cars")

    vnet.update() # Do this every loop at the end after all code related to messages is finished


# the function that will be called when the simulation is ended/stopped
def saveSimulationResults():
    vcar.saveResults(RESULTS_DIR+"\\Data\\"+SIM_TIME+" Cars.csv")
    vnet.saveResults(RESULTS_DIR+"\\Data\\"+SIM_TIME+" Comms.csv")
   

######################
# Boilerplate Code
######################
def StartVissim():
    # Function to start PTV Vissim via COM Interface.
    # COM-Server
    import win32com.client as com
    ## Connecting the COM Server => Open a new Vissim Window:
    global Vissim # follows naming convention of standard Vissim COM interface

    logger.info("Starting Vissim")
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

    logger.info("Simulation Running")
    # set all scripts to run manually:
    Vissim.Net.Scripts.SetAllAttValues('RunType', 1) # 1 == Manually

    Vissim.Simulation.SetAttValue('NumCores',num_cores)

    sim_res = Vissim.Simulation.AttValue('SimRes')
    for i in range(sim_length_sec*sim_res): # to run every single time step
        Vissim.ResumeUpdateGUI() # allow updating of the complete Vissim workspace (network editor, list, chart and signal time table windows)
        Vissim.Simulation.RunSingleStep()
        Vissim.SuspendUpdateGUI() # stop updating of the complete Vissim workspace (network editor, list, chart and signal time table windows)
        runSingleStep()

    saveSimulationResults()


# This is conditionally called at the end of the script
def main():
    # If this script is started externally, this functions calls the required sub-functions to run the example externally.
    logger.info("This script called was called externally. Running the setup methods")
    StartVissim() # Start PTV Vissim via COM
    Initialization()
    SimulateExternally()


# This should be at the end to avoid any declaration or "not defined" problems
if __name__ == '__main__':
    main()