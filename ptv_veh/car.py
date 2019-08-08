import logging
from collections import namedtuple
import pandas as pd

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MIT"
__version__ = "0.0.1"


logger = logging.getLogger(__name__)

ATTRIBUTES = ['No','VehType','CoordFront', 'CoordRear','Lane\Link\No', 'Lane\Index', 'DestLane', 'Lane\Link\NumLanes','Length','DesSpeed','Speed', 'Acceleration','DistTravTot','LeadTargNo','LeadTargType','Hdwy','RoutDecNo', 'RouteNo','Occup']

Skill = namedtuple('Skill', 'id, comm_type, comm_range')
# Skill = namedtuple('Skill', 'id, comm_type, dist_distr')
# [skill_id(DEFINE),[comm_type(DEFINE), comm_range(DEFINE))]]
SKILLS = [
    Skill(0,'dsrc',700),
    Skill(10,'dsrc',500),
    Skill(20,'dsrc',1000),
    Skill(100,'bt',200),
    Skill(200,'cell',500),
    Skill(300,'web',100000) # 'infinite' range
]
# # [skil_id(DEFINE),[comm_type(DEFINE), comm_range_dist(Distance Distribution No)]]
# SKILLS = [
#     Skill(0,'dsrc',1),
#     Skill(10,'dsrc',2),
#     Skill(20,'dsrc',3),
#     Skill(100,'bt',50),
#     Skill(200,'cell',100),
#     Skill(300,'web',150)
# ]


""" Intended Use Documentation Here




"""

def setup(_Vissim, _custom_veh_type_list = [111], _CAR_SKILLS=-1):
    global Vissim # follows naming convention of standard Vissim COM interface
    global CUSTOM_VEH_TYPES
    global SKILLS

    if _CAR_SKILLS != -1:
        SKILLS = _CAR_SKILLS
        
    Vissim = _Vissim
    CUSTOM_VEH_TYPES = _custom_veh_type_list


def update(): # call at beginning of every loop
    Car.null_cars = []
    Car.new_cars = []
    Car.all_vissim_cars = []

    global TIME
    TIME = float(Vissim.Simulation.AttValue('SimSec'))
    all_vissim_cars = Vissim.Net.Vehicles.GetMultipleAttributes(ATTRIBUTES)
    
    # Convert to dictionary and parse any strings
    for car in all_vissim_cars:
        Car.all_vissim_cars.append({key:car[i] for i,key in enumerate(ATTRIBUTES)})
        Car.all_vissim_cars[-1]['CoordFront'] = _parse_coord(Car.all_vissim_cars[-1]['CoordFront'])
        Car.all_vissim_cars[-1]['CoordRear'] = _parse_coord(Car.all_vissim_cars[-1]['CoordRear'])

    # deactivate all out of scope vehicles
    for veh_type in CUSTOM_VEH_TYPES:
        new_car_nums = [int(veh['No']) for veh in Car.all_vissim_cars if int(veh['VehType'])==veh_type]
        old_car_nums = [car.id for car in Car.active_cars if car.type==veh_type]
        for num in old_car_nums:
            if num in new_car_nums:
                new_car_nums.remove(num)
            else:
                car = next((car for car in Car.active_cars if car.id==num), None)
                if car != None:
                    car.deactivate()
        for num in new_car_nums:
            Car(num)

    for car in Car.all_cars:
        car.update('master') # for speed it might be better to get all attributes at once and then sort that info to the correct object

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

    #Vissim does not sem to close the python interpreter after stopping the simulation.
    #Therefore we need to clear names/variables that might cause problems when starting a new simulation
    # Car.all_cars=Car.active_cars=Car.new_cars=Car.null_cars=[]
    # This also means you need to restart Vissim if you made changes to the python files/library


