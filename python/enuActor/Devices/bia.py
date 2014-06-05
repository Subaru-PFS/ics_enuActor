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

    def __init__(self, actor=None):
        super(Bia, self).__init__(actor)
        self.currPos = "off"

    ############################
    #  About Device functions  #
    ############################

    def initialise(self):
        """Initialise Bia :
         * Load *cfg/device_parameters.cfg* file
         * ...todo
        :returns: @todo
        :raises: @todo

        """
        #TODO: to improve
        self.load_cfg(self.device)
        self.check_status()

    def setConfig(self, freq=None, dur=None, intensity=None):
        """It specifies parameters for light and strobe mode.

        .. note:: Default parameters are located in\
                *cfg/devices_parameters.cfg* file. This function only\
                change default parameters of session.

        .. todo:: Check values and types

        :param freq: frequency of strobe mode in *Hz*
        :param dur: duration of strobe mode in :math:`mu`s
        :param intensity: intensity of light
        :returns: @todo
        :raises: @todo

        """
        #TODO: check values and types
        self._param["frequency"] = freq
        self._param["duration"] = dur
        self._param["intensity"] = intensity

    @interlock(["on", "strobe"], "open", "shutter")
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
        self.lastActionCmd = transition
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

    def op_check_status(self):
        """ *Can not check status yet*  """
        # TODO: to be changed whan input received
        # Same as sim_check_status
        if self.lastActionCmd is not None:
            self.currPos = self.lastActionCmd


