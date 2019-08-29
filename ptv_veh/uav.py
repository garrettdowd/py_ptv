import os
import math
import datetime as dt
import logging
from collections import namedtuple
import pandas as pd

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MIT"
__version__ = "0.0.1"

logger = logging.getLogger(__name__)

class Skill(namedtuple('Skill', 'id, min_speed, max_speed, max_acc, max_ascent, max_descent, comm_range')):
    def __eq__(self, other):
        return self.id == other.id

SKILLS = [
    Skill(0, 0, 35, 3.5, 5, 2, 1000),
    Skill(10, 0, 19.9, 4, 5, 3, 800),
    Skill(20, 0, 45, 4, 5, 3, 800),
    Skill(100, 15.2, 39, 4, 5, 3, 900)
]
CAMERA_PARAM = {
    'FOV': 20,
    'PitchAngle': 90,
    'RollAngle': 0,
    'YawAngle': 0,
    'RecAVI': "true",
    'ShowPrev': "true",
    'ResX': 720,
    'ResY': 480,
    'Framerate': 20,
}
DEFAULT = {
    'comms': None,
    'msg_handler': None,
    'model_flag': False,
    'camera_flag': False,
    'skill': 0,
    'position': [0,0,0],
    'sim_freq': 20 # multiple of 10
}
""" Intended Use Documentation Here
3D Models and cameras must be created before the start of simulation so the code had to be structured to accomodate that requirement
3D Models can really slow down the simulation speed (by half)


"""
def setup(_Vissim, _RESULTS_DIR, model_filepath, num_models=0, model_scale=1, num_cameras=0, defaults=None, uav_skills=None, camera_param=None):
    global Vissim
    global RESULTS_DIR
    global SKILLS
    global CAMERA_PARAM
    global TIME
    global DEFAULT

    Vissim = _Vissim
    RESULTS_DIR = _RESULTS_DIR

    if uav_skills != None:
        for new_skill in uav_skills:
            if new_skill in SKILLS:
                idx = SKILLS.index(new_skill)
                SKILLS[idx] = new_skill
            else:
                SKILLS.append(new_skill)

    if camera_param != None:
        for param in camera_param:
            CAMERA_PARAM[param] = camera_param[param]

    if defaults != None:
        for default in defaults:
            DEFAULT[default] = defaults[default]

    TIME = float(Vissim.Simulation.AttValue('SimSec'))
    # cannot create static models during simulation 
    # so must create a predefined number before simulation starts
    # define uav models

    # Create new stuff based on definitions above
    if num_models > 0:
        for i in range(num_models):
            Vissim.Net.Static3DModels.AddStatic3DModel(0, model_filepath, 'Point(0, 0, 0)')
        models = Vissim.Net.Static3DModels.GetAll()
        for model in models:
            model.SetAttValue('CoordX', 0)
            model.SetAttValue('CoordY', 0)
            model.SetAttValue('CoordZOffset', -100)
            model.SetAttValue('Scale', model_scale)
            Model(model)
            

    if num_cameras > 0:
        for i in range(num_cameras):
            Vissim.Net.CameraPositions.AddCameraPosition(0, 'Point(0, 0, 0)') 
            Vissim.Net.Storyboards.AddStoryboard(0)
        cameras = Vissim.Net.CameraPositions.GetAll()
        for camera in cameras:
            camera.SetAttValue('CoordX', 0)
            camera.SetAttValue('CoordY', 0)
            camera.SetAttValue('CoordZ', -100)
            camera.SetAttValue('FOV', CAMERA_PARAM['FOV'])
            camera.SetAttValue('PitchAngle', CAMERA_PARAM['PitchAngle'])
            camera.SetAttValue('RollAngle', CAMERA_PARAM['RollAngle'])
            camera.SetAttValue('YawAngle', CAMERA_PARAM['YawAngle'])
            Camera(camera)
        storyboards = Vissim.Net.Storyboards.GetAll()
        i = 0 # to name the video files
        for i,storyboard in enumerate(storyboards):
            storyboard.SetAttValue('Filename', _RESULTS_DIR+"Camera "+str(i)+".avi")
            storyboard.SetAttValue('RecAVI', CAMERA_PARAM['RecAVI']) # create AVI file
            storyboard.SetAttValue('ShowPrev', CAMERA_PARAM['ShowPrev']) # show preview of camera during sim
            storyboard.SetAttValue('Resolution', 1) # specify user defined resolution. Must do this to specify x,y res
            storyboard.SetAttValue('ResX', CAMERA_PARAM['ResX'])
            storyboard.SetAttValue('ResY', CAMERA_PARAM['ResY'])
            storyboard.SetAttValue('Framerate', CAMERA_PARAM['Framerate'])
            storyboard.Keyframes.AddKeyframe(0)
            keyframes = storyboards[i].Keyframes.GetAll()
            for keyframe in keyframes:
                keyframe.SetAttValue('CamPos', cameras[i])
                keyframe.SetAttValue('StartTime', 1) # StartTime == 0 means that recording must be manually started from presentation tab
                keyframe.SetAttValue('DwellTime', 600)
            


