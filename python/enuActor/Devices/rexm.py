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
        self.home = None
        self.medium = None
        self.low = None


    @transition('init', 'idle')
    def initialise(self):
        """Initialise Rexm.

        .. note:: Should be improved after getting hardware status

        """
        self.OnLoad()
        self.goHome()
        self.check_status()

    def goHome(self):
        #TODO : add routine go home
        self.curSimPos = self.home

    def getHome(self):
        """ get home position.

        :returns: x position of encoder
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        return self.home

    def setHome(self, X=None):
        """setHome.
        setHome to posCoord or to current if posCoord is None

        :param X: X encoder value or nothing if current
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        if X is None:
            #if None then X=CURRENT
            home = self.getHome()
        self.home = home

    @transition('busy', 'idle')
    def moveTo(self, x=None):
        """MoveTo.
        Move to x or to home if x is None

        :param posCoord: x or nothing if home
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        if x is None:
            x = self.home
        self.currSimPos = x

    @transition('busy', 'idle')
    def switch(self, resolution):
        """Switch between low and medium resolution
        """
        if resolution.lower() == 'medium':
            self.currSimPos = self.medium
            # TODO: add routine to put medium
        elif resolution.lower() == 'low':
            self.currSimPos = self.low
            # TODO: add routine to put low
        else:
            raise Exception("Wrong format : %s" % resolution)

    def OnLoad(self):
        self.home = self._param['home']
        self.medium = self._param['medium']
        self.low = self._param['low']

    def check_status(self):
        """ Check status.
        """
        pass

