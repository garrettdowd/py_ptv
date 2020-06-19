import os
import math
import datetime as dt
import logging
from collections import namedtuple
import pandas as pd
import numpy as np

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MPL-2.0"
__version__ = "0.0.2"

logger = logging.getLogger(__name__)

class Skill(namedtuple('Skill', 'id, min_speed, max_speed, max_acc, max_ascent, max_descent, comm_range')):
    """One liner.

    """
    def __eq__(self, other):
        return self.id == other.id

"""One liner.

"""
SKILLS = [
    Skill(0, 0, 35, 3.5, 5, 2, 1000),
    Skill(10, 0, 19.9, 4, 5, 3, 800),
    Skill(20, 0, 45, 4, 5, 3, 800),
    Skill(100, 15.2, 39, 4, 5, 3, 900)
]

"""One liner.

"""
UAV_DEFAULT = {
    'comms': None,
    'msg_handler': None,
    'model_flag': True,
    'camera_flag': False,
    'skill': 0,
    'position': [0,0,0],
    'sim_type': "ZO",
    'sim_mult': 2,
}

"""One liner.

"""
CAMERA_DEFAULT = {
    'FOV': 20,
    'PitchAngle': 90,
    'RollAngle': 0,
    'YawAngle': 0,
    'RecAVI': "true",
    'ShowPrev': "true",
    'ResX': 720,
    'ResY': 480,
    'Framerate': 20,
    'Pos': [0,0,-100],
}


def setup(_Vissim, _RESULTS_DIR, uav_skills=None, uav_default=None, camera_default=None):
    """One liner.

    """
    global Vissim
    global RESULTS_DIR
    global SKILLS
    global UAV_DEFAULT
    global CAMERA_DEFAULT
    global TIME

    Vissim = _Vissim
    RESULTS_DIR = _RESULTS_DIR

    if uav_skills != None:
        for new_skill in uav_skills:
            if new_skill in SKILLS:
                idx = SKILLS.index(new_skill)
                SKILLS[idx] = new_skill
            else:
                SKILLS.append(new_skill)

    if uav_default != None:
        for default in uav_default:
            UAV_DEFAULT[default] = uav_default[default]

    if camera_default != None:
        for param in camera_default:
            CAMERA_DEFAULT[param] = camera_default[param]

    TIME = float(Vissim.Simulation.AttValue('SimSec'))
    

def update(model_update_rate=1, camera_update_rate=1): # call at beginning of every loop
    global TIME
    TIME = float(Vissim.Simulation.AttValue('SimSec'))

    for uav in UAV.active_uavs:
        uav.update()

    for model in Model.active_models:
        model.update(model_update_rate)

    for camera in Camera.active_cameras:
        camera.update(camera_update_rate)

def getUAVs():
    uavs = dict()
    uavs['all'] = UAV.all_uavs
    uavs['active'] = UAV.active_uavs
    return uavs

def saveResults(filepath=None):
    # make sure that the necessary folder structure exists
    if filepath == None:
        filepath = RESULTS_DIR
    # make sure that the necessary folder structure exists
    file_dir = os.path.dirname(filepath)
    if not os.path.exists(file_dir):
        logger.debug("Creating directory "+file_dir)
        os.makedirs(file_dir)

    logger.info("Saving UAV Results to "+filepath)
    column_uav = ['uavID', 'time', 'x', 'y', 'z']

    df = []
    for uav in UAV.all_uavs:
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
    df = df.reindex(columns=column_uav)  # ensure columns are in correct order
    # df = df.iloc[::-1] # reverse order of rows
    df.to_csv(filepath, encoding='utf-8', index=False)

    #Vissim does not sem to close the python interpreter after stopping the simulation.
    #Therefore we need to clear names/variables that might cause problems when starting a new simulation
    # Car.all_cars=Car.active_cars=Car.new_cars=Car.null_cars=[]
    # This also means you need to restart Vissim if you made changes to the python files/library

