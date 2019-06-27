import logging
from collections import namedtuple
import pandas as pd

logger = logging.getLogger(__name__)

""" Intended Use Documentation Here




"""

Skill = namedtuple('Skill', 'id, comm_type, comm_range')

def setup(_Vissim, _custom_veh_type_list = [111], _car_skills=-1):
    global Vissim
    global car_skills
    global custom_veh_types

    if _car_skills == -1:
        # [Skill#,[comm_type(DEFINE), comm_range(m)]]
        car_skills = [
            Skill(0,'dsrc',300),
            Skill(10,'dsrc',500),
            Skill(20,'dsrc',900),
            Skill(100,'bt',400),
            Skill(200,'cell',800),
            Skill(300,'web',100000)
        ]
    else:
        car_skills = _car_skills

    #################################################################################
    #################################################################################
    Vissim = _Vissim
    custom_veh_types = _custom_veh_type_list



def update(): # call at beginning of every loop
    Car.null_cars = []
    Car.new_cars = []

    all_veh_attributes = Vissim.Net.Vehicles.GetMultipleAttributes(('No', 'VehType'))
    # deactivate all out of scope vehicles
    for veh_type in custom_veh_types:
        new_car_nums = [int(veh[0]) for veh in all_veh_attributes if int(veh[1])==veh_type]
        old_car_nums = [car.id for car in Car.all_cars]

        for num in old_car_nums:
            if num not in new_car_nums:
                car = next((car for car in Car.all_cars if car.id==num), None)
                car.deactivate()
            if num in new_car_nums:
                new_car_nums.remove(num)
        for num in new_car_nums:
            Car(num)

    for car in Car.all_cars:
        car.update()

def getCars():
    cars = dict()
    cars['all'] = Car.all_cars
    cars['active'] = Car.active_cars
    cars['new'] = Car.new_cars
    cars['null'] = Car.null_cars
    return cars

def saveResults(filepath):
    logger.info("Saving Car Results")

    column_cars = ['carID', 'time', 'x', 'y']

    df = []
    for car in Car.all_cars:
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
    df.to_csv(filepath, encoding='utf-8', index=False)


class Car:
    all_cars = []
    active_cars = []
    new_cars = []
    null_cars = []

    def __init__(self, car_num=0,comm=-1,skill=0,veh_type=100,link=1,lane=1,desired_speed=0):
        logger.debug("Creating a Car object with # "+str(car_num))
        if car_num == 0:
            # Putting a new vehicle in the network:
            self.type = veh_type
            self.dspeed = desired_speed # unit according to the user setting in Vissim [km/h or mph]
            self.link = link
            self.lane = lane
            start_pos = 0 # unit according to the user setting in Vissim [m or ft]
            interaction = True # optional boolean, should vehicle interact with other vehicles and such?
            self.vissim = Vissim.Net.Vehicles.AddVehicleAtLinkPosition( self.type, self.link, self.lane, start_pos, self.dspeed, interaction)
            self.id = int(self.vissim.AttValue('No')) # get vehicle number from vissim
        else: # if car_num != 0
            # Get existing info from vehicle already defined in the network
            self.id = car_num
            self.vissim = Vissim.Net.Vehicles.ItemByKey(self.id)
            self.type = int(self.vissim.AttValue('VehType'))
            self.dspeed = float(self.vissim.AttValue('DesSpeed'))
            linklane = self.vissim.AttValue('Lane')
            self.link = int(linklane.split("-")[0])
            self.lane = int(linklane.split("-")[1])
            self.speed = float(self.vissim.AttValue('Speed'))

        self.all_cars.append(self) # add to list of all cars
        self.active_cars.append(self)
        self.new_cars.append(self)
        # initialize time and position
        self.time = [float(Vissim.Simulation.AttValue('SimSec'))]
        self.x = [float(self.vissim.AttValue('CoordFrontX'))]
        self.y = [float(self.vissim.AttValue('CoordFrontY'))]
        self.position = lambda: [self.x[-1],self.y[-1]] # current position
        self.active = 1 # is this object currently active in the simulation?

        self.setComms(comm)
        # copy skills to local variables
        self.setSkill(skill)


    def update(self):
        if self.active:
            # get data from VISSIM
            self.dspeed = float(self.vissim.AttValue('DesSpeed'))
            linklane = self.vissim.AttValue('Lane')
            self.link = int(linklane.split("-")[0])
            self.lane = int(linklane.split("-")[1])
            self.speed = float(self.vissim.AttValue('Speed'))
            self.time.append(float(Vissim.Simulation.AttValue('SimSec')))
            self.x.append(float(self.vissim.AttValue('CoordFrontX')))
            self.y.append(float(self.vissim.AttValue('CoordFrontY')))
            return 1
        else:
            return 0

    def deactivate(self):
        self.active = 0
        self.active_cars.remove(self)
        self.null_cars.append(self)

    #######################################################
    """ Communication functions go here

    """
    def sendMsg(self, recipient_id=-1, msg_type=0, payload='null'):
        if self.comms == -1:
            logger.error("Comms was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
        if (int(msg_type) == 0) & (payload == 'null'):
            payload = self.position()
             
        # default message is broadcast to everyone listening (-1)
        self.comms.broadcast(self.position(), self.comm_range, msg_type, payload, recipient_id, self.id)
        logger.debug("Car # " + str(self.id) + " sending payload "+str(payload) +" to " + str(recipient_id))

    # all of the logic for handling messages happens here
    def receiveMsg(self, sender_id, msg_type, payload):
        if msg_type == 0: # location
            logger.debug("Car # " + str(self.id) + " received a message from " + str(sender_id) )


    def setComms(self,comm):
        logger.debug("Setting comms for car # "+str(self.id))
        self.comms = comm

    def setSkill(self,skill):
        flag = 0
        for item in car_skills:
            if item.id == skill:
                self.comm_type = item.comm_type
                self.comm_range = item.comm_range
                flag = 1
        if flag == 0:
            logger.critical("When instantiating a car object, given skill "+str(skill)+" does not exist")
            Vissim.Simulation.Stop()


    #######################################################
    """ Helper functions go here

    """
    # def get_car_front(self):


    # def get_car_radius(self, radius):


    #######################################################
    """ Wrapper functions go here

    """
    # set destination, des speed, 
