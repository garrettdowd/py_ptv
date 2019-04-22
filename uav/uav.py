import datetime as dt
import math

def UAV_setup(_Vissim, _num_uavs = 8, _num_cameras = 1, _uav_base = [297, 380, 15], _uav_skills=-1, model_directory="3D Models", results_directory="Script.results"):
    global Vissim
    global uav_base
    global num_uavs
    global uav_skills
    global num_cameras
    global cameras
    global uav_models

    Vissim = _Vissim
    uav_base = _uav_base
    num_uavs = _num_uavs
    num_cameras = _num_cameras
    if _uav_skills == -1:
        # These skills define the characteristics/abilities of the objects during simulation
        # [Skill#,[min_speed(x,y)(m/s), max_speed(x,y)(m/s), max_acc(x,y,z)(m/s^2), max_ascent(z)(m/s), max_descent(z)(m/s), comm_range(m)]]
        uav_skills = [
            [10, [0, 19.9, 4, 5, 3, 800]],
            [20,[0, 45, 4, 5, 3, 800]],
            [100,[15.2, 39, 4, 5, 3, 900]]
            ]
    else:
        uav_skills = _uav_skills


    # save this time to use for file naming
    sim_time = str(dt.datetime.now().strftime("%y-%m-%d-%H-%M"))


    # cannot create static models during simulation 
    # so must create a predefined number before simulation starts
    # define uav landing base
    file3D_base = model_directory + "\\uavbase.skp"
    scale_base = 1.5 # not implemented

    # define uav models
    file3D = model_directory + "\\quad.skp"
    scale = .9


    # Create new stuff based on definitions above
    for i in range(num_uavs):
        Vissim.Net.Static3DModels.AddStatic3DModel(0, file3D, 'Point(0, 0, 0)')
    for i in range(num_cameras):
        Vissim.Net.CameraPositions.AddCameraPosition(0, 'Point(0, 0, 0)') # add one camera for each uav
        Vissim.Net.Storyboards.AddStoryboard(0) # add one storyboard for each uav

    uav_models = Vissim.Net.Static3DModels.GetAll()
    cameras = Vissim.Net.CameraPositions.GetAll()
    storyboards = Vissim.Net.Storyboards.GetAll()
    for model in uav_models:
        model.SetAttValue('CoordX', uav_base[0])
        model.SetAttValue('CoordY', uav_base[1])
        model.SetAttValue('CoordZOffset', uav_base[2])
        model.SetAttValue('Scale', scale)
    for camera in cameras:
        camera.SetAttValue('CoordX', uav_base[0])
        camera.SetAttValue('CoordY', uav_base[1])
        camera.SetAttValue('CoordZ', uav_base[2])
        camera.SetAttValue('FOV', 20)
        camera.SetAttValue('PitchAngle', 90)
        camera.SetAttValue('RollAngle', 0)
        camera.SetAttValue('YawAngle', 0)
    i = 0
    for storyboard in storyboards:
        storyboard.SetAttValue('Filename', results_directory+"\\Video\\"+sim_time+" uavCam "+str(i)+".avi")
        storyboard.SetAttValue('RecAVI', "true") # create AVI file
        storyboard.SetAttValue('ShowPrev', "true") # show preview of camera during sim
        storyboard.SetAttValue('Resolution', 1) # specify user defined resolution. Must do this to specify x,y res
        storyboard.SetAttValue('ResX', 720)
        storyboard.SetAttValue('ResY', 480)
        storyboard.SetAttValue('Framerate', 20)
        storyboard.Keyframes.AddKeyframe(0)
        keyframes = storyboards[i].Keyframes.GetAll()
        for keyframe in keyframes:
            keyframe.SetAttValue('CamPos', cameras[i])
            keyframe.SetAttValue('StartTime', 1) # StartTime == 0 means that recording must be manually started from presentation tab
            keyframe.SetAttValue('DwellTime', 600)
        i += 1


    point = 'Point('+str(uav_base[0])+', '+str(uav_base[1])+', 0)' # Vissim requires this string format
    Vissim.Net.Static3DModels.AddStatic3DModel(0, file3D_base, point)