class UAV:
    all_uavs = []
    active_uavs = []

    def __eq__(self, other):
        if other:
            return self.id == other.id
        else:
            return False

    # define what happens when an uav object is instatiated
    def __init__(self, parameters=None):
        uav_default = UAV_DEFAULT
        if parameters != None:
            for param in parameters:
                uav_default[param] = parameters[param]

        # define a unique id
        if not self.all_uavs:
            self.id = 0
        else:
            max_id = max([uav.id for uav in self.all_uavs])
            self.id = max_id + 1
        if len(uav_default['position']) != 3:
            logger.critical("UAV instantiation, invalid position: "+ str(uav_default['position']))
            Vissim.Simulation.Stop()
        self.time = [TIME]
        self.x = [uav_default['position'][0]]
        self.y = [uav_default['position'][1]]
        self.z = [uav_default['position'][2]]
        self.heading = 0 # [pitch(-90,90), roll(0,360), yaw(0,360)]
        

        self.dest = [[self.x[-1],self.y[-1],self.z[-1]]] # destination. where uav should be flying to
        self.car = None
        self.default_altitude = 50
        self.mission = 0 # defines what the uav should be doing e.g. car following = 1, stationary point = 0.

        self.active = True # is this object currently active in the simulation?

        self.model3D = None
        self.camera = None
        if uav_default['camera_flag']:
            self._addCamera()
        if uav_default['model_flag']:
            self._add3D()

        self.setComms(uav_default['comms']) # Comm object
        self.setMsgHandler(uav_default['msg_handler'])
        self.setSkill(uav_default['skill'])

        UAV.all_uavs.append(self)
        UAV.active_uavs.append(self)
        ##########################################################
        self.sim = dict()
        self.sim['type'] = uav_default['sim_type']
        self.sim['mult'] = uav_default['sim_mult']

    def update(self):
        if self.mission == 'car_follow':
            if self.car.active != 0:
                xy = self.car.position()
                self.setDest(xy)
                logger.debug('UAV with ID# '+str(self.id)+' following car. Current car location is ' + str(xy))
            else:
                self.setCar(None)
                self.deactivate()

        self._simXYZ()

    def position(self):
        pos = [self.x[-1],self.y[-1],self.z[-1]] # current position
        return pos

    def deactivate(self):
        self.active = False
        if self in UAV.active_uavs:
            UAV.active_uavs.remove(self)
        else:
            logger.error("Trying to remove UAV "+str(self.id)+" from active_uavs failed")
            active_ids = [uav.id for uav in UAV.active_uavs]
            logger.error("Active IDs are "+str(active_ids))
        self._remove3D()
        self._removeCamera()

    def setDest(self, xyz):
        if xyz == None:
            logger.error('Invalid Input - Input is None type')
        elif len(xyz) == 2:
            xyz.append(self.default_altitude)
        elif len(xyz) == 3:
            pass
        else:
            logger.critical("Invalid input to setDest- " + str(xyz))
            Vissim.Simulation.Stop()
        
        if self.dest[-1] != xyz:
            self.dest.append(xyz)


    def setCar(self, car, default_altitude=40):
        if self.car != car:
            self.car = car
            if self.car == None:
                logger.info('Cancelling car following for UAV with ID# '+str(self.id))
                self.mission == 'hold'
            else:
                logger.info('Setting UAV with ID# '+str(self.id)+' to follow car with ID# ' + str(car.id))
                self.mission = 'car_follow' # actively track vehicle, possibly fly ahead to scout
                self.default_altitude = default_altitude



    #######################################################
    """ Communication functions go here

    """

    def sendMsg(self, recipient_id=-1, msg_type='loc', payload='null'):
        if self.comms == None:
            logger.error("Comms was not set up for UAV with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if self.m == None:
            logger.error("Message logic was not set up for UAV with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if msg_type not in self.m.msg_types:
            logger.error("Message type" + str(msg_type )+ "is not a valid type for UAV with ID "+str(self.id)+", cannot sendMsg()")
            return 0

        result = self.m.send(self, recipient_id, msg_type, payload)

        recipient_id = result['recipient_id']
        msg_type = result['msg_type']
        payload = result['payload']

        logger.debug("UAV # " + str(self.id) + " sending payload "+str(payload) +" to " + str(recipient_id))
        # default message is broadcast to everyone listening (-1)
        self.comms.broadcast(self.position(), self.comm_range, msg_type, payload, recipient_id, self.id)
        return 1


    def receiveMsg(self, sender_id, msg_type, payload):
        if not self.comms:
            logger.error("Comms was not set up for UAV with ID "+str(self.id)+" cannot receiveMsg()")
            return 0
        if not self.m:
            logger.error("Message logic was not set up for UAV with ID "+str(self.id)+" cannot sendMsg()")
            return 0
        if msg_type not in self.m.msg_types:
            logger.error("Message type" + str(msg_type )+ "is not a valid type for UAV with ID "+str(self.id)+", cannot receiveMsg()")
            return 0

        self.m.receive(self, sender_id, msg_type, payload)
        return 1

    def setComms(self,comm):
        logger.info("Setting comms for UAV # "+str(self.id))
        self.comms = comm

    def setSkill(self,skill_id):
        logger.info("Setting skill # "+str(skill_id)+" for UAV # "+str(self.id))
        # copy skills to local variables
        skill = next((skill for skill in SKILLS if skill.id == skill_id),None)
        if skill:
            self.min_speed = skill.min_speed
            self.max_speed = skill.max_speed
            self.max_acc = skill.max_acc
            self.max_ascent = skill.max_ascent
            self.max_descent = skill.max_descent
            self.comm_range = skill.comm_range
            return 1
        else:
            logger.critical("When instantiating a uav object, given skill #"+str(skill_id)+" does not exist")
            Vissim.Simulation.Stop()
            return 0

    def setMsgHandler(self,message_handler):
        logger.debug("Setting message handler for UAV # "+str(self.id))
        self.m = message_handler
    ##############################################################################
    #############################################################################

    def _simXYZ(self, sim_type=None, sim_mult=None):
        if not sim_type:
            sim_type = self.sim['type']

        if not sim_mult:
            sim_mult = self.sim['mult']

        dt = (TIME - self.time[-1])
        time_steps = int(sim_mult)
        sim_freq = sim_mult/dt

        if len(self.x)<2:
            self.sim['time'] = [0]
            self.sim['x'] = self.x
            self.sim['xd'] = [0]
            self.sim['y'] = self.y
            self.sim['yd'] = [0]
            self.sim['z'] = self.z
            self.sim['zd'] = [0]
            self.sim['xyzd'] = [0]
            self.sim['xyzdd'] = [0]

            self.sim['err_mag'] = []
            self.sim['err_dir'] = []

        for i in range(time_steps):
            # self.sim['time'].append(self.sim['time'][-1] + 1/sim_freq)
            err_x = self.dest[-1][0] - self.sim['x'][-1]
            err_y = self.dest[-1][1] - self.sim['y'][-1]
            err_z = self.dest[-1][2] - self.sim['z'][-1]
            error_magnitude = (err_x**2 + err_y**2 + err_z**2)**0.5
            if error_magnitude != 0:
                error_direction = [err_x/error_magnitude, err_y/error_magnitude, err_z/error_magnitude]
            else:
                error_direction = [0,0,0]
            self.sim['err_mag'] = [error_magnitude]
            self.sim['err_dir'] = [error_direction]
            pitch = 90 * error_direction[2]
            roll = 0
            if error_direction[0] == 0:
                yaw = 0
            elif error_direction[1] == 0:
                yaw = 90
            else:
                yaw = np.degrees(np.arctan(error_direction[1]/error_direction[0]))
                if yaw < 0:
                    yaw += 360
            
            self.heading = [pitch, roll, yaw]
            # self.sim['err_mag'].append(error_magnitude)
            # self.sim['err_dir'].append(error_direction)
            # if len(self.x)<3:
            #     if len(self.x)==2:
            #         accx = speedx/dt
            #         accy = speedy/dt
            #         accz = speedz/dt
            #     else:
            #         accx = 0
            #         accy = 0
            #         accz = 0
            # else:
            #     accx = (self.x[-1] - 2*self.x[-2]-self.x[-3])/dt^2
            #     accy = (self.y[-1] - 2*self.y[-2]-self.y[-3])/dt^2
            #     accz = (self.z[-1] - 2*self.z[-2]-self.z[-3])/dt^2

            # ### calculate velocity error term for control
            # vel_errx = (self.dest[-1][0] - self.dest[-2][0])/dt - speedx
            # vel_erry = (self.dest[-1][1] - self.dest[-2][1])/dt - speedy
            # vel_errz = (self.dest[-1][2] - self.dest[-2][2])/dt - speedz

            if sim_type == "ZO":
                # zero order model with velocity/acceleration saturation. uav will fly in direction defined by the distance error vector

                # saturation
                desired_acc = self.sim['err_mag'][-1]*(sim_freq**2)
                if desired_acc > self.max_acc:
                    desired_acc = self.max_acc
                # self.sim['xyzdd'].append(desired_acc)
                desired_vel = desired_acc*sim_freq + self.sim['xyzd'][-1]
                if desired_vel > self.max_speed:
                    desired_vel = self.max_speed
                self.sim['xyzd'][-1] = desired_vel
                # self.sim['xyzd'].append(desired_vel)

                # calc new position
                self.sim['xd'] = [desired_vel * error_direction[0]]
                self.sim['x'] = [self.sim['xd'][-1] * 1/sim_freq + self.sim['x'][-1]]
                self.sim['yd'] = [desired_vel * error_direction[1]]
                self.sim['y'] = [self.sim['yd'][-1] * 1/sim_freq + self.sim['y'][-1]]
                self.sim['zd'] = [desired_vel * error_direction[2]]
                self.sim['z'] = [self.sim['zd'][-1] * 1/sim_freq + self.sim['z'][-1]]
                # self.sim['xd'].append(desired_vel * error_direction[0])
                # self.sim['x'].append(self.sim['xd'][-1] * 1/sim_freq + self.sim['x'][-1])
                # self.sim['yd'].append(desired_vel * error_direction[1])
                # self.sim['y'].append(self.sim['yd'][-1] * 1/sim_freq + self.sim['y'][-1])
                # self.sim['zd'].append(desired_vel * error_direction[2])
                # self.sim['z'].append(self.sim['zd'][-1] * 1/sim_freq + self.sim['z'][-1])


            elif sim_type == "FO":
                ## Use simple position based first order model with proportional control for uav. No saturation on velocity or acceleration
                K=1.5
                tau = 2
                
                newPosX = K*(1-math.exp(-dt/tau))*self._dist_errx[-1] + self.x[-1]
                newPosY = K*(1-math.exp(-dt/tau))*self._dist_erry[-1] + self.y[-1]
                newPosZ = K*(1-math.exp(-dt/tau))*self._dist_errz[-1] + self.z[-1]



            elif sim_type == "PID":
                ## calculate PID controller output (saturation causes integration to turn off to prevent windup)
                integ_len = 300
                if self.sat_flagx == 1:
                    desired_vel_x = self._PID(self._dist_errx,1,dt)
                else:
                    desired_vel_x = self._PID(self._dist_errx,integ_len,dt)

                if self.sat_flagy == 1:
                    desired_vel_y = self._PID(self._dist_erry,1,dt)
                else:
                    desired_vel_y = self._PID(self._dist_erry,integ_len,dt)

                if self.sat_flagz == 1:
                    desired_vel_z = self._PID(self._dist_errz,1,dt)
                else:
                    desired_vel_z = self._PID(self._dist_errz,integ_len,dt)

                # desired_vel_x = self._PID(self._dist_errx,self.sat_idx_x,dt)
                # desired_vel_y = self._PID(self._dist_erry,self.sat_idx_y,dt)
                # desired_vel_z = self._PID(self._dist_errz,self.sat_idx_z,dt)

                ### Impose saturation on state variables
                self.sat_flagx = 0
                self.sat_flagy = 0
                self.sat_flagz = 0

                # simplified second order model
                # this is not correct, max acceleration is for resulting (x,y,z) vector e.g. sqrt(x^2+y^2+z^2)
                if abs((desired_vel_x-speedx)/dt) > self.max_acc:
                    desired_vel_x = math.copysign(1,desired_vel_x)*(self.max_acc * dt) + speedx
                    self.sat_flagx = 1
                    self.sat_idx_x = len(self._dist_errx)
                if abs((desired_vel_y-speedy)/dt) > self.max_acc:
                    desired_vel_y = math.copysign(1,desired_vel_y)*(self.max_acc * dt) + speedy
                    self.sat_flagy = 1
                    self.sat_idx_y = len(self._dist_erry)
                if abs((desired_vel_z-speedz)/dt) > self.max_acc:
                    desired_vel_z = math.copysign(1,desired_vel_z)*(self.max_acc * dt) + speedz
                    self.sat_flagz = 1
                    self.sat_idx_z = len(self._dist_errz)

                # this is not correct, max speed is for resulting (x,y) vector e.g. sqrt(x^2+y^2)
                if abs(desired_vel_x) > self.max_speed:
                    desired_vel_x = math.copysign(1,desired_vel_x)*self.max_speed
                    self.sat_flagx = 1
                    self.sat_idx_x = len(self._dist_errx)
                if abs(desired_vel_y) > self.max_speed:
                    desired_vel_y = math.copysign(1,desired_vel_y)*self.max_speed
                    self.sat_flagy = 1
                    self.sat_idx_y = len(self._dist_erry)
                if desired_vel_z > self.max_ascent:
                    desired_vel_z = self.max_ascent
                    self.sat_flagz = 1
                    self.sat_idx_z = len(self._dist_errz)
                elif desired_vel_z < -1*self.max_descent:
                    desired_vel_z = -1*self.max_descent
                    self.sat_flagz = 1
                    self.sat_idx_z = len(self._dist_errz)

                newPosX = desired_vel_x * dt + self.x[-1]
                newPosY = desired_vel_y * dt + self.y[-1]
                newPosZ = desired_vel_z * dt + self.z[-1]



        self.x.append(self.sim['x'][-1])
        self.y.append(self.sim['y'][-1])
        self.z.append(self.sim['z'][-1])
        self.time.append(TIME)



    def _integrate(self,err_list,integ_len):
        result = 0

        if len(err_list) < integ_len:
            for val in err_list:
                result = result + val
        else:
            for val in err_list[-integ_len:-1]:
                result = result + val

        return result

    def _PID(self,err_list,integ_len,dt):
        ## PID controller gain values
        Kp = .11
        Ki = 0
        Kd = 0

        result = Kp*err_list[-1] + Ki*(self._integrate(err_list,integ_len)) + Kd*(err_list[-1]-err_list[-2])/dt

        return result

    # def _PID(self,err_list,integ_idx,dt):
    #     ## PID controller gain values
    #     Kp = .115
    #     Ki = .8
    #     Kd = 0

    #     result = Kp*err_list[-1] + Ki*(self._integrate(err_list,integ_idx)) + Kd*(err_list[-1]-err_list[-2])/dt

    #     return result

    # def _integrate(self,err_list,integ_idx):
    #     result = 0

    #     for val in err_list[integ_idx:-1]:
    #         result = result + val

    #     return result

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

    def _add3D(self):
        if not self.model3D:
            model = next((model for model in Model.all_models if model.agent == None), None)
            if model:
                model.assign(self)
                self.model3D = model
            else:
                self.model3D = None
                logger.error("No models currently available to assign to UAV #"+str(self.id))
        else:
            logger.error("Model already assigned to UAV #"+str(self.id))

    def _remove3D(self):
        if self.model3D:
            self.model3D.unassign()
            self.model3D = None
        else:
            logger.error("Model not assigned to UAV #"+str(self.id))

    
    def _addCamera(self):
        if not self.camera:
            cam = next((camera for camera in Camera.all_cameras if camera.agent == None), None)
            if cam:
                cam.assign(self)
                self.camera = cam
            else:
                self.camera = None
                logger.error("No cameras currently available to assign to UAV #"+str(self.id))

    def _removeCamera(self):
        if self.camera:
            self.camera.unassign()
            self.camera = None


class Model:
    all_models = []
    active_models = []

    def __eq__(self, other):
        return self.id == other.id

    def __init__(self, filepath, model_scale=1, pos=[0,0,-100], yaw_offset=0):
        model = Vissim.Net.Static3DModels.AddStatic3DModel(0, filepath, 'Point(0, 0, 0)')
        model.SetAttValue('CoordX', pos[0])
        model.SetAttValue('CoordY', pos[1])
        model.SetAttValue('CoordZOffset', pos[2])
        model.SetAttValue('Scale', model_scale)
        self.model = model
        self.agent = None
        self.update_rate = 1
        self.update_counter = 1
        self.yaw_offset = yaw_offset
        if not self.all_models:
            self.id = 0
        else:
            max_id = max([model.id for model in self.all_models])
            self.id = max_id + 1
        Model.all_models.append(self)

    def assign(self,agent):
        if self.agent == None:
            self.agent = agent
            Model.active_models.append(self)
        else:
            logger.error("Model already assigned to agent with ID #"+str(agent.id))

    def unassign(self):
        if self.agent != None:
            self.agent = None
            Model.active_models.remove(self)
        else:
            logger.error("Model not assigned to agent with ID #"+str(agent.id))

    def update(self, update_rate):
        # update_rate = 1 means the model will update every time step. update_rate= 2 will update every two time steps
        if update_rate != self.update_rate:
            self.update_rate = update_rate
            self.update_counter = 1

        if self.agent != None:
            if self.update_counter/self.update_rate >= 1:
                point = "Point(" + str(self.agent.x[-1]) + ", " + str(self.agent.y[-1]) + ", " + str(self.agent.z[-1]) + ")"
                self.model.SetAttValue('CoordWktPoint3D', point)
                # self.model.SetAttValue('CoordX',self.agent.x[-1])
                # self.model.SetAttValue('CoordY',self.agent.y[-1])
                # self.model.SetAttValue('CoordZOffset',self.agent.z[-1])

                # self.model.SetAttValue('PitchAngle', )
                # self.model.SetAttValue('RollAngle', )
                self.model.SetAttValue('YawAngle', (self.agent.heading[2]+self.yaw_offset)%360)
                self.update_counter = 1
            else:
                self.update_counter += 1
        else:
            logger.error("Model not assigned to agent with ID #"+str(agent.id))



class Camera:
    all_cameras = []
    active_cameras = []

    def __eq__(self, other):
        return self.id == other.id

    def __init__(self, num_cameras=1, parameters=None):
        # may need to delete all existing cameras and storyboards
        camera_default = CAMERA_DEFAULT
        if parameters != None:
            for param in parameters:
                camera_default[param] = parameters[param]

        camera = Vissim.Net.CameraPositions.AddCameraPosition(0, 'Point(0, 0, 0)') 
        camera.SetAttValue('CoordX', camera_default['Pos'][0])
        camera.SetAttValue('CoordY', camera_default['Pos'][1])
        camera.SetAttValue('CoordZ', camera_default['Pos'][2])
        camera.SetAttValue('FOV', camera_default['FOV'])
        camera.SetAttValue('PitchAngle', camera_default['PitchAngle'])
        camera.SetAttValue('RollAngle', camera_default['RollAngle'])
        camera.SetAttValue('YawAngle', camera_default['YawAngle'])
        self.camera = camera
        self.agent = None
        self.update_rate = 1
        self.update_counter = 1
        # define a unique id
        if not self.all_cameras:
            self.id = 0
        else:
            max_id = max([camera.id for camera in self.all_cameras])
            self.id = max_id + 1
        Camera.all_cameras.append(self)

        storyboard = Vissim.Net.Storyboards.AddStoryboard(0)
        storyboard.SetAttValue('Filename', RESULTS_DIR+"Camera "+str(self.id)+".avi")
        storyboard.SetAttValue('RecAVI', camera_default['RecAVI']) # create AVI file
        storyboard.SetAttValue('ShowPrev', camera_default['ShowPrev']) # show preview of camera during sim
        storyboard.SetAttValue('Resolution', 1) # specify user defined resolution. Must do this to specify x,y res
        storyboard.SetAttValue('ResX', camera_default['ResX'])
        storyboard.SetAttValue('ResY', camera_default['ResY'])
        storyboard.SetAttValue('Framerate', camera_default['Framerate'])

        keyframe = storyboard.Keyframes.AddKeyframe(0)
        keyframe.SetAttValue('CamPos', camera)
        keyframe.SetAttValue('StartTime', 1) # StartTime == 0 means that recording must be manually started from presentation tab
        keyframe.SetAttValue('DwellTime', 600)

    def assign(self,agent):
        if self.agent == None:
            self.agent = agent
            Camera.active_cameras.append(self)
        else:
            logger.error("Camera already assigned to agent with ID #"+str(agent.id))

    def unassign(self):
        if self.agent != None:
            self.agent = None
            Camera.active_cameras.remove(self)
        else:
            logger.error("Camera not assigned to agent with ID #"+str(agent.id))

    def update(self, update_rate):
        # update_rate = 1 means the model will update every time step. update_rate= 2 will update every two time steps
        if update_rate != self.update_rate:
            self.update_rate = update_rate
            self.update_counter = 1

        if self.agent != None:
            if self.update_counter/self.update_rate >= 1:
                point = "Point(" + str(self.agent.x[-1]) + ", " + str(self.agent.y[-1]) + ", " + str(self.agent.z[-1]) + ")"
                self.camera.SetAttValue('CoordWktPoint3D', point)
                # self.camera.SetAttValue('CoordX',self.agent.x[-1])
                # self.camera.SetAttValue('CoordY',self.agent.y[-1])
                # self.camera.SetAttValue('CoordZ',self.agent.z[-1])

                # self.model.SetAttValue('PitchAngle', )
                # self.model.SetAttValue('RollAngle', )
                self.camera.SetAttValue('YawAngle', self.agent.heading[2])

                self.update_counter = 1
            else:
                self.update_counter += 1
        else:
            logger.error("Camera not assigned to agent with ID #"+str(agent.id))