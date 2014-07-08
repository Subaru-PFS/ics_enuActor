#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                        FPSA SW device module                        #
#######################################################################

from enuActor.QThread import *
import serial, time
import Error
from Device import *
from utils import hxp_drivers
import numpy as np
import re
import sys


class Slit(DualModeDevice):

    """SW device: Fiber Slit Positionning Sub Assembly

        Attributes:
         * currPos : current position of the slit

    """

    def __init__(self, actor=None):
        super(Slit, self).__init__(actor)
        self.currPos = None
        self.groupName = 'HEXAPOD'
        self.check_status_busy = 0
        self.myxps = None
        self.socketId = None
        self.link_busy = False

    def initialise(self):
        """ Initialise shutter.
        Here just trigger the FSM to INITIALISING and IDLE
        :returns: @todo
        :raises: @todo

        """
        if self.mode == 'simulated':
            super(Slit, self).initialise()
            return

        if self.socketId == -1:
            raise Error.CommErr('Connection to Hexapod failed,\
                    Check Ip & port')
        self._kill()
        self._initialize()
        self._homeSearch()
        self.check_status()

    def getHome(self):
        """@todo: Docstring for getHome.
        :returns: [x, y, z, u, v, w]
        :raises: :class: `~.Error.DeviceError`, :class:`~.Error.CommErr`
        """
        return self._hexapodCoordinateSytemGet('Tool')

    def setHome(self, posCoord=None):
        """@todo: Docstring for setHome.

        :param posCoord: [x, y, z, u, v, w] or nothing if current
        :raises: :class: `~.Error.DeviceError`, :class:`~.Error.CommErr`
        """
        if posCoord is None:
            posCoord = self._getCurrentPosition()
            curHome = self.getHome()
            print posCoord
            print curHome
            #newhome = posCoord + curHome
            posCoord = [sum(x) for x in zip(posCoord, curHome)]
            print posCoord
        self._hexapodCoordinateSytemSet('Tool', *posCoord)


    def moveTo(self, baseline='absolute', posCoord=None):
        """@todo: Docstring for moveTo.

        :param posCoord: [x, y, z, u, v, w] or nothing if home
        :raises: :class: `~.Error.DeviceError`, :class:`~.Error.CommErr`
        """
        if posCoord == None:
            posCoord = self.getHome()
        self._hexapodMoveAbsolute('Work', *posCoord)

    def op_start_communication(self):
        self.load_cfg(self.device)
        self.myxps = hxp_drivers.XPS()
        self.socketId = self.myxps.TCP_ConnectToServer(
                self._cfg['ip'],
                int(self._cfg['port']),
                int(self._cfg['timeout'])
                )
        super(Slit, self).op_start_communication()

    def op_check_status(self):
        """Check status of hexapod and position
        :raises: :class: `~.Error.DeviceError`, :class:`~.Error.CommErr`
        """

        if self.fsm.current not in ['none', 'LOADED', 'INITIALISING']:
            time.sleep(.1)# have to wait else return busy socke
            # check status
            status_code = self._getStatus()
            status = self._getStatusString(int(status_code))
            # check position
            self.currPos = '[x, y, z, u, v, w] = %s' %\
                    self._getCurrentPosition()

    #############
    #  Parsers  #
    #############

    def _getCurrentPosition(self):
        return self.errorChecker(
                self.myxps.GroupPositionCurrentGet,
                self.socketId,
                self.groupName,
                6)

    def _getStatus(self):
        return self.errorChecker(
                self.myxps.GroupStatusGet,
                self.socketId,
                self.groupName)[0]

    def _getStatusString(self, code):
        return self.errorChecker(
                self.myxps.GroupStatusStringGet,
                self.socketId,
                code)

    def _kill(self):
        return self.errorChecker(
                self.myxps.GroupKill,
                self.socketId,
                self.groupName)

    def _initialize(self):
        return self.errorChecker(
                self.myxps.GroupInitialize,
                self.socketId,
                self.groupName)

    def _homeSearch(self):
        return self.errorChecker(
                self.myxps.GroupHomeSearch,
                self.socketId,
                self.groupName)

    def _hexapodCoordinateSytemGet(self, coordSystem):
        return self.errorChecker(
                self.myxps.HexapodCoordinateSystemGet,
                self.socketId,
                self.groupName,
                coordSystem)

    def _hexapodCoordinateSytemSet(self, coordSystem, x, y, z, u, v, w):
        return self.errorChecker(
                self.myxps.HexapodCoordinateSystemSet,
                self.socketId,
                self.groupName,
                coordSystem,
                x, y, z, u, v, w)

    def _hexapodMoveAbsolute(self, coordSystem, x, y, z, u, v, w):
        print x, y, z, u, v,w
        return self.errorChecker(
                self.myxps.HexapodMoveAbsolute,
                self.socketId,
                self.groupName,
                coordSystem,
                x, y, z, u, v, w)

    def errorChecker(self, func, *args):
        """ Kind of decorator who check error after routine.
        :returns: value receive from TCP
        :raises: :class: `~.Error.DeviceError`, :class:`~.Error.CommErr`
        """
        #Check if sending or receiving
        if self.link_busy == True:
            time.sleep(0.2)
            return self.errorChecker(func, *args)
        else:
            self.link_busy = True
        buf = func(*args)
        self.link_busy = False
        if buf[0] != 0:
            if buf[0] not in [-2, -108]:
                [errorCode, errorString] = self.myxps.ErrorStringGet(self.socketId, buf[0])
                if errorCode != 0:
                    err = func.func_name + ' : ERROR ' + str(errorCode)
                else:
                    err = func.func_name + ' : ' + errorString
            else:
                if buf[0] == -2:
                    raise Error.CommErr(func.func_name + 'TCP timeout')
                elif buf[0] == -108:
                    raise Error.CommErr(func.func_name +
                            'TCP/IP connection was closed by an admin')
            raise Error.DeviceErr(err)#a traiter si Device ou COmm suivant cas
        return buf[1:]

