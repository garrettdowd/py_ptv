import logging
from collections import namedtuple
import pandas as pd

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MIT"
__version__ = "0.0.1"


logger = logging.getLogger(__name__)
Skill = namedtuple('Skill', 'id, comm_type, comm_range')
# Skill = namedtuple('Skill', 'id, comm_type, dist_distr')

""" Intended Use Documentation Here




"""

def setup(_Vissim, _custom_veh_type_list = [111], _CAR_SKILLS=-1):
    global Vissim # follows naming convention of standard Vissim COM interface
    global CAR_SKILLS
    global CUSTOM_VEH_TYPES

    if _CAR_SKILLS == -1:
        # [skill_id(DEFINE),[comm_type(DEFINE), comm_range(DEFINE))]]
        CAR_SKILLS = [
            Skill(0,'dsrc',700),
            Skill(10,'dsrc',500),
            Skill(20,'dsrc',1000),
            Skill(100,'bt',200),
            Skill(200,'cell',500),
            Skill(300,'web',100000) # 'infinite' range
        ]
        # # [skil_id(DEFINE),[comm_type(DEFINE), comm_range_dist(Distance Distribution No)]]
        # CAR_SKILLS = [
        #     Skill(0,'dsrc',1),
        #     Skill(10,'dsrc',2),
        #     Skill(20,'dsrc',3),
        #     Skill(100,'bt',50),
        #     Skill(200,'cell',100),
        #     Skill(300,'web',150)
        # ]
    else:
        CAR_SKILLS = _CAR_SKILLS

    #################################################################################
    #################################################################################
    Vissim = _Vissim
    CUSTOM_VEH_TYPES = _custom_veh_type_list



