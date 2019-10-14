import os
import datetime as dt
import logging
from collections import namedtuple
import pandas as pd

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MPL-2.0"
__version__ = "0.0.2"


logger = logging.getLogger(__name__)

class Skill(namedtuple('Skill', 'id, comm_type, comm_range')):
    def __eq__(self, other):
        return self.id == other.id

######################
# DEFAULTS
######################
# REQUIRED ATTRIBUTES
# ['CoordFront','Lane\Link\No','Lane\Index','RouteNo','RoutDecNo','DesSpeed','Speed','Hdwy','Occup','DistTravTot','LeadTargNo','LeadTargType']
ATTRIBUTES = ['No','VehType','CoordFront', 'CoordRear','Lane\Link\No', 'Lane\Index', 'DestLane', 'Lane\Link\NumLanes','Length','DesSpeed','Speed', 'Acceleration','DistTravTot','LeadTargNo','LeadTargType','Hdwy','RoutDecNo', 'RouteNo','Occup']

SKILLS = [
    Skill(0,'dsrc',500),
    Skill(10,'dsrc',700),
    Skill(20,'dsrc',1000),
    Skill(100,'bt',100),
    Skill(200,'cell',500),
    Skill(300,'web',100000) # 'infinite' range
]
CAR_DEFAULT = {
    'comms': None,
    'msg_handler': None,
    'skill': 0,
    'veh_type': 111,
    'link': 1,
    'lane': 1,
    'desired_speed': 0
}
######################
# DEFAULTS
######################
""" Intended Use Documentation Here




"""

def setup(_Vissim, _RESULTS_DIR, _tracked_veh_type_list, car_default=None, vissim_attributes=None, car_skills=None):
    global Vissim # follows naming convention of standard Vissim COM interface
    global RESULTS_DIR
    global TRACKED_VEH_TYPES
    global CAR_DEFAULT
    global ATTRIBUTES
    global SKILLS
    global TIME

    Vissim = _Vissim
    TRACKED_VEH_TYPES = _tracked_veh_type_list
    RESULTS_DIR = _RESULTS_DIR

    if vissim_attributes != None:
        ATTRIBUTES = vissim_attributes

    if car_skills != None:
        for new_skill in car_skills:
            if new_skill in SKILLS:
                idx = SKILLS.index(new_skill)
                SKILLS[idx] = new_skill
            else:
                SKILLS.append(new_skill)

    if car_default != None:
        for default in car_default:
            CAR_DEFAULT[default] = car_default[default]

    TIME = float(Vissim.Simulation.AttValue('SimSec'))


def update(): # call at beginning of every loop
    Car.null_cars = []
    Car.new_cars = []
    Car.all_vissim_cars = []

    global TIME
    TIME = float(Vissim.Simulation.AttValue('SimSec'))
    all_vissim_cars = Vissim.Net.Vehicles.GetMultipleAttributes(ATTRIBUTES)
    
    # Convert to dictionary and parse any strings (make this robust to changes in attributes)
    for car in all_vissim_cars:
        Car.all_vissim_cars.append({key:car[i] for i,key in enumerate(ATTRIBUTES)})
        if 'CoordFront' in ATTRIBUTES:
            Car.all_vissim_cars[-1]['CoordFront'] = _parse_coord(Car.all_vissim_cars[-1]['CoordFront'])
        if 'CoordRear' in ATTRIBUTES:
            Car.all_vissim_cars[-1]['CoordRear'] = _parse_coord(Car.all_vissim_cars[-1]['CoordRear'])

    # deactivate all out of scope vehicles
    for veh_type in TRACKED_VEH_TYPES:
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
            Car(num) # create new instance with default parameters for all new vehicles

    for car in Car.all_cars:
        car.update('master')

def getCars():
    cars = dict()
    cars['all'] = Car.all_cars
    cars['active'] = Car.active_cars
    cars['new'] = Car.new_cars
    cars['null'] = Car.null_cars
    return cars

