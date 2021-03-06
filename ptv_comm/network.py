import os
import logging
from collections import namedtuple
import random
import pandas as pd

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MPL-2.0"
__version__ = "0.0.1"

"""Implements a simple wired/wireless network for message passing.

This module provides the underlying networking that objects can use to pass messages.
Usually, the methods in this module will not be used directly, instead wrapper methods will be
    defined in the object classes that use this module.
"""

logger = logging.getLogger(__name__)
Message = namedtuple('Message', 'timestamp, sender_id, sender_loc, recipient_id, recipient_loc, msg_type, payload, delay, dropped')
Event = namedtuple('Event', 'time, priority, action, argument')

def setup(_Vissim, _RESULTS_DIR):
    """Call before beginning of simulation to initialize module.

    Gives the module access to the Vissim COM API and 
    defines a directory to save results to.

    Args:
        _Vissim:(COM) the Vissim COM object associated with your simulation, commonly "Vissim"
        _RESULTS_DIR:(string) an absolute directory
    """
    global Vissim       #follows naming convention of standard Vissim COM interface
    global RESULTS_DIR
    global SIM_RES

    Vissim = _Vissim
    RESULTS_DIR = _RESULTS_DIR
    SIM_RES = Vissim.Simulation.AttValue('SimRes')
    

def update():
    """Call every time step to update messages.

    This makes sure that every network is updated and messages are sent.
    """
    for net in Net.all_nets:
        net.update()


class Net:
    """Generic Network class for message passing.

    This class enables messages to be passed between objects with simplified
    wired/wireless networking properties such as stochastic distance limits and delay.

    Attributes:
        type:(string) indicates a class of communicatin technology. Labelling purposes only
        agents:(list[list[object]]) a list of lists containing objects reprsenting nodes in the network
        NOT IMPLEMENTED - reliability_pct:(float) a percentage used to estimte the reliability of message delivery
        delay_gauss_mean:(float) gaussian mean of delay
        delay_guass_stddev:(float) guassian standard deviation of delay
        s:(Sched object) the scheduler object to use for scheduling messages
        all_messages:(list) a list of all created messages
        all_nets:(list) list of all instantiated Net objects
    """

    all_nets = [] # list of all instantiated Net objects

    def __eq__(self, other):
        if other:
            return self.id == other.id
        else:
            return False


    def __init__(self, tech_type, list_of_lists_of_agents, reliability_pct = 1 , delay_gauss_mean = 0, delay_guass_stddev = 0):
        """Call before beginning of simulation to initialize module.

        Gives the module access to the Vissim COM API and 
        defines a directory to save results to.

        Args:
            type:(string) indicates a class of communicatin technology. Labelling purposes only
            agents:(list[list[object]]) a list of lists containing objects* reprsenting nodes in the network
            NOT IMPLEMENTED - reliability_pct:(float) a percentage used to estimte the reliability of message delivery
            delay_gauss_mean:(float) gaussian mean of delay
            delay_guass_stddev:(float) guassian standard deviation of delay

        *object must have a receive method - agent.receiveMsg(sender_id, msg_type, payload)
        *object must have a unique "id" attribute - agent.id
        """
        # define a unique id
        if not self.all_nets:
            self.id = 0
        else:
            max_id = max([net.id for net in self.all_nets])
            self.id = max_id + 1

        self.type = tech_type
        self.agents = list_of_lists_of_agents
        self.reliability_pct = reliability_pct
        self.delay_gauss_mean = delay_gauss_mean
        self.delay_guass_stddev = delay_guass_stddev
        self.s = Sched(self._timefunc)
        self.all_messages = []

        self.all_nets.append(self) # add this instance to list of all instances for iteration


    def update(self):
        """No need to call this function directly.

        This udpdates the assocaited scheduler which sends delayed messages.
        This function is called by the module level update function.
        """
        self.s.update()


    def broadcast(self, broadcast_location, comm_range, msg_type, payload, recipient_id = -1, sender_id = -1):
        """ Sends a message.

        Args:
            broadcast_location:(list) [X,Y] or [X,Y,Z] must be given as it determines which agents will be in range to receive the message
            msg_type:(*) externally defined message types that determine how an agent shoud interpret the message. This could eventually be combined with the payload
            payload:(*) parsing of payload is left to receiving agents
            recipient_id:(integer) -1 will broadcast the message to all agents within range
            sender_id: (integer) -1 means that the message is being sent anonymously

        Recipient_id must be unique among all agents - this is a reason to implement IP networking
        """

        if recipient_id == -1: # broadcast to all agents NOT including self (unless sent anonymously)
            for agent_list in self.agents:
                for agent in agent_list:
                    if agent.id != sender_id:
                        msg = self._createMsg(sender_id, agent.id, msg_type, payload, broadcast_location, agent.position(), comm_range)
                        self._scheduleMsg(msg)
        else: # broadcast only to desired recipient_id
            for agent_list in self.agents:
                agent = next((agent for agent in agent_list if agent.id==recipient_id), None)
                if agent != None:
                    msg = self._createMsg(sender_id, agent.id, msg_type, payload, broadcast_location, agent.position(), comm_range)
                    self._scheduleMsg(msg)
                else:
                    logger.error("When broadcasting a message, given recipient_id #"+str(recipient_id)+" does not exist")
                    # Vissim.Simulation.Stop()

    def _createMsg(self, sender_id, recipient_id, msg_type, payload, sender_loc, recipient_loc, comm_range):
        """Sub- function to create a message and calculate metadata.

        This function creates a Message with delay and drop metadata
        """
        time = Vissim.Simulation.AttValue('SimSec')
        delay = self._delay()
        dist = self._dist(sender_loc,recipient_loc)
        dropped = self._drop(dist, comm_range)
        msg =  Message(time, sender_id, sender_loc, recipient_id, recipient_loc, msg_type, payload, delay, dropped)
        self.all_messages.append(msg)
        return msg

    def _scheduleMsg(self, message):
        """Schedule the message for future.

        Args:
            message:(Message)

        If the delay is less than the simulation time step resolution then it sends it immediately.
        Otherwise it schedules the message to be sent in the future.
        """
        if message.dropped == 0:
            if message.delay < SIM_RES:
                self._sendMsg(message)
            else:
                self.s.enter(message.delay,1,self._sendMsg,(message))

    def _sendMsg(self, message):
        """This delivers a message to a recipient.

        Args:
            message:(Message)

        Find the correct agent and call that agents receive message function.
        """
        for agent_list in self.agents:
            agent = next((agent for agent in agent_list if agent.id==message.recipient_id), None)
            if agent != None:
                agent.receiveMsg(message.sender_id, message.msg_type, message.payload)

    
    def _delay(self):
        """
        message delays can be used, but anything shorter than the sim time step
        is trivial and can be ignored. This should be the case given a normal simulation time step
        and a max communication distance of 1-2km

        # maybe should be based on congestion?
        """
        return random.gauss(self.delay_gauss_mean, self.delay_guass_stddev)

    def _dist(self, loc1, loc2):
        """Calculate euclidian distance.

        Args:
            loc1:(list) [X,Y] or [X,Y,Z]  if only [X,Y] then Z is assumed to be 0
            loc2:(list) [X,Y] or [X,Y,Z]  if only [X,Y] then Z is assumed to be 0

        """
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

    # this needs to be updated with an equation that can better model the chance of dropping messages based on distance
    def _drop(self, dist, comm_range):
        """Determine if message will be dropped (delivery failure).

        Args:
            dist:(float) the distance betwwen agents
            comm_range:(float) rated distance at which the transmitter can send a message

        Stochastic drop logic has not yet been implemented        
        """
        normalized_diff = (comm_range - dist)/comm_range
        
        if normalized_diff > 0:
            return 0 # message is not dropped
        elif normalized_diff < 0:
            return 1 # message is dropped

    def _timefunc(self):
        """Returns Vissim SimSec."""
        return float(Vissim.Simulation.AttValue('SimSec'))



