#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                 Back-Illumination SW device module                  #
#######################################################################
from enuActor.QThread import *
from Device import *
from interlock import interlock
import serial, time
import Error
import numpy as np
import re


class Bia(DualModeDevice):

    """SW device: BIA

       Instance attributes:

            * currPos : current position of the BIA

       Class attributes:

           * positions : set of possible positions
    """

    positions = ['on', 'off', 'strobe']

    def __init__(self, actor=None):
        super(Bia, self).__init__(actor)
        self.currPos = None
        self.home = None
        self.strobe_duty = None
        self.strobe_period = None
        self.dimmer_duty = None
        self.dimmer_period = None
        self.intensity_thresh = None

    ############################
    #  About Device functions  #
    ############################

    @interlock
    @transition('init', 'idle')
    def initialise(self):
        """Initialise Bia.

        .. note:: Should be improved after getting hardware status

        """
        self.OnLoad()
        self.inform("initialising...")
        self.currSimPos = self.home
        self.send('set_bia_thresh%s\r\n' % self.intensity_thresh)
        self.check_status()
        self.check_position()
        self.finish("initialisation done!")

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
        self._param["duty"] = freq
        self._param["period"] = dur

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
        self.inform("sending...")
        try:
            if transition == 'on':
                self.send('cia_on\r\n')
                time.sleep(.5)
                self.send('set_bia_period%s\r\n' % self.dimmer_period)
                time.sleep(.5)
                self.send('set_bia_duty%s\r\n' % self.dimmer_duty)
                self.currSimPos = "on" # TODO: To be change when got input
            elif transition == 'strobe':
                self.send('a\r\n')
                time.sleep(.5)
                if strobe is None:
                    # Use default parameters
                    strobe = [
                            self.strobe_period,
                            self.strobe_duty
                            ]
                self.send('set_bia_speriod%i\r\n' % int(strobe[0]))
                time.sleep(5)
                self.send('set_bia_sduty%i\r\n' % int(strobe[1]))
                self.currSimPos = "strobe" # TODO: To be change when got input
            elif transition == 'off':
                self.send('bia_off\r\n')
                self.currSimPos = "off" # TODO: To be change when got input
        except socket.error as e:
            self.curSimPos = 'undef.'
            raise Error.CommErr(e)
        self.generate(self.currPos)
        self.inform("check the status and position...")
        self.check_status()
        self.check_position()
        self.finish("job done my friend!")

    def OnLoad(self):
        self.home = self._param['home']
        self.strobe_period = self._param['strobe_period']
        self.strobe_duty = self._param['strobe_duty']
        self.dimmer_period = self._param['period']
        self.dimmer_duty = self._param['duty']
        self.intensity_thresh = self._param['intensity_thres']

    def check_status(self):
        """ Check status.

        .. warning: Can not check status yet (waiting for input)
        """

        status = self.send('ctrlstat\r\n')
        # We have to remove all \r and \n
        status = status.split('\r')[0].split('\n')[0]
        if status == 'nok':
            if self.debug:
                #To much talkative
                self.diag("sent ctrlstat and received nok.")
        elif status == '':
            # weird case scenario wait for next check²
            return
        elif status not in ['0', '1', '2']:
            self.warn("ctrlstat returned: '%s'" % status )
        elif int(status) == 1 and self.currPos == 'on':
            self.error("Interlock hardware! - Didier : (┛ò__ó)┛")

    def check_position(self):
        """ Check position.

        .. warning: Can not check postion yet (waiting for input).
        So here Position simulated is same as real Position
        """
        OnOrOff = self.send('get_bia_status\r\n')
        # We have to remove all \r and \n
        OnOrOff = OnOrOff.split('\r')[0].split('\n')[0]
        if OnOrOff == 'nok':
            if self.debug:
                #To much talkative
                self.diag("sent get_bia_status and received nok.")
        elif OnOrOff == '':
            # weird case scenario wait for next check²
            return
        if OnOrOff == 1:
            self.currPos = "on"
        elif OnOrOff == 0:
            self.currPos = "off"
        else:
            self.currPos = "undef."
        if self.currSimPos is not None:
            self.currPos = self.currSimPos
        self.generate(self.currPos)