def saveResults(filepath=None):
    if filepath == None:
        filepath = RESULTS_DIR
    # make sure that the necessary folder structure exists
    file_dir = os.path.dirname(filepath)
    if not os.path.exists(file_dir):
        logger.info("Creating directory "+file_dir)
        os.makedirs(file_dir)

    logger.info("Saving Car Results to "+filepath)
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

    #Vissim does not seem to close the python interpreter after stopping the simulation.
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
        if other:
            return self.id == other.id
        else:
            return False

    def __init__(self, car_num=None, parameters=None):
        car_default = CAR_DEFAULT
        if parameters != None:
            for param in parameters:
                car_default[param] = parameters[default]

        logger.info("Creating a Car object with # "+str(car_num))
        if car_num == None:
            # Putting a new vehicle in the network:
            self.type = car_default['veh_type']
            self.dspeed = car_default['desired_speed'] # unit according to the user setting in Vissim [km/h or mph]
            self.link = car_default['link']
            self.lane = car_default['lane']
            start_pos = 0 # unit according to the user setting in Vissim [m or ft]
            interaction = True # optional boolean, should vehicle interact with other vehicles and such?
            self.vissim = Vissim.Net.Vehicles.AddVehicleAtLinkPosition(self.type, self.link, self.lane, start_pos, self.dspeed, interaction)
            self.id = int(self.vissim.AttValue('No')) # get vehicle number from vissim
        else: # if car_num != 0
            # Get existing info from vehicle already defined in the network
            self.id = int(car_num)
            self.vissim = Vissim.Net.Vehicles.ItemByKey(self.id) # For IVehicle Attributes
            self.type = int(self.vissim.AttValue('VehType'))

        self.vissim_type = Vissim.Net.VehicleTypes.ItemByKey(self.type) # For IVehicleType attributes
        self.capacity = int(self.vissim_type.AttValue('Capacity'))

        self.active = 1 # is this object currently active in the simulation?

        Car.all_cars.append(self) # add to list of all cars
        Car.active_cars.append(self)
        Car.new_cars.append(self)

        # initialize all lists
        self.time = []
        self.x = []
        self.y = []
        
        self.update('master') # get data from Vissim
        self.setComms(car_default['comms'])
        self.setSkill(car_default['skill'])
        self.setMsgHandler(car_default['msg_handler'])


    def update(self, update_type):
        if self.active:
            if update_type == 'master':
                # get data from VISSIM
                car = next((car for car in Car.all_vissim_cars if car['No']==self.id), None)
                if car != None:
                    self.attributes = car
                    self.time.append(TIME)
                    self.x.append(_none_check(car['CoordFront'][0],'float'))
                    self.y.append(_none_check(car['CoordFront'][1],'float'))
                    self.link = _none_check(car['Lane\Link\No'],'int')
                    self.lane = _none_check(car['Lane\Index'],'int')
                    self.route_num = _none_check(car['RouteNo'],'int')
                    self.route_decision_num = _none_check(car['RoutDecNo'],'int')
                    self.dspeed = _none_check(car['DesSpeed'],'float')
                    self.speed = _none_check(car['Speed'],'float')
                    self.headway = _none_check(car['Hdwy'],'float')
                    self.occupancy = _none_check(car['Occup'],'int')
                    self.total_distance = _none_check(car['DistTravTot'],'float')
                    self.lead_object_num = _none_check(car['LeadTargNo'],'int')
                    self.lead_object_type = car['LeadTargType'] # NONE, VEHICLE, SIGNALHEAD, CONFLICTAREA, STOPSIGN, REDUCEDSPEEDAREA
                    return 1
                else:
                    logger.critical("Car # "+str(self.id)+" does not exist in network. Cannot update()")
            # included for speed comparison, this is how library was orignally written
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
                self.lead_object_type = self.vissim.AttValue('LeadTargType') # NONE, VEHICLE, SIGNALHEAD, CONFLICTAREA, STOPSIGN, REDUCEDSPEEDAREA
                return 1

            else:
                return 0

    def position(self):
        pos = [self.x[-1],self.y[-1]] # current position
        return pos 

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
        if self.comms == None:
            logger.error("Comms was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if self.m == None:
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
        if self.comms == None:
            logger.error("Comms was not set up for car with ID "+str(self.id)+" cannot receiveMsg()")
            return 0
        if self.m == None:
            logger.error("Message logic was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if msg_type not in self.m.msg_types:
            logger.error("Message type" + str(msg_type )+ "is not a valid type for car with ID "+str(self.id)+", cannot receiveMsg()")
            return 0

        self.m.receive(self, sender_id, msg_type, payload)
        return 1


    def setComms(self,comms):
        logger.info("Setting comms for car # "+str(self.id))
        self.comms = comms

    def setSkill(self,skill_id):
        logger.info("Setting skill # "+str(skill_id)+" for car # "+str(self.id))
        # copy skills to local variables
        skill = next((skill for skill in SKILLS if skill.id == skill_id),None)
        if skill:
            self.comm_type = skill.comm_type
            self.comm_range = skill.comm_range
            return 1
        else:
            logger.critical("When instantiating a Car object, given skill #"+str(skill_id)+" does not exist")
            Vissim.Simulation.Stop()
            return 0

    def setMsgHandler(self,message_handler):
        logger.info("Setting message handler for car # "+str(self.id))
        self.m = message_handler


    #######################################################
    """ Helper functions go here

    """

    """ Sends car to parking lot with given ID (dynamic assignment)

    """
    def go_park(self, parking_lot_id):
        # Assign a new destination in terms of a parking lot to a vehicle.
        # Inputs:
        #   vehicleID:        Integer value of a vehicle ID,  example: 53
        #   destParkingLot:   Integer value of a parking lot, example: 5
        # Output:
        #   newPath as IPath PTV Vissim object.

        # check if a vehicle parks => vehicle has no NextNode
        if self.attributes['InteractTargType'] == 'PARKINGLOT' and self.attributes['InteractState'] == 'DWELL':
            current_parking_lot = self.attributes['InteractTargNo']
            if current_parking_lot == parking_lot_id:
                logger.error('Vehicle #' + str(vehicleID) + ' is send to destination parking lot #' + str(destParkingLot) + ' but is already there => no new path assigned to the vehicle.')
                return None
            start_node = NextNodeFromParkingLot(current_parking_lot)
        else:
            # check if a vehicle is inside of a node:
            if self.attributes['PrevNode\No'] != None and self.attributes['PrevNode\No'] == self.attributes['NextNode\No']:
                # calculates the Node sequence of a path using the Edge information
                # only returns the Node, not the Turns
                currentPathAttributes = [x for x in pathAttributes if x[pathAttNames['No']] == self.attributes['Path\No']][0]
                currentPathAttributes = zip(currentPathAttributes[pathAttNames['Concatenate:EdgeSeq\FromNode']],currentPathAttributes[pathAttNames['Concatenate:EdgeSeq\ToNode']],currentPathAttributes[pathAttNames['Concatenate:EdgeSeq\IsTurn']]) # only the relevant information
                nodesNoTurns = [x for x in currentPathAttributes if x[2] == 0] # delete Nodes from Turns
                nodeSequence = map(lambda x: x[0], nodesNoTurns) + [nodesNoTurns[-1][1]] # all FromNodes + last ToNode

                indexOfCurrentNode = nodeSequence.index(self.attributes['NextNode\No'])
                if len(nodeSequence) > indexOfCurrentNode:
                    start_node = nodeSequence[indexOfCurrentNode + 1]
                else:
                    print 'No next Node downstream for Path #' + str(pathNo) + ' because Node #' + str(currentNode) + ' is the last Node of the Path. Next Node will be None.'
                    start_node = None
            else:
                # check if vehicle has no status (because it was just added):
                if self.attributes['PrevNode\No'] == None and self.attributes['Path\No'] == None:
                    start_node = self.attributes['OrigParkLot\No'] # in this example the origin parking lot equals the current node, because the parking lots are modelled inside the node!
                else:
                    # get the next Node as vehicle attribute:
                    start_node = self.attributes['NextNode\No']

        next_node_sequence = CalculateShortestRouteToDestination(start_node, parking_lot_id) # Simple shortest Path algorithm based on distance (not taking into account distances of turns!):

        # Add current node to node sequence, if vehicle is inside of a node:
        if self.attributes['PrevNode\No'] != None and self.attributes['PrevNode\No'] == self.attributes['NextNode\No']:
            next_node_sequence = [self.attributes['NextNode\No']] + next_node_sequence

        logger.info('Path for vehicle #' + str(vehicleID) + ': ToParkLot #' + str(parking_lot_id) + ' Node sequence: ' + str(next_node_sequence))
        new_path = Vissim.Net.Paths.AddPathForVehicle(self.id, parking_lot_id, next_node_sequence)
        # Assign Path to Vehicle
        self.vissim.AssignPath(new_path)

        return new_path

    """ Returns car id number of front vehicle (if it exists)

    """    
    def get_car_front(self,max_dist=300):
        front_car = None
        if self.lead_object_type == 'VEHICLE':
            car = next((car for car in Car.all_vissim_cars if car['No']==self.lead_object_num), None)
            if car != None:
                front_car = car['No']
            else:
                logger.error("Couldn't get front vehicle")

    """ Returns car id numbers within specified radius

    """
    def get_car_radius(self, radius=300, scope='all', method='brute', dist_distr=1):
        close_cars = []

        if scope == 'all':
            if method == 'brute':
                pass
            else:
                logger.error("method "+str(method)+" not valid. Options are 'brute' and")
                return close_cars
            
            for car in Car.all_vissim_cars:
                dist = self._dist(self.position(),car['CoordFront'])
                if dist <= radius:
                    close_cars.append(car['No'])

        elif scope == 'tracked':
            for car in Car.active_cars:
                dist = self._dist(self.position(),car.position()) 
                if dist <= radius:
                    close_cars.append(car.id)
        
        else:
            logger.error("scope '"+str(scope)+"' not valid. Options are 'all' and 'tracked'")
        return close_cars


    def _dist(self, loc1, loc2):
        # Calculate Euclidian Distance
        if len(loc1) < 2 | len(loc1) > 3:
            logger.critical("Invalid location 1")
            Vissim.Simulation.Stop()
        elif len(loc1) == 2:
            loc1.append(0)

        if len(loc2) < 2 | len(loc2) > 3:
            logger.critical("Invalid location 2")
            Vissim.Simulation.Stop()
        if len(loc2) == 2:
            loc2.append(0)

        dist = ( (loc1[0] - loc2[0])**2 + (loc1[1] - loc2[1])**2 + (loc1[2] - loc2[2])**2 )**0.5
        return dist


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

def _none_check(vissim_attribute, attrib_type):
    # Vissim COM returns values as strings and if the value does not exist it will return a NoneType.
    # This functions makes it easier to both convert to the correct type while safeguarding against converting NoneType
    if vissim_attribute != None:
        if attrib_type == 'int':
            return int(vissim_attribute)
        elif attrib_type == 'float':
            return float(vissim_attribute)
    else:
        return None