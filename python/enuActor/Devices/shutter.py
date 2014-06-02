#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                      Shutter SW device module                       #
#######################################################################

from enuActor.QThread import *
import serial, time
import Error
from Device import *
import numpy as np
import re


class Shutter(DualModeDevice):

    """SW device: Shutter

       Attributes:
        * currPos : current position of the shutter
    """

    positions = ['undef.', 'open', 'closed(A)', 'closed(B)']
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
        Device.__init__(self, actor)
        self.currPos = "open"     #current position
        self.shutter_id = None      #current id

    @interlock("open", "on", "bia")
    @transition('busy', 'idle')
    def shutter(self, transition):
        """Operation open/close shutter red or blue

        :param transition: *str* ``'open'`` or ``'close'``
        :type transition: str.
        :returns: 0 if OK
        :raises: :class:`~.Error.CommErr`, :class:`~.Error.DeviceErr`

        """
        if self.mode == "simulated":
            self.currPos = "open" if transition == 'open'\
                else 'closed'
            self.fsm.idle()
        else: #if mode operation
            try:
                if transition == 'open':
                    self.send('os\r\n')
                elif transition == 'close':
                    self.send('cs\r\n')
                elif transition == 'reset':
                    self.send('rs\r\n')
            except Error.DeviceErr, e:
                print e
                #raise e
            except Error.CommErr, e:
                print e
        return 0

    #@transition('init', 'idle')
    def initialise(self):
        """ Initialise shutter.
        Here just trigger the FSM to INITIALISING and IDLE
        :returns: @todo
        :raises: @todo

        """
        self.load_cfg(self.device)
        self.handleTimeout()
        if self.mode == 'operation':
            self.check_status()


    def terminal(self):
        """launch terminal connection to shutter device

        :returns: @todo

        """
        return NotImplementedError

    def handleTimeout(self):
        """Override method :meth:`.QThread.handleTimeout`.
        Process while device is idling.

        :returns: @todo
        :raises: :class:`~.Error.CommErr`

        """
        if self.mode is "operation" and self.started:
            self.check_status()
        elif self.started:
            self.status = self.currPos
            if self.fsm.current in ['INITIALISING', 'BUSY']:
                self.fsm.idle()
            elif self.fsm.current == 'none':
                self.fsm.load()

    def check_status(self):
        """Check status byte 1, 3, 4, 5 and 6 from Shutter controller\
            and return current list of status byte.

        :returns: [sb1, sb3, sb5, sb6] with sbi\
         list of byte from status byte
        :raises: :class:`~.Error.CommErr`

        """
        l_sb = [1, 3, 5, 4, 6]
        mask = [None] * 6
        status = ''
        try:
            self.ss = int(self.send('ss\r\n')[0])
            self.currPos = Shutter.positions[self.ss]
            status += self.currPos
            for sb in l_sb:
                time.sleep(0.3)
                mask[sb - 1] = self.parseStatusByte(sb)
                #status += ', '.join(np.array(getattr(Shutter,
                    #'STATUS_BYTE_%i' % sb))[mask[sb - 1] == 1])
                if sum(mask[sb -1] * np.asarray(getattr(Shutter,
                    'MASK_ERROR_SB_%i' % sb))) > 0:
                    print "warn ='%s'" %\
                      ', '.join(np.array(getattr(Shutter,
                    'STATUS_BYTE_%i' % sb))[mask[sb - 1] == 1])
                    self.fsm.fail()
                elif self.fsm.current in ['INITIALISING', 'BUSY']:
                    self.fsm.idle()
                elif self.fsm.current == 'none':
                    self.fsm.load()
            self.status = status
            return mask
        except Error.CommErr, e:
            print e


    def parseStatusByte(self, sb):
        """Send status byte command and parse reply of device

        :param sb: byte 1, 3, 4, 5 or 6
        :returns: array_like defining status flag
        :raises: :class:`~.Error.CommErr`

        """
        ret = self.send('sb %i\r\n' % sb)
        ret = re.split(r"[~\r\n ]+", ret)

        #compare binary and decimal value
        try:
            if int(format(int(ret[0]), 'b')) != int(ret[1]):
                raise Error.CommErr("Control bit error (bit lost or whatever)")
        except ValueError, e:
            raise Error.CommErr("Error bad type return from serial")

        #return status byte 1
        mask = map(int, list(ret[1]))
        mask.reverse()
        arr_mask = np.array(mask[0: len(getattr(Shutter, 'STATUS_BYTE_%i' % sb))])
        return arr_mask


