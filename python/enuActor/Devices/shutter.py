#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                      Shutter SW device module                       #
#######################################################################

from enuActor.QThread import *
from interlock import interlock
import serial, time
import Error
from Device import *
import numpy as np
import re


class Shutter(DualModeDevice):

    """SW device: Shutter

    Instance attributes:

        * currPos : current position of the shutter.

    Class attributes:

        * positions : set of position.
        * STATUS_BYTE_N : set of string value return by byte N.
        * MASK_ERROR_SB_N : mask error related to SB N
    """

    positions = {
        'shop' : 'open',
        'shcl' : 'closed',
        'sherr': 'undef.',
        'shmov': 'undef.'
    }
    shutter_id = ["red", "blue", "all"]

    STATUS_BYTE_1 = ['S_blade_A_offline', 'S_blade_B_offline', ''
                    'S_CAN_comm_error', 'S_error_interlock']
    STATUS_BYTE_3 = ['S_motor_to_origin_timeout', 'S_threshold_error', '',
                       'S_limit_switch', 'S_unknown_command', 'S_collision',
                       'S_EEPROM_RW_error']
    STATUS_BYTE_4 = ['S_blade_open', 'S_blade_closed', 'S_error_LED',
                       'S_error_interlock']
    STATUS_BYTE_5 = STATUS_BYTE_3
    STATUS_BYTE_6 = STATUS_BYTE_4

    # Mask whose status byte is an error
    MASK_ERROR_SB_1 = [0, 0, 1, 1]
    MASK_ERROR_SB_3 = [1] * 7
    MASK_ERROR_SB_4 = [0, 0, 1, 1]
    MASK_ERROR_SB_5 = MASK_ERROR_SB_3
    MASK_ERROR_SB_6 = MASK_ERROR_SB_4


    def __init__(self, actor=None):
        """Inherit QThread and start the Thread (with FSM)"""
        super(Shutter, self).__init__(actor)
        self.home = None
        self.currPos = None     #current position
        self.shutter_id = None      #current id

    @interlock
    @transition('busy', 'idle')
    def shutter(self, transition):
        """Operation open/close shutter red or blue

        :param transition: *str* ``'open'`` or ``'close'``
        :type transition: str.
        :returns: 0 if OK
        :raises: :class:`~.Error.CommErr`, :class:`~.Error.DeviceErr`

        """
        self.currSimPos = transition
        try:
            if transition == 'open':
                self.send('open_sh\r\n')
                self.currSimPos = 'open'
            elif transition == 'close':
                self.send('close_sh\r\n')
                self.currSimPos = 'close'
            elif transition == 'reset':
                self.send('rs\r\n')
            self.check_status()
        except Error.DeviceErr, e:
            self.currSimPos = 'undef.'
            raise e
        except Error.CommErr, e:
            self.currSimPos = 'undef.'
            raise e

    @interlock
    @transition('init', 'idle')
    def initialise(self):
        """ Initialise shutter.
        Here just trigger the FSM to INITIALISING and IDLE

        """
        self.OnLoad()
        self.check_status()
        self.currSimPos = self.home
        self.send('init_sh\r\n')
        self.check_position()

    def terminal(self):
        """launch terminal connection to shutter device

        """
        return NotImplementedError

    def OnLoad(self):
        self.home = self._param['home']

     #def check_status(self):
        #"""Check status byte 1, 3, 4, 5 and 6 from Shutter controller\
            #and return current list of status byte.

        #:returns: [sb1, sb3, sb5, sb6] with sbi\
         #list of byte from status byte
        #:raises: :class:`~.Error.CommErr`

        #"""
        #l_sb = [1, 3, 5, 4, 6]
        #mask = [None] * 6
        #for sb in l_sb:
            #time.sleep(0.3)
            #mask[sb - 1] = self.parseStatusByte(sb)
            #if self.started:
                #if sum(mask[sb -1] * np.asarray(getattr(Shutter,
                    #'MASK_ERROR_SB_%i' % sb))) > 0:
                    #error = ', '.join(np.array(getattr(Shutter,\
    #'STATUS_BYTE_%i' % sb))[mask[sb - 1] == 1])
                    #self.fail("%s" % error)
                #elif self.fsm.current in ['INITIALISING', 'BUSY']:
                    #self.fsm.idle()
                #elif self.fsm.current == 'none':
                    #self.fsm.load()
        #self.generate(self.currPos)
        #return mask

    def check_status(self):
        """Check status byte 1, 3, 4, 5 and 6 from Shutter controller\
            and return current list of status byte.

        :returns: [sb1, sb3, sb5, sb6] with sbi\
            list of byte from status byte
        :raises: :class:`~.Error.CommErr`

        """
        if self.started:
            ss = self.send('status_sh')
            if ss == 'sherr':
                self.fail("%s" % error)
            elif self.fsm.current in ['INITIALISING', 'BUSY']:
                if ss != 'shmov':
                    self.fsm.idle()
            elif self.fsm.current == 'none':
                self.fsm.load()
        self.generate(self.currPos)

    def check_position(self):
        """Check position from Shutter controller

        :raises: :class:`~.Error.DeviceErr`

        """
        try:
            ss = self.send('status_sh\r\n')
            self.currPos = Shutter.positions[ss]
            self.generate(self.currPos)
        except Error.CommErr as e:
            if self.started:
                self.fail("%s" % e)
            raise e
        if self.currPos == None:
            raise Error.DeviceErr("Position undef.")


    def parseStatusByte(self, sb):
        """Send status byte command and parse reply of device

        :param sb: byte 1, 3, 4, 5 or 6
        :returns: array_like defining status flag
        :raises: :class:`~.Error.CommErr`

        """
        ret = self.send('sb %i\r\n' % sb)
        ret = re.split(r"[~\r\n ]+", ret)

        #compare binary and decimal value
        #try:
            #if int(format(int(ret[0]), 'b')) != int(ret[1]):
                #raise Error.CommErr("sb %s : Control bit error (bit lost)" % sb)
        #except ValueError, e:
            #raise Error.CommErr("sb %s :Error bad type return from serial\
#: [%s, %s]" % (sb, ret[0], ret[1]))
        #return status byte 1
        mask = map(int, list(ret[1]))
        mask.reverse()
        arr_mask = np.array(mask[0: len(getattr(Shutter, 'STATUS_BYTE_%i' % sb))])
        return arr_mask
