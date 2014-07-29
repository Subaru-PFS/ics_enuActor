#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                 Back-Illumination SW device module                  #
#######################################################################
try:
    from enuActor.QThread import *
    from Device import *
except ImportError:
    pass
import serial, time
import Error
import numpy as np
import re


class Bia(DualModeDevice):

    """SW device: BIA

       Attributes:
        * currPos : current position of the BIA
    """

    positions = ['on', 'off', 'strobe']

    def __init__(self, actor=None):
        super(Bia, self).__init__(actor)
        self.currPos = "off"

    ############################
    #  About Device functions  #
    ############################

    @transition('init', 'idle')
    def initialise(self):
        """Initialise Bia.

        .. note:: Should be improved after getting hardware status

        """
        #TODO: to improve
        self.load_cfg(self.device)
        self.check_status()
        self.check_position()

    def setConfig(self, freq=None, dur=None, intensity=None):
        """It specifies parameters for light and strobe mode.

        .. note:: Default parameters are located in\
                *cfg/devices_parameters.cfg* file. This function only\
                change default parameters of session.

        .. todo:: Check values and types

        :param freq: frequency of strobe mode in *Hz*
        :param dur: duration of strobe mode in :math:`\mu{}s`
        :param intensity: intensity of light

        """
        #TODO: check values and types
        self._param["frequency"] = freq
        self._param["duration"] = dur
        self._param["intensity"] = intensity

    @interlock
    @transition('busy', 'idle')
    def bia(self, transition, strobe=None):
        """Operation on/off bia

        .. todo:: code to be changed when ne input received

        :param transition: ``'on'`` or ``'off'``
        :type transition: str.
        :param strobe: [int or float, int or float]
        :type strobe: list
        :returns: 0 if OK
        :raises: :class:`~.Error.CommErr`, :class:`~.Error.DeviceErr`

        """
        self.currSimPos = transition
        try:
            if transition == 'on':
                self.send('a\r\n')
                time.sleep(.5)
                self.send('p10\r\n')
                time.sleep(.5)
                self.send('d1000\r\n')
                self.currPos = "on" # TODO: To be change when got input
            elif transition == 'strobe':
                self.send('a\r\n')
                time.sleep(.5)
                if strobe is None:
                    # Use default parameters
                    strobe = [
                            self._param["frequency"],
                            self._param["duration"]
                            ]
                self.send('p%i\r\n' % int(strobe[0]))
                time.sleep(5)
                self.send('d%i\r\n' % int(strobe[1]))
                self.currPos = "strobe" # TODO: To be change when got input
            elif transition == 'off':
                self.send('c\r\n')
                self.currPos = "off" # TODO: To be change when got input
        except socket.error as e:
            raise Error.CommErr(e)
        self.check_status()

    def OnLoad(self):
        self.check_status()

    def check_status(self):
        """ Check status.

        .. warning: Can not check status yet (waiting for input)
        """
        # TODO: to be changed whn input received
        # Same as sim_check_status
        pass

    def check_position(self):
        """ Check position.

        .. warning: Can not check postion yet (waiting for input)
        """
        if self.currSimPos is not None:
            self.currPos = self.currSimPos



