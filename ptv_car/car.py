import logging
from collections import namedtuple

Skill = namedtuple('Skill', 'id, comm_type, comm_range')

def setup(_Vissim, _custom_veh_type = 111, _car_skills=-1):
    global Vissim
    global car_skills
    global custom_veh_type

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    if _car_skills == -1:
        # [Skill#,[comm_type(DEFINE), comm_range(m)]]
        car_skills = [
            Skill(10,'dsrc',300),
            Skill(20,'dsrc',900)
        ]
    else:
        car_skills = _car_skills

    #################################################################################
    #################################################################################
    Vissim = _Vissim
    custom_veh_type = _custom_veh_type


class Car:
    # define what happens when an uav object is instatiated
    def __init__(self, car_num=0,comm=-1,skill=0,veh_type=10,link=1,lane=1,desired_speed=0):

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

        # initialize time and position
        self.time = [float(Vissim.Simulation.AttValue('SimSec'))]
        self.x = [float(self.vissim.AttValue('CoordFrontX'))]
        self.y = [float(self.vissim.AttValue('CoordFrontY'))]
        self.position = lambda: [self.x[-1],self.y[-1]] # current position
        self.active = 1 # is this object currently active in the simulation?

        self.comms = comm
        # copy skills to local variables
        self.comm_type = 0
        self.comm_range = 0
        flag = 0
        for item in car_skills:
            if item.id == skill:
                self.comm_type = item.comm_type
                self.comm_range = item.comm_range
                flag = 1
        if flag == 0:
            logging.debug("When instantiating a car object, given skill "+str(skill)+" does not exist")
            Vissim.Simulation.Stop()


    def update(self):
        # get data from VISSIM
        self.dspeed = float(self.vissim.AttValue('DesSpeed'))
        linklane = self.vissim.AttValue('Lane')
        self.link = int(linklane.split("-")[0])
        self.lane = int(linklane.split("-")[1])
        self.speed = float(self.vissim.AttValue('Speed'))
        self.time.append(float(Vissim.Simulation.AttValue('SimSec')))
        self.x.append(float(self.vissim.AttValue('CoordFrontX')))
        self.y.append(float(self.vissim.AttValue('CoordFrontY')))

    def deactivate(self):
        self.active = 0


    def sendMsg(self, recipient_id=-1, msg_type=0, payload='null'):
        if self.comms == -1:
            logging.debug("Comms was not set up for car with ID "+str(self.id)+" cannot sendMsg()")
            return
        if (int(msg_type) == 0) & (payload == 'null'):
            payload = self.position()
            logging.debug("Car # "+str(self.id)+" sending position "+str(self.position()))
        # default message is broadcast to everyone listening (-1)
        self.comms.broadcast(self.position(), self.comm_range, msg_type, payload, recipient_id, self.id)
        return

    # all of the logic for handling messages happens here
    def receiveMsg(self, sender_id, msg_type, payload):
        if msg_type == 0: # location
            logging.debug("Car # " + str(self.id) + " received a message from " + str(sender_id) )
        return

    # def get_car_front(self):


    # def get_car_radius(self, radius):


    # set destination, des speed, 