class UAV:
    # define what happens when an uav object is instatiated
    def __init__(self, id_num, pos=-1, skill=20, comms=-1):
        if pos == -1:
            pos = uav_base
        elif len(pos) != 3:
            print("UAV instantiation invalid for 'pos'")
            Vissim.Simulation.Stop()
        self.id = id_num
        # initialize time and position
        self.time = [float(Vissim.Simulation.AttValue('SimSec'))]
        self.x = [pos[0]]
        self.y = [pos[1]]
        self.z = [pos[2]]
        self.position = [self.x[-1],self.y[-1],self.z[-1]]

        self.comms = comms

        self.active = 1 # is this object currently active in the simulation?
        self.dest = [[0,0,0]]
        self.mission = 0 # defines what the uav should be doing e.g. car following or stationary
        self.car_num = -1 # the number of the car in vissim that it should be following
        self.car_pos = [0,0] # place to store current [x,y] location of car with "car_num"

        # if there is an available camera then take it
        if self.id < num_cameras:
            self.camera = cameras[self.id]
        else:
            self.camera = -1

        self._add3D()
        self.update3D()

        # copy skills to local variables
        flag=0
        for item in uav_skills:
            if item[0] == skill:
                self.min_speed = item[1][0]
                self.max_speed = item[1][1]
                self.max_acc = item[1][2]
                self.max_ascent = item[1][3]
                self.max_descent = item[1][4]
                self.comm_range = item[1][5]
                flag=1
        if flag == 0:
            print("When instantiating a uav object, given skill #"+skill+" does not exist")
            Vissim.Simulation.Stop()

        # Stuff for control/simulation
        self._dist_errx = [0]   # error term for PID control
        self._dist_erry = [0]   # error term for PID control
        self._dist_errz = [0]   # error term for PID control

        ## Stuff for ZO Model
        self._tracking_flag = 0 

        ## Stuff for PID Control
        ### For integral windup
        self.sat_flagx = 0 # flags for whether the state is saturated (beyond max value)
        self.sat_flagy = 0
        self.sat_flagz = 0
        self.sat_idx_x = 0
        self.sat_idx_y = 0
        self.sat_idx_z = 0


    def setDest(self, xyz):
        if len(xyz) != 3:
            print("Invalid input to uav.setDest")
            Vissim.Simulation.Stop()

        self.dest.append(xyz)
        # self.mission = 0 # go to point and stay there
        # self._tracking_flag = 0


    def setCar(self, car_num):
        self.car_num = car_num
        self.mission = 1 # actively track vehicle, possibly fly ahead to scout
        self._tracking_flag = 0


    def sendMsg(self, recipient_id=-1, msg_type=0, payload=-1):
        if payload == -1:
            payload = self.position
        # default message is broadcast to everyone listening (-1)
        self.comms.broadcast(recipient_id,msg_type,payload)


    # all of the logic for handling messages happens here
    def receiveMsg(self, msg_type, payload):
        if msg_type == 0: # location
            print("Hi")




    def simXYZ(self, sim_type):
        SimSec = float(Vissim.Simulation.AttValue('SimSec'))
        dt = (SimSec - self.time[-1])
        
        if self.mission == 1:
            x = self.car_pos[0]
            y = self.car_pos[1]
            z = 150
            self.dest.append([x, y, z])


        ## calculate state parameters - could simplify this by initializing self.x as [0,0,0] instead of [0]
        if len(self.x)<2:
            speedx = 0
            speedy = 0
            speedz = 0
            speedxyz = 0
        else:
            speedx = (self.x[-1] - self.x[-2])/dt
            speedy = (self.y[-1] - self.y[-2])/dt
            speedz = (self.z[-1] - self.z[-2])/dt
            speedxyz = (speedx**2 + speedy**2 + speedz**2)**0.5

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

        ### calculate distance error term for control
        self._dist_errx.append(self.dest[-1][0] - self.x[-1])
        self._dist_erry.append(self.dest[-1][1] - self.y[-1])
        self._dist_errz.append(self.dest[-1][2] - self.z[-1])

        # ### calculate velocity error term for control
        # vel_errx = (self.dest[-1][0] - self.dest[-2][0])/dt - speedx
        # vel_erry = (self.dest[-1][1] - self.dest[-2][1])/dt - speedy
        # vel_errz = (self.dest[-1][2] - self.dest[-2][2])/dt - speedz

        if sim_type == "ZO":
            # if already tracking (locked on) to target then simply set destination as new/current position
            if self._tracking_flag == 1:
                newPosX = self.dest[-1][0]
                newPosY = self.dest[-1][1]
                newPosZ = self.dest[-1][2]
            else:
                # zero order model with velocity/acceleration saturation. uav will fly in direction defined by the distance error vector
                # direction vector
                dist_err_mag = (self._dist_errx[-1]**2 + self._dist_erry[-1]**2 + self._dist_errz[-1]**2)**0.5
                direction = [self._dist_errx[-1]/dist_err_mag, self._dist_erry[-1]/dist_err_mag, self._dist_errz[-1]/dist_err_mag]
                # vel_err_mag = (vel_errx**2 + vel_erry**2 + vel_errz**2)**0.5

                # saturation
                des_v_x = self._dist_errx[-1]/dt + speedx
                des_v_y = self._dist_erry[-1]/dt + speedy
                des_v_z = self._dist_errz[-1]/dt + speedz
                desired_vel = (des_v_x**2 + des_v_y**2 + des_v_z**2)**0.5
                desired_acc = ((des_v_x - speedx)**2 + (des_v_y - speedy)**2 + (des_v_z - speedz)**2)**0.5
                if desired_acc > self.max_acc:
                    desired_vel = self.max_acc * dt + speedxyz
                elif desired_vel > self.max_speed:
                    desired_vel = self.max_speed

                # to prevent jitter if the UAV is close enough then just set the UAV position as its destination
                if dist_err_mag < 1.5: # this value needed here will probably depend on the speed of the cars
                    self._tracking_flag = 1
                
                # calc new position
                newPosX = desired_vel * dt * direction[0] + self.x[-1]
                newPosY = desired_vel * dt * direction[1] + self.y[-1]
                newPosZ = desired_vel * dt * direction[2] + self.z[-1]


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


        self.x.append(newPosX)
        self.y.append(newPosY)
        self.z.append(newPosZ)
        self.time.append(SimSec)

        self.update3D()



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
        if len(uav_models) < 1:
            print("No Static Models exist...")
            Vissim.Simulation.Stop()
        self.model3D = uav_models[self.id]

    def update3D(self):
        if self.model3D is None:
            print("No Static Model assigned to uav object "+self.id+"...")
            Vissim.Simulation.Stop()
        self.model3D.SetAttValue('CoordX',self.x[-1])
        self.model3D.SetAttValue('CoordY',self.y[-1])
        self.model3D.SetAttValue('CoordZOffset',self.z[-1])

        if self.camera != -1:
            # Update camera
            self.camera.SetAttValue('CoordX',self.x[-1])
            self.camera.SetAttValue('CoordY',self.y[-1])
            self.camera.SetAttValue('CoordZ',self.z[-1])
            # self.camera.SetAttValue('FOV',20)
            # self.camera.SetAttValue('PitchAngle',90)
            # self.camera.SetAttValue('RollAngle',0)
            # self.camera.SetAttValue('YawAngle',0)


    def RTB(self):
        self.setDest(uav_base)
        self._tracking_flag = 0


    def update(self):
        self.simXYZ("ZO")
        self.update3D()


    def deactivate(self):
        self.active = 0
        self._tracking_flag = 0
        # self.model3D.SetAttValue('CoordX',0)
        # self.model3D.SetAttValue('CoordY',0)
        # self.model3D.SetAttValue('CoordZOffset',500)
