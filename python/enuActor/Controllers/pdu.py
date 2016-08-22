#!/usr/bin/env python

import time

import numpy as np

from Controllers.device import Device
from Controllers.Simulator.pdu_simu import PduSimulator

class pdu(Device):
    def __init__(self, actor, name):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        super(pdu, self).__init__(actor, name)


    def getStatus(self, cmd):
        return True, "online"