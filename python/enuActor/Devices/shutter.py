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


class Shutters(DualModeDevice):

    """SW device: Shutter

    Instance attributes:

        * currPos : current position of the shutter.

    Class attributes:

        * positions : set of position.
        * STATUS_BYTE_N : set of string value return by byte N.
        * MASK_ERROR_SB_N : mask error related to SB N
    """

    # Status returned from arduino ethernet
    positions = ['Shutter blue error',
                'Shutter blue initialised',
                'Shutter blue opened',
                'Shutter blue closed',
                'Shutter red error',
                'Shutter red initialised',
                'Shutter red opened',
                'Shutter red closed']

    # Shutter open/close/init = BLUE + RED opened/closed/init converted to decimal
    STATUS_OPEN = int(0b00100010)
    STATUS_CLOSE = int(0b00010001)
    STATUS_INIT = int(0b01000100)
    STATUS_ERROR_R = int(0b00001000)
    STATUS_ERROR_B = int(0b10000000)

    # Dict of position
    STATUS_POSITION = {
        STATUS_OPEN : 'open',
        STATUS_CLOSE: 'close',
        STATUS_ERROR_R: 'undef.',
        STATUS_ERROR_B: 'undef.',
        STATUS_INIT: 'undef.'
    }

    shutter_id = ["red", "blue", "all"]

    ################
    #  RS232 BYTE  #
    ################
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
        super(Shutters, self).__init__(actor)
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
        # wait 0.2s after check_status (during handleTimeout) sending message
        # not necesary just safer
        time.sleep(0.2)

        self.currSimPos = transition
        self.inform("sending %s..." % transition)
        try:
            if transition == 'open':
                ret = self.send('open_sh\r\n')
                ret = ret.split('\r')[0].split('\n')[0]
                if ret == 'nok':
                    self.warn('open_sh command sent => Command is not ok')
                elif ret == 'intlck':
                    self.warn('interlock from hardware - Didier (┛ò__ó)┛')
                elif ret != 'ok':
                    self.error('wrong value returned :%s' % ret)
                self.currSimPos = 'open'
            elif transition == 'openred':
                ret = self.send('open_rsh\r\n')
                ret = ret.split('\r')[0].split('\n')[0]
                if ret == 'nok':
                    self.warn('open_rsh command sent => Command is not ok')
                elif ret == 'intlck':
                    self.warn('interlock from hardware - Didier (┛ò__ó)┛')
                elif ret != 'ok':
                    self.error('wrong value returned :%s' % ret)
            elif transition == 'openblue':
                ret = self.send('open_bsh\r\n')
                ret = ret.split('\r')[0].split('\n')[0]
                if ret == 'nok':
                    self.warn('open_bsh command sent => Command is not ok')
                elif ret == 'intlck':
                    self.warn('interlock from hardware - Didier (┛ò__ó)┛')
                elif ret != 'ok':
                    self.error('wrong value returned :%s' % ret)
            elif transition == 'close':
                ret = self.send('close_sh\r\n')
                ret = ret.split('\r')[0].split('\n')[0]
                if ret == 'nok':
                    self.warn('close_sh command sent => Command is not ok')
                elif ret == 'intlck':
                    self.warn('interlock from hardware - Didier (┛ò__ó)┛')
                elif ret != 'ok':
                    self.error('wrong value returned :%s' % ret)
                self.currSimPos = 'close'
            elif transition == 'closered':
                ret = self.send('close_rsh\r\n')
                ret = ret.split('\r')[0].split('\n')[0]
                if ret == 'nok':
                    self.warn('open_rsh command sent => Command is not ok')
                elif ret == 'intlck':
                    self.warn('interlock from hardware - Didier (┛ò__ó)┛')
                elif ret != 'ok':
                    self.error('wrong value returned :%s' % ret)
            elif transition == 'closelue':
                ret = self.send('close_bsh\r\n')
                ret = ret.split('\r')[0].split('\n')[0]
                if ret == 'nok':
                    self.warn('close_bsh command sent => Command is not ok')
                elif ret == 'intlck':
                    self.warn('interlock from hardware - Didier (┛ò__ó)┛')
                elif ret != 'ok':
                    self.error('wrong value returned :%s' % ret)
            elif transition == 'reset':
                self.send('reboot\r\n')
            self.check_status()
        except Error.DeviceErr, e:
            self.currSimPos = 'undef.'
            raise e
        except Error.CommErr, e:
            self.currSimPos = 'undef.'
            raise e
        self.finish("operation done sucessfully!")

    @interlock
    @transition('init', 'idle')
    def initialise(self):
        """ Initialise shutter.
        Here just trigger the FSM to INITIALISING and IDLE

        """
        self.OnLoad()
        self.inform("initialising...")
        self.check_status()
        self.currSimPos = self.home
        self.send('init_sh\r\n')
        self.check_position()
        self.finish("initialisation done!")

    def terminal(self):
        """launch terminal connection to shutter device

        """
        return NotImplementedError

    def OnLoad(self):
        self.home = self._param['home']

    def check_status_RS232(self):
        """Check status byte 1, 3, 4, 5 and 6 from Shutter controller\
            and return current list of status byte.

        :returns: [sb1, sb3, sb5, sb6] with sbi\
         list of byte from status byte
        :raises: :class:`~.Error.CommErr`

        """
        l_sb = [1, 3, 5, 4, 6]
        mask = [None] * 6
        for sb in l_sb:
            time.sleep(0.3)
            mask[sb - 1] = self.parseStatusByte(sb)
            if self.started:
                if sum(mask[sb -1] * np.asarray(getattr(Shutter,
                    'MASK_ERROR_SB_%i' % sb))) > 0:
                    error = ', '.join(np.array(getattr(Shutter,\
    'STATUS_BYTE_%i' % sb))[mask[sb - 1] == 1])
                    self.fail("%s" % error)
                elif self.fsm.current in ['INITIALISING', 'BUSY']:
                    self.fsm.idle()
                elif self.fsm.current == 'none':
                    self.fsm.load()
        self.generate(self.currPos)
        return mask

    def check_status(self):
        """Check status byte

        :raises: :class:`~.Error.CommErr`

        """
        ret = None
        try:
            ret = self.send('status_sh\r\n')
        except Exception, e:
            self.fsm.fail()
            self.error("%s" % e)
            return

        # We have to remove all \r and \n
        ret = ret.split('\r')[0].split('\n')[0]
        if ret in ['nok', '']:
            if self.debug:
                self.diag('status_sh received a nok or \'\' ')
            return

        ret = np.asarray([int(val) for val in ret[0:8]])
        if ret in [Shutter.STATUS_ERROR_B, Shutter.STATUS_ERROR_R]:
            self.fail("%s" % ret)
        elif self.fsm.current in ['BUSY']:
            self.fsm.idle()
        elif self.fsm.current == 'none':
            self.fsm.load()

        #check position in check status because smae command
        self.currPos = Shutter.STATUS_POSITION[ret]
        self.generate(self.currPos)

    def check_position(self):
        """Check position from Shutter controller

        :raises: :class:`~.Error.DeviceErr`

        """
        pass

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

