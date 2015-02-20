#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                      ENU SW abstract module                         #
#######################################################################

from enuActor.QThread import *
from Device import *
import Error


class Enu(DualModeDevice):

    """Docstring for Enu. """

    def __init__(self, actor=None):
        """@todo: to be defined1. """
        super(Enu, self).__init__(actor)
        self.currPos = None
        self.d_devMode ={
            'bia' : None,
            'shutter' : None,
            'slit' : None
        }

    def startUp(self):
        """Abstract start
        :returns: @todo
        :raises: @todo

        """
        #ENU is always in operation MODE as it is an abstract device
        self.change_mode('operation')


    @transition('init', 'idle')
    def initialise(self):
        """ Perform a sequence of action for all device"""
        self.OnLoad()
        self.actor.bcast.inform("text='Start sequence init ENU'")
        self.actor.bia.change_mode(self.d_devMode['bia'])
        self.actor.bia.initialise()
        self.actor.bia.putMsg(self.actor.bia.bia, 'off')
        self.actor.shutter.change_mode(self.d_devMode['shutter'])
        self.actor.shutter.initialise()
        self.actor.shutter.putMsg(self.actor.shutter.shutter, 'close')
        self.actor.slit.change_mode(self.d_devMode['slit'])
        self.actor.slit.initialise()
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
        for devName in self._param.keys():
            self.d_devMode[devName] = self._param[devName]
