#!/usr/bin/env python

from Controllers.device import Device
from Controllers.Simulator.iis_simu import IisSimulator

class iis(Device):
    def __init__(self, actor, name):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        super(iis, self).__init__(actor, name)

    def getStatus(self, cmd):
        return True, "online"