def update(): # call at beginning of every loop
    global TIME
    TIME = float(Vissim.Simulation.AttValue('SimSec'))

    for uav in UAV.active_uavs:
        uav.update()

    for model in Model.active_models:
        model.update()

    for camera in Camera.active_cameras:
        camera.update()

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
    def __init__(self, comms=None, msg_handler=None, model_flag=None, camera_flag=None, skill=None, pos=None, sim_frequency=None):
        if comms == None:
            comms = DEFAULT['comms']
        if msg_handler == None:
            msg_handler = DEFAULT['msg_handler']
        if model_flag == None:
            model_flag = DEFAULT['model_flag']
        if camera_flag == None:
            camera_flag = DEFAULT['camera_flag']
        if skill == None:
            skill = DEFAULT['skill']
        if pos == None:
            pos = DEFAULT['position']
        if sim_frequency == None:
            sim_frequency = DEFAULT['sim_freq']

        # define a unique id
        if not self.all_uavs:
            self.id = 0
        else:
            max_id = max([uav.id for uav in self.all_uavs])
            self.id = max_id + 1
        if len(pos) != 3:
            logger.critical("UAV instantiation, invalid position: "+ str(pos))
            Vissim.Simulation.Stop()
        self.time = [TIME]
        self.x = [pos[0]]
        self.y = [pos[1]]
        self.z = [pos[2]]
        self.position = lambda: [self.x[-1],self.y[-1],self.z[-1]] # current position

        self.dest = [[pos[0],pos[1],pos[2]]] # destination. where uav should be flying to
        self.mission = 0 # defines what the uav should be doing e.g. car following = 1, stationary point = 0.

        UAV.all_uavs.append(self)
        UAV.active_uavs.append(self)
        self.active = True # is this object currently active in the simulation?

        self.model3D = None
        self.camera = None
        if camera_flag:
            self._addCamera()

        if model_flag:
            self._add3D()

        self.setComms(comms) # Comm object
        self.setMsgHandler(msg_handler)
        self.setSkill(skill)

        ##########################################################
        self.sim = dict()
        self.sim['freq'] = sim_frequency

    def update(self):
        if self.mission == 'car':
            xy = self.car.position()
            xyz = xy.append(self.follow_altitude)
            self.dest.append(xyz)
        self._simXYZ("ZO")


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

        # self.model3D.SetAttValue('CoordX',0)
        # self.model3D.SetAttValue('CoordY',0)
        # self.model3D.SetAttValue('CoordZOffset',500)

    def setDest(self, xyz):
        if len(xyz) == 2:
            xyz.append(30) # default altitude, need better default value
        elif len(xyz) == 3:
            pass
        else:
            logger.critical("Invalid input to setDest- " + str(xyz))
            Vissim.Simulation.Stop()

        self.dest.append(xyz)
        # self.mission = 0 # go to point and stay there
        # self._tracking_flag = 0


    def setCar(self, car, follow_altitude=40):
        self.car = car
        self.mission = 'car' # actively track vehicle, possibly fly ahead to scout
        self.follow_altitude = follow_altitude



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
        logger.debug("Setting comms for UAV # "+str(self.id))
        self.comms = comm

    def setSkill(self,skill_id):
        logger.debug("Setting skill # "+str(skill_id)+" for UAV # "+str(self.id))
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

    def _simXYZ(self, sim_type, sim_freq=None):
        if not sim_freq:
            sim_freq = self.sim['freq']

        dt = (TIME - self.time[-1])
        time_steps = int(dt*sim_freq)

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
                camera.assign(self)
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

    def __init__(self,model):
        self.model = model
        self.agent = None
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

    def update(self):
        if self.agent != None:
            point = "Point(" + str(self.agent.x[-1]) + ", " + str(self.agent.y[-1]) + ", " + str(self.agent.z[-1]) + ")"
            self.model.SetAttValue('CoordWktPoint3D', point)
            # self.model.SetAttValue('CoordX',self.agent.x[-1])
            # self.model.SetAttValue('CoordY',self.agent.y[-1])
            # self.model.SetAttValue('CoordZOffset',self.agent.z[-1])
        else:
            logger.error("Model not assigned to agent with ID #"+str(agent.id))



class Camera:
    all_cameras = []
    active_cameras = []

    def __eq__(self, other):
        return self.id == other.id

    def __init__(self,camera):
        self.camera = camera
        self.agent = None
        # define a unique id
        if not self.all_cameras:
            self.id = 0
        else:
            max_id = max([camera.id for camera in self.all_cameras])
            self.id = max_id + 1
        Camera.all_cameras.append(self)

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

    def update(self):
        if self.agent != None:
            point = "Point(" + str(self.agent.x[-1]) + ", " + str(self.agent.y[-1]) + ", " + str(self.agent.z[-1]) + ")"
            self.model.SetAttValue('CoordWktPoint3D', point)
            # self.camera.SetAttValue('CoordX',self.agent.x[-1])
            # self.camera.SetAttValue('CoordY',self.agent.y[-1])
            # self.camera.SetAttValue('CoordZ',self.agent.z[-1])
        else:
            logger.error("Camera not assigned to agent with ID #"+str(agent.id))