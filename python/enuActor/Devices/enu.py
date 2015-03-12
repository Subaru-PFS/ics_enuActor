#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                      ENU SW abstract module                         #
#######################################################################

from enuActor.QThread import *
from Device import *
import Error
import ConfigParser
import os

here = os.path.dirname(os.path.realpath(__file__))
path = here + '/cfg/'

class Enu(DualModeDevice):

    """Docstring for Enu. """

    def __init__(self, actor=None):
        """@todo: to be defined1. """
        super(Enu, self).__init__(actor)
        self.currPos = None

    def startUp(self):
        """Abstract start
        :returns: @todo
        :raises: @todo

        """
        #ENU is always in operation MODE as it is an abstract device
        self.change_mode('operation')
        self.OnLoad()

    def saveConfig(self, dir=None):
        """Save ENUs parameter into config file

        :param dir: @todo
        :returns: @todo
        :raises: @todo

        """
        def rmBracket(stringList):
            return str(stringList).replace('[', '').replace(']', '')

        if self.actor.bia.deviceStarted == 0 or\
                self.actor.slit.deviceStarted == 0 or\
                self.actor.enu.deviceStarted == 0 or\
                self.actor.rexm.deviceStarted == 0:
            self.warn("Some device are not started. Config file not complete.")
        config = ConfigParser.RawConfigParser()
        config.add_section('ENU')
        config.set('ENU', 'shutters', self.actor.shutter.mode)
        config.set('ENU', 'bia', self.actor.bia.mode)
        config.set('ENU', 'slit', self.actor.slit.mode)
        config.set('ENU', 'temperature', self.actor.temperature.mode)
        config.set('ENU', 'rexm', self.actor.temperature.mode)
        config.add_section('BIA')
        config.set('BIA', 'home', self.actor.bia.home)
        config.set('BIA', 'period', self.actor.bia.dimmer_period)
        config.set('BIA', 'duty', self.actor.bia.dimmer_duty)
        config.set('BIA', 'strobe_period', self.actor.bia.strobe_period)
        config.set('BIA', 'strobe_duty', self.actor.bia.strobe_duty)
        config.set('BIA', 'intensity_thres', self.actor.bia.intensity_thresh)
        config.add_section('SHUTTERS')
        config.set('SHUTTERS', 'home', self.actor.shutter.home)
        config.add_section('SLIT')
        config.set('SLIT', 'home', rmBracket(self.actor.slit._homeHexa))
        config.set('SLIT', 'slit_position', rmBracket(self.actor.slit._slit_position))
        config.set('SLIT', 'dither_axis', rmBracket(self.actor.slit.dither_axis))
        config.set('SLIT', 'focus_axis', rmBracket(self.actor.slit.focus_axis))
        config.set('SLIT', 'magnification', self.actor.slit.magnification)
        config.set('SLIT', 'focus_value', self.actor.slit.focus_value)
        config.set('SLIT', 'dithering_value', self.actor.slit.dithering_value)
        config.add_section('REXM')
        config.set('REXM', 'home', self.actor.rexm.home)
        config.set('REXM', 'medium', self.actor.rexm.medium)
        config.set('REXM', 'low', self.actor.rexm.low)
        config.add_section('TEMPERATURE')


        import time
        dir = '%sMyParam_%s.cfg' % (path, time.ctime())
        with open(dir, 'wb') as configfile:
            config.write(configfile)
        return dir

    @transition('init', 'idle')
    def initialise(self):
        """ Perform a sequence of action for all device"""
        def nameOf(device):
            return device.deviceName.lower()

        self.actor.bcast.inform("text='Start sequence init ENU'")
        self.actor.bia.change_mode(
            self._param[nameOf(self.actor.bia)])
        self.actor.bia.initialise()
        self.actor.bia.putMsg(self.actor.bia.bia, 'off')
        self.actor.shutter.change_mode(
            self._param[nameOf(self.actor.shutter)])
        self.actor.shutter.initialise()
        self.actor.shutter.putMsg(self.actor.shutter.shutter, 'close')
        self.actor.slit.change_mode(
            self._param[nameOf(self.actor.slit)])
        self.actor.slit.initialise()
        self.actor.rexm.change_mode(
            self._param[nameOf(self.actor.rexm)])
        self.actor.rexm.initialise()
        self.actor.temperature.change_mode(
            self._param[nameOf(self.actor.temperature)])
        self.actor.temperature.initialise()
        self.check_status()

    def check_status(self):
        """ Check state of each device and take worst state as is current state"""
        # If no device is started dont check
        try:
            condition = self.actor.bia.deviceStarted == False or\
                self.actor.shutter.deviceStarted == False or\
                self.actor.slit.deviceStarted == False
        except Error.DeviceErr:
            if e.code == 1000:
                self.warn("check status before started")
                return
            else:
                self.error('%s' % e.reason)

        if condition:
            return

        # Checkng state of each device
        if self.actor.bia.fsm.current == 'IDLE' and\
                self.actor.shutter.fsm.current == 'IDLE' and\
                self.actor.slit.fsm.current == 'IDLE' and\
                self.fsm.current != 'IDLE':
            if self.fsm.current == 'LOADED':
                self.fsm.init()
            #if all device IDLE goto ENU IDLE
            self.fsm.idle()
        elif 'LOADED' in [self.actor.bia.fsm.current,
                          self.actor.shutter.fsm.current,
                          self.actor.slit.fsm.current]\
            and self.fsm.current != 'LOADED':
            #if 1 Device LOADED goto ENU LOADED
            self.fsm.load()
        elif 'FAILED' in [self.actor.bia.fsm.current,
                          self.actor.shutter.fsm.current,
                          self.actor.slit.fsm.current]\
            and self.fsm.current not in ['FAILED', 'LOADED']:
            #if 1 Device FAILED and NO Device LOADED goto ENU FAILED
            self.fsm.fail()
        elif 'BUSY' in [self.actor.bia.fsm.current,
                          self.actor.shutter.fsm.current,
                          self.actor.slit.fsm.current]\
            and self.fsm.current != 'BUSY':
            self.fsm.busy()


    def check_position(self):
        pass

    def OnLoad(self):
        """ Load all param of all device"""
        pass