class Car:
    all_cars = []
    active_cars = []
    new_cars = []
    null_cars = []
    all_vissim_cars = []

    def __eq__(self, other):
        return self.id == other.id

    def __init__(self, car_num=0,comm=-1,msg_logic=-1,skill=0,veh_type=111,link=1,lane=1,desired_speed=0):
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
            self.id = int(car_num)
            self.vissim = Vissim.Net.Vehicles.ItemByKey(self.id) # For IVehicle Attributes
            self.type = int(self.vissim.AttValue('VehType'))

        self.vissim_type = Vissim.Net.VehicleTypes.ItemByKey(self.type) # For IVehicleType attributes
        self.capacity = int(self.vissim_type.AttValue('Capacity'))

        self.position = lambda: [self.x[-1],self.y[-1]] # current position
        self.active = 1 # is this object currently active in the simulation?

        Car.all_cars.append(self) # add to list of all cars
        Car.active_cars.append(self)
        Car.new_cars.append(self)

        # initialize all lists
        self.time = []
        self.x = []
        self.y = []
        
        self.update('master')
        self.setComms(comm)
        self.setSkill(skill)
        self.setMsgLogic(msg_logic)


    def update(self, update_type):
        if self.active:
            if update_type == 'master':
                # get data from VISSIM
                car = next((car for car in Car.all_vissim_cars if car['No']==self.id), None)
                if car != None:
                    self.dspeed = float(car['DesSpeed'])
                    self.link = int(car['Lane\Link\No'])
                    self.lane = int(car['Lane\Index'])
                    self.speed = float(car['Speed'])
                    self.time.append(TIME)
                    self.x.append(float(car['CoordFront'][0]))
                    self.y.append(float(car['CoordFront'][1]))
                    if car['Occup'] != None:
                        self.occupancy = int(car['Occup'])
                    else:
                        self.occupancy = -1
                    if car['LeadTargNo'] != None:
                        self.lead_object_num = int(car['LeadTargNo'])
                    else:
                        self.lead_object_num = -1
                    self.lead_object_type = car['LeadTargType']
                    return 1
                else:
                    logger.critical("Car # "+str(self.id)+" does not exist in network. Cannot update()")

            elif update_type == 'self':
                self.dspeed = float(self.vissim.AttValue('DesSpeed'))
                linklane = self.vissim.AttValue('Lane')
                self.link = int(linklane.split("-")[0])
                self.lane = int(linklane.split("-")[1])
                self.speed = float(self.vissim.AttValue('Speed'))
                self.time.append(float(Vissim.Simulation.AttValue('SimSec')))
                self.x.append(float(self.vissim.AttValue('CoordFrontX')))
                self.y.append(float(self.vissim.AttValue('CoordFrontY')))
                self.occupancy = int(self.vissim.AttValue('Occup'))
                self.lead_object_num = int(self.vissim.AttValue('LeadTargNo'))
                self.lead_object_type = self.vissim.AttValue('LeadTargType')
                return 1

            else:
                return 0

    def deactivate(self):
        self.active = 0
        Car.null_cars.append(self)
        # Car.active_cars.remove(self)
        if self in Car.active_cars:
            Car.active_cars.remove(self)
        else:
            logger.error("Trying to remove car "+str(self.id)+" from active_cars failed")
            active_ids = [car.id for car in Car.active_cars]
            logger.error("Active IDs are "+str(active_ids))

    #######################################################
    """ Communication functions go here

    """
    def sendMsg(self, recipient_id=-1, msg_type='loc', payload='null'):
        if self.comms == -1:
            logger.error("Comms was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if self.m == -1:
            logger.error("Message logic was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if msg_type not in self.m.msg_types:
            logger.error("Message type" + str(msg_type )+ "is not a valid type for car with ID "+str(self.id)+", cannot sendMsg()")
            return 0

        result = self.m.send(self, recipient_id, msg_type, payload)

        recipient_id = result['recipient_id']
        msg_type = result['msg_type']
        payload = result['payload']

        logger.debug("Car # " + str(self.id) + " sending payload "+str(payload) +" to " + str(recipient_id))
        # default message is broadcast to everyone listening (-1)
        self.comms.broadcast(self.position(), self.comm_range, msg_type, payload, recipient_id, self.id)
        return 1


    def receiveMsg(self, sender_id, msg_type, payload):
        if self.comms == -1:
            logger.error("Comms was not set up for car with ID "+str(self.id)+" cannot receiveMsg()")
            return 0
        if self.m == -1:
            logger.error("Message logic was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if msg_type not in self.m.msg_types:
            logger.error("Message type" + str(msg_type )+ "is not a valid type for car with ID "+str(self.id)+", cannot receiveMsg()")
            return 0

        self.m.receive(self, sender_id, msg_type, payload)
        return 1


    def setComms(self,comm):
        logger.debug("Setting comms for car # "+str(self.id))
        self.comms = comm

    def setSkill(self,skill_id):
        logger.debug("Setting skill # "+str(skill_id)+" for car # "+str(self.id))
        flag = 0
        for skill in SKILLS:
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
        return 1

    def setMsgLogic(self,message_logic_module):
        logger.debug("Setting message logic for car # "+str(self.id))
        self.m = message_logic_module


    #######################################################
    """ Helper functions go here

    """
    def get_car_front(self,max_dist=300):
        front_car = []
        cars = self.get_car_radius(max_dist)

        # Possibly compare Hdwy or FollowDist to get_car_radius to match correct car
        #InteractTargNo,InteractTargType

    """ Returns car id numbers within specified radius

    """
    def get_car_radius(self, radius=300, scope='all', method='brute', dist_distr=1):
        close_cars = []

        if scope == 'all':
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

    # def send_to_parking_lot(self)


def _parse_coord(coord_string):
    # Adapted from Vissim Platooning example
    # converts a Coordinates string with seperated values from PTV Vissim to a list of float
    # Example: from input string '-514.485 -294.097 0.000' to output list of floats: [-514.485, -294.097, 0.000]
    if not coord_string:
        listCoordinates = [] # if the string is empty '' or None, an empty list is returned
    else:
        listCoordinates = map(float, coord_string.split(' ')) # from '-514.485 -294.097 0.000' split first to ['-514.485', '-294.097', '0.000'] and than to integer: [-514.485, -294.097, 0.000]
    return listCoordinates