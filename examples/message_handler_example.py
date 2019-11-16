import logging

__author__ = "Garrett Dowd"
__copyright__ = "Copyright (C) 2019 Garrett Dowd"
__license__ = "MPL-2.0"
__version__ = "0.0.1"

logger = logging.getLogger(__name__)

""" Intended Use Documentation Here
A message handler defines the available message types, format of a message payload, packing of messages into a payload, and parsing data from a payload.
It is recommended that payloads be dicts for easy parsing
A message handler should only read external data, not write. A message handler should be generic enough to apply to any use case. This means any actions taken from received messages should be contained within the main python project file or another project related file.

# Requirements
- define msg_types dict
- define receive()
-- input should be the follwowing, receive(agent, sender_id, msg_type, payload)
- define send()
-- input should be the following, send(agent, recipient_id=-1, msg_type='loc', payload='null')

# Optional
- any other functions or data structures related to the defined msg_types

"""

# list of all valid message types to validate against
# Currently, only keys used, values not used
msg_types = {
    'loc':      0,  # [x,y,z] coordinates
    'BSM':      20,  # [time, message #, location, speed, heading, acceleration]
    'SPAT':     19,
    'TIM':      31,  # can be used for a lot of stuff, use ITIS phrases
    'EVA':      22,  # emergency vehicle alert
    'ICA':      23,  # intersection collision avoidance
    'PSM':      32,  # personal safety message, for vulnerable road users
    'PVD':      26, # probe vehicle data, send data to RSU
    'RSA':      27, # road side alert
}

def send(agent, recipient_id=-1, msg_type='loc', payload='null'):
    # It is strongly recommended to NOT change the recipient_id nor the msg_type in this function. This is for simplicity and clarity

    if (msg_type == 'loc') & (payload == 'null'):
        payload = {
            'location': agent.position(),
        }
        
    if (msg_type == 'RSA') & (payload == 'null'):
        payload = {
            'location': agent.position(),
            'link': agent.link,
            'lane':agent.lane,
        }

    result = {
        'recipient_id':  recipient_id,
        'msg_type':      msg_type,
        'payload':       payload,
    }
    return result


def receive(agent, sender_id, msg_type, payload):
    if msg_type == 'loc': # location
        logger.debug("Car # " + str(agent.id) + " received location "+str(payload) +" from " + str(sender_id))
    if msg_type == 'RSA': # road side alert
        location = payload['location']
        link = payload['link']
        lane = payload['lane']
        dist = agent._dist(agent.position(),payload['location'])
        logger.debug("Car # " + str(agent.id) + " received RSA from Agent # " + str(sender_id) + " which is "+str(dist)+" meters away")
        # if link == self.link:
        #     logger.debug("Car # " + str(self.id) + " slowing down for RSA on link " + str(self.link) + " which is "+str(dist)+" meters away")
        #     self.set_desired_speed(self.dspeed-15)
        #     if lane == self.lane
        #         if lane >= 3 | lane < 2:
        #             des_lane = 2
        #         else:
        #             des_lane = 1 
        #         self.vissim.SetAttValue('DesLane',des_lane)

    result = {
        'sender_id':  sender_id,
        'msg_type':   msg_type,
        'payload':    payload,
    }
    return result
