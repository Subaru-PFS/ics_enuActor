#!/usr/bin/env python
# encoding: utf-8
"""
File:
Author: Thomas Pegot-Ogier
Email: thomas.pegot@lam.fr
Github: gitolite@pfs.ipmu.jp:enuActor
Description:
"""
#######################################################################
#                        REXM SW Device Module                        #
#######################################################################

# Import from module or from anywhere
from enuActor.QThread import *
import serial, time
import Error
from Device import *


class Rexm(Device):

    """SW Device: Red EXchange Mechanism"""

    def __init__(self, actor=None):
        """@todo: to be defined1.
        """
        Device.__init__(self, actor)
        self.ToolCoordinates = [None] * 6   # Tool Coordinate system
        self.WorksCoordinates = [None] * 6   # Work Coordinate system
        self.BaseCoordinates = [None] * 6   # Base Coordinate system
        self.status = None

    def move(self, coord):
        """Position defined in Cartesian coordinates with Bryant angles
        * move to (translate) X, Y, Z
        * Make a clockwise rotation around Z-axis
        * Make a clockwise rotation around Y-axis
        * Make a clockwise rotation around X-axis

        :param coord: @todo
        :returns: @todo
        :raises: @todo

        """
        pass

    def initialise(self):
        """Initialise REXM
        :returns: @todo
        :raises: @todo

        """
        print "in REXM"

    def getStatus(self):
        """return status of shutter (FSM)

        :returns: ``'LOADED'``, ``'IDLE'``, ``'BUSY'``, ...
        """
        return "state: %s, status: %s" % (self.fsm.current, self.status)

    def check_status(self):
        pass

    def handleTimeout(self):
        """Override method :meth:`.QThread.handleTimeout`.
        Process while device is idling.

        :returns: @todo
        :raises: :class:`~.Error.CommErr`

        """
        if self.started:
            if self.fsm.current in ['INITIALISING', 'BUSY']:
                self.fsm.idle()
            elif self.fsm.current == 'none':
                self.fsm.load()