def update(): # call at beginning of every loop
    Car.null_cars = []
    Car.new_cars = []

    all_veh_attributes = Vissim.Net.Vehicles.GetMultipleAttributes(('No', 'VehType'))
    # deactivate all out of scope vehicles
    for veh_type in CUSTOM_VEH_TYPES:
        new_car_nums = [int(veh[0]) for veh in all_veh_attributes if int(veh[1])==veh_type]
        old_car_nums = [car.id for car in Car.all_cars if car.type==veh_type]
        for num in old_car_nums:
            if num in new_car_nums:
                new_car_nums.remove(num)
            else:
                car = next((car for car in Car.all_cars if car.id==num), None)
                car.deactivate()
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

    def __eq__(self, other):
        return self.id == other.id

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

        Car.all_cars.append(self) # add to list of all cars
        Car.active_cars.append(self)
        Car.new_cars.append(self)
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
        Car.active_cars.remove(self)
        Car.null_cars.append(self)

    #######################################################
    """ Communication functions go here

    """
    def sendMsg(self, recipient_id=-1, msg_type='loc', payload='null'):
        if self.comms == -1:
            logger.error("Comms was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
        if (msg_type == 'loc') & (payload == 'null'):
            payload = self.position()
        if (msg_type == 'RSA') & (payload == 'null'):
            payload = [self.position(), self.link, self.lane]
        logger.debug("Car # " + str(self.id) + " sending payload "+str(payload) +" to " + str(recipient_id))
        # default message is broadcast to everyone listening (-1)
        self.comms.broadcast(self.position(), self.comm_range, msg_type, payload, recipient_id, self.id)

    # all of the logic for handling messages happens here
    def receiveMsg(self, sender_id, msg_type, payload):
        if msg_type == 'loc': # location
            logger.debug("Car # " + str(self.id) + " received location "+str(payload) +" from " + str(sender_id))
        if msg_type == 'RSA': # road side alert
            location = payload[0]
            link = payload[1]
            lane = payload[2]
            dist = self._dist(self.position(),location)
            logger.debug("Car # " + str(self.id) + " received RSA from Agent # " + str(sender_id) + " which is "+str(dist)+" meters away")
            # if link == self.link:
            #     logger.debug("Car # " + str(self.id) + " slowing down for RSA on link " + str(self.link) + " which is "+str(dist)+" meters away")
            #     self.set_desired_speed(self.dspeed-15)
            #     if lane == self.lane
            #         if lane >= 3 | lane < 2:
            #             des_lane = 2
            #         else:
            #             des_lane = 1 
            #         self.vissim.SetAttValue('DesLane',des_lane)


    def setComms(self,comm):
        logger.debug("Setting comms for car # "+str(self.id))
        self.comms = comm

    def setSkill(self,skill_id):
        logger.debug("Setting skill # "+str(skill_id)+" for car # "+str(self.id))
        flag = 0
        for skill in CAR_SKILLS:
            if skill.id == skill_id:
                self.comm_type = skill.comm_type
                self.comm_range = skill.comm_range
                flag = 1
                # dists = Vissim.Net.DistanceDistribution.GetAll()
                # for dist in dists:
                #     if int(dist.AttValue('No')) == skill.dist_distr
                #         self.comm_range = int(dist.AttValue('UpperBound'))
                #         flag = 2
                
        if flag == 0:
            logger.critical("When setting car # "+str(self.id)+" skills, given skill "+str(skill_id)+" does not exist")
            Vissim.Simulation.Stop()
        # elif flagg == 1:
        #     logger.critical("When setting car # "+str(self.id)+" skills, given distance distribution "+str(skill.dist_distr)+" does not exist in Vissim")
        #     Vissim.Simulation.Stop()

    def RSA(self):
        return [self.position(), self.link, self.lane]

    #######################################################
    """ Helper functions go here

    """
    def get_car_front(self,max_dist=300):
        front_car = []
        cars = self.get_car_radius(max_dist)


    """ Returns car id numbers within specified radius

    """
    def get_car_radius(self, radius=300, scope='all', method='brute', dist_distr=1):
        close_cars = []

        if scope == 'all':
            attributes = ('No','CoordFrontX','CoordFrontY')
            if method == 'vissim':
                try:
                    temp = Vissim.Net.Vehicles.GetByLocation(self.x[-1], self.y[-1], dist_distr) # limited by using predefined distance distribution
                    cars = temp.GetMultipleAttributes(attributes)
                except:
                    logger.error("Most likely distance distribution "+str(dist_distr)+" is not setup in Vissim yet. This must be configured before using method 'vissim'")
            elif method == 'brute':
                cars = Vissim.Net.Vehicles.GetMultipleAttributes(attributes)
            else:
                logger.error("method "+str(method)+" not valid. Options are 'vissim' and 'brute'")
                return close_cars
            
            for i in range(len(cars)):
                current_car = cars[i]
                coord_x = float(current_car[1])
                coord_y = float(current_car[2])
                dist = self._dist(self.position,[coord_x,coord_y])
                if dist <= radius:
                    close_cars.append(int(current_car[0]))

        elif scope == 'tracked':
            for car in Car.active_cars:
                dist = self._dist(self.position,car.position) 
                if dist <= radius:
                    close_cars.append(car.id)
        
        else:
            logger.error("scope '"+str(scope)+"' not valid. Options are 'all' and 'tracked'")
        return close_cars


    def _dist(self, loc1, loc2):
        if len(loc1) < 2 | len(loc1) > 3:
            logger.critical("Invalid location 1 for class Car method _dist()")
            Vissim.Simulation.Stop()
        elif len(loc1) == 2:
            loc1.append(0)

        if len(loc2) < 2 | len(loc2) > 3:
            logger.critical("Invalid location 2 for class Car method _dist()")
            Vissim.Simulation.Stop()
        if len(loc2) == 2:
            loc2.append(0)

        return (loc1[0] - loc2[0])**2 + (loc1[1] - loc2[1])**2 + (loc1[2] - loc2[2])**2 
    #######################################################
    """ Wrapper functions go here
    
    """
    def set_desired_speed(self, speed = 0):
        self.vissim.SetAttValue('DesSpeed',speed)

    def move_to_link(self, link_number, lane_number=0, link_coordinate=0):
        self.vissim.MoveToLinkPosition(link_number, lane_number, link_coordinate)