def saveResults(filepath=None):
    """Save all messages to a csv file.

    Args:
        filepath:(string) an absolute filepath. 

    If a file path is not given then the default will be used
    """
    # make sure that the necessary folder structure exists
    if filepath == None:
        filepath = RESULTS_DIR
    # make sure that the necessary folder structure exists
    file_dir = os.path.dirname(filepath)
    if not os.path.exists(file_dir):
        logger.debug("Creating directory "+file_dir)
        os.makedirs(file_dir)

    logger.info("saving network results to "+filepath)
    column_comms = ['timestamp', 'sender_id', 'sender_loc', 'recipient_id', 'recipient_loc', 'msg_type', 'payload', 'delay', 'dropped']
    df = []
    for net in Net.all_nets:
        for msg in net.all_messages:
            df_d = {
                'timestamp': msg.timestamp,
                'sender_id': msg.sender_id,
                'sender_loc': msg.sender_loc,
                'recipient_id': msg.recipient_id,
                'recipient_loc': msg.recipient_loc,
                'msg_type': msg.msg_type,
                'payload': msg.payload,
                'delay': msg.delay,
                'dropped': msg.dropped
            }
            df.append(df_d)

    df = pd.DataFrame(df)
    df = df.reindex(columns=column_comms)  # ensure columns are in correct order
    # df = df.iloc[::-1] # reverse order of rows
    df.to_csv(filepath, encoding='utf-8', index=False)



def id(num):
    """Return the Net object with the given id number"""
    return next((net for net in Net.all_nets if net.id==num), None)




class Sched:
    """ Generic python module "Sched" will not work in this context
    Modify library slightly to work in this context
    Main differences:
    no delayfunc needed
    no run() method. Replaced with update() method that is called every loop
    "priority" not used because there is no real time context where events can be delayed past the intended delay time
    heapq not used. regular sorted list used instead
    """
    def __init__(self,timefunc):
        self.time = timefunc
        self._queue = [] # sorted from next to last

    def enterabs(self, time, priority, action, argument):
        """Enter a new event in the queue at an absolute time.
        Returns an ID for the event which can be used to remove it,
        if necessary.
        """
        event = Event(time, priority, action, argument)
        self._queue.append(event)
        self._queue.sort(key=lambda x: x[1][0]) # sort by time
        return event # The ID

    def enter(self, delay, priority, action, argument):
        """A variant that specifies the time as a relative time.
        This is actually the more commonly used interface.
        """
        time = self.time() + delay
        return self.enterabs(time, priority, action, argument)

    def cancel(self, event):
        """Remove an event from the queue.
        This must be presented the ID as returned by enter().
        If the event is not in the queue, this raises ValueError.
        """
        self._queue.remove(event)

    def empty(self):
        """Check whether the queue is empty."""
        return not self._queue

    def update(self):
        now = self.time()
        while self._queue:
            time, priority, action, argument = self._queue[0]
            if now <= time:
                return
            else:
                self._queue.pop(0)
                action(*argument)
