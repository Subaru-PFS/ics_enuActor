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


class Bia(Device):

    """SW device: BIA

    """

    def __init__(self, actor=None):
        Device.__init__(self, actor)
        self.currPos = None
        self.status = None

    def initialise(self):
        """Initialise Bia
        :returns: @todo
        :raises: @todo

        """
        self.handleTimeout()
        #TODO: to improve

    @transition('busy', 'idle')
    def bia(self, transition, strobe=None):
        """Operation on/off bia

        :param transition: ``'on'`` or ``'off'``
        :type transition: str.
        :param strobe: [int or float, int or float]
        :type strobe: list
        :returns: 0 if OK
        :raises: :class:`~.Error.CommErr`, :class:`~.Error.DeviceErr`


        """
        if self.mode == "simulated":
            self.currPos = "on" if transition == 'on'\
                    else 'off'
        else:
            try:
                if transition == 'on':
                    self.send('a\r\n')
                    time.sleep(.5)
                    self.send('p10\r\n')
                    time.sleep(.5)
                    self.send('d1000\r\n')
                elif transition == 'strobe':
                    self.send('a\r\n')
                    time.sleep(.5)
                    self.send('p%i\r\n' % strobe[0])
                    time.sleep(.5)
                    self.send('d%i\r\n' % strobe[1])
                elif transition == 'off':
                    self.send('c\r\n')
            except socket.error as e:
                raise Error.CommErr(e)
        return 0

    def getStatus(self):
        """return status of shutter (FSM)

        :returns: ``'LOADED'``, ``'IDLE'``, ``'BUSY'``, ...
        """
        return "state: %s, status: %s" % (self.fsm.current, self.status)

    def handleTimeout(self):
        """Override method :meth:`.QThread.handleTimeout`.
        Process while device is idling.

        :returns: @todo
        :raises: :class:`~.Error.CommErr`

        """
        if self.started:
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
            for sb in l_sb:
                time.sleep(0.3)
                mask[sb - 1] = self.parseStatusByte(sb)
                status += ', '.join(np.array(getattr(Shutter,
                    'STATUS_BYTE_%i' % sb))[mask[sb - 1] == 1])
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
            #self.currPos = Shutter.positions[self.send('ss\r\n')[0]]
            self.status = status
            return mask
        except Error.CommErr, e:
            print e


