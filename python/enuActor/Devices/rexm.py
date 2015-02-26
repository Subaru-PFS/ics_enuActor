#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                    Rexm SW device module                     #
#######################################################################
from enuActor.QThread import *
from Device import *


class Rexm(DualModeDevice):

    """SW device: Rexm

    """

    def __init__(self, actor=None):
        super(Rexm, self).__init__(actor)
        self.currPos = None
        self._home = None


    @transition('init', 'idle')
    def initialise(self):
        """Initialise Rexm.

        .. note:: Should be improved after getting hardware status

        """
        self.check_status()

    def goHome(self):
        return NotImplemented

    def getHome(self):
        """ get home position.

        :returns: x position of encoder
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        raise NotImplementedError

    def setHome(self, X=None):
        """setHome.
        setHome to posCoord or to current if posCoord is None

        :param X: X encoder value or nothing if current
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        if X is None:
            #if None then X=CURRENT
            curHome = self._getHome()
        return NotImplemented

    @transition('busy', 'idle')
    def moveTo(self, x=None):
        """MoveTo.
        Move to x or to home if x is None

        :param posCoord: x or nothing if home
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        if x is None:
            x = self._home
        return NotImplemented

    @transition('busy', 'idle')
    def switch(self, resolution):
        """Switch between low and medium resolution
        """
        self.resolution = resolution

    def check_status(self):
        """ Check status.
        """
        pass




