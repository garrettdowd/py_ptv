

def Car_setup(_Vissim, _custom_veh_type = 111, _car_skills=-1):
    global Vissim
    global car_skills
    global custom_veh_type


    Vissim = _Vissim
    custom_veh_type = _custom_veh_type
    if _car_skills == -1:
        # [Skill#,[comm_type(DEFINE), comm_range(m)]]
        car_skills = [
            [10, [1, 800]],
            [100, [1, 900]]
        ]
    else:
        car_skills = _car_skills


class Car:
    # define what happens when an uav object is instatiated
    def __init__(self, car_num=0,skill=0,veh_type=10,link=1,lane=1,desired_speed=0,comm=-1):

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
            # copy skills to local variables
            flag = 0
            for item in car_skills:
                if item[0] == skill:
                    self.comm_type = car_skills[item][1][0]
                    self.comm_range = car_skills[item][1][1]
                    flag = 1
            if flag == 0:
                print("When instantiating a car object, given skill "+skill+" does not exist")
                Vissim.Simulation.Stop()
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
        self.position = [self.x[-1],self.y[-1]] # current position
        self.active = 1 # is this object currently active in the simulation?

        self.comms = comm


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

    # def requestuav

    def sendMsg(self, recipient_id=-1, msg_type=0, payload=-1):
        if self.comms == -1:
            print("Comms was not set up for car with ID "+self.id+" cannot sendMsg()")
            return
        if payload == -1:
            payload = self.position
        # default message is broadcast to everyone listening (-1)
        self.comms.broadcast(recipient_id,msg_type,payload)

    # def receiveMsg



