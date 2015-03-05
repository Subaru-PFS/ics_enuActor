#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                    Temperature SW device module                     #
#######################################################################
from enuActor.QThread import *
from Device import *


class Temperature(DualModeDevice):

    """SW device: Temperature

    """

    def __init__(self, actor=None):
        super(Temperature, self).__init__(actor)
        self.currPos = None


    @transition('init', 'idle')
    def initialise(self):
        """Initialise Bia.

        .. note:: Should be improved after getting hardware status

        """
        self.check_status()

    @transition('busy', 'idle')
    def read(self, sensorId):
        """Read sensorId value
        """
        return NotImplemented

    def check_status(self):
        """ Check status.
        """
        pass

    def OnLoad(self):
        pass



