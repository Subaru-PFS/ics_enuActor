#!/usr/bin/env python

import sys

import numpy as np

from enuActor.Controllers.Simulator.slit_simu import SlitSimulator
from enuActor.Controllers.device import Device
from enuActor.Controllers.drivers import hxp_drivers
from enuActor.utils.wrap import busy


class slit(Device):
    timeout = 2

    @staticmethod
    def convertToWorld(array):
        def degToRad(deg):
            return 2 * np.pi * deg / 360

        [X, Y, Z, U, V, W] = array
        x = X * np.cos(degToRad(W)) - Y * np.sin(degToRad(W))
        y = X * np.sin(degToRad(W)) + Y * np.cos(degToRad(W))
        return [round(x, 5), round(y, 5), float(Z), float(U), float(V), float(W)]

    def __init__(self, actor, name):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Device.__init__(self, actor, name)

        # Hexapod Attributes
        self.groupName = 'HEXAPOD'
        self.myxps = None
        self.socketId = None
        self.link_busy = False
        self.currPos = [np.nan] * 6

    def loadCfg(self, cmd, mode=None):
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """

        self.actor.reloadConfiguration(cmd=cmd)

        self.currMode = self.actor.config.get('slit', 'mode') if mode is None else mode
        self.host = self.actor.config.get('slit', 'host')
        self.port = int(self.actor.config.get('slit', 'port'))
        self.home = [float(val) for val in self.actor.config.get('slit', 'home').split(',')]
        self.slit_position = [float(val) for val in self.actor.config.get('slit', 'slit_position').split(',')]
        self.dither_axis = [float(val) for val in self.actor.config.get('slit', 'dither_axis').split(',')]
        self.focus_axis = [float(val) for val in self.actor.config.get('slit', 'focus_axis').split(',')]
        self.thicknessCarriage = float(self.actor.config.get('slit', 'thicknessCarriage'))
        self.magnification = float(self.actor.config.get('slit', 'magnification'))
        self.lowerBounds = [float(val) for val in self.actor.config.get('slit', 'lowerBounds').split(',')]
        self.upperBounds = [float(val) for val in self.actor.config.get('slit', 'upperBounds').split(',')]

        self.homeHexa = self.home
        self.home = slit.convertToWorld([sum(i) for i in zip(self.homeHexa[:3],
                                                             self.slit_position[:3])] + self.homeHexa[3:])

        # Set Tool to slit home coord instead of center of hexa

        tool_value = self.slit_position[:3] + self.home[3:]
        tool_value = slit.convertToWorld(tool_value)[:3] + self.slit_position[3:]
        # Tool z = 21 + z_slit with 21 height of upper carriage
        self.tool_value = [sum(i) for i in zip(tool_value, [0, 0, self.thicknessCarriage, 0, 0, 0])]

    def startCommunication(self, cmd):

        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the controller, fsm goes to LOADED
                 False, ret: if the communication failed with the controller, ret is the error, fsm goes to FAILED
        """

        if self.currMode == 'operation':
            self.myxps = hxp_drivers.XPS()
            self.socketId = self.myxps.TCP_ConnectToServer(self.host, self.port, slit.timeout)
        else:
            self.myxps = SlitSimulator(self.home)
            self.socketId = 1

        if self.socketId == -1:
            raise Exception('Connection to Hexapod failed check IP & Port')

    def initialise(self, cmd):
        """ Initialise slit

        - kill socket
        - init hxp
        - search home
        - set home and tool system
        - go home

        wrapper @safeCheck handles the state machine
        :param e, fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """


        cmd.inform("text='killing existing socket..._'")
        self._kill()

        cmd.inform("text='initialising hxp..._'")
        self._initialize()

        cmd.inform("text='seeking home ...'")
        self._homeSearch()

        self._hexapodCoordinateSysSet('Work', *self.home)
        cmd.inform("slitHome=%s" % ','.join(["%.5f" % p for p in self.home]))

        self._hexapodCoordinateSysSet('Tool', *self.tool_value)
        cmd.inform("slitTool=%s" % ','.join(["%.5f" % p for p in self.tool_value]))

        cmd.inform("text='going to home ...'")
        self._hexapodMoveAbsolute(*[0, 0, 0, 0, 0, 0])

    def getStatus(self, cmd=None, doFinish=True):
        """getStatus
        position is nan if the controller is unreachable
        :param cmd,
        :return True, state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
                 False, state, mode, nan, nan, nan, nan, nan, nan if not initialised or an error had occured
        """

        ender = cmd.finish if doFinish else cmd.inform
        fender = cmd.fail if doFinish else cmd.warn
        self.currPos = 6 * [np.nan]

        if self.fsm.current in ['LOADED', 'IDLE', 'BUSY']:
            try:
                ret = self._getHxpStatusString(self._getHxpStatus()[0])[0]
                cmd.inform("slitInfo='%s'" % ret)
                self.currPos = self._getCurrentPosition()
            except Exception as e:
                cmd.warn("text='%s getStatus failed %s'" % (self.name.upper(), self.formatException(e, sys.exc_info()[2])))
                ender = fender

        ender("slit=%s,%s,%s" % (self.fsm.current, self.currMode, ','.join(["%.5f" % p for p in self.currPos])))

    @busy
    def moveTo(self, cmd, reference, posCoord):
        """MoveTo.
        Move to posCoord

        wrapper @busy handles the state machine
        :param cmd
        :param reference: 'absolute' or 'relative'
        :param posCoord: [x, y, z, u, v, w]
        :return: True, ret : if the command raise no error
                 False, ret: if the command fail

        """
        try:
            if reference == 'absolute':
                ret = self._hexapodMoveAbsolute(*posCoord)

            elif reference == 'relative':
                ret = self._hexapodMoveIncremental('Work', *posCoord)

        except Exception as e:
            cmd.warn("text='%s move to %s failed failed %s'" % (self.name.upper(), reference,
                                                                self.formatException(e, sys.exc_info()[2])))
            if not "Warning: [X, Y, Z, U, V, W] exceed" in str(e):
                return False

        return True

    def getSystem(self, system):
        """getSystem
        Get system from the controller and update the actor's current value

        :param system (Work or Home)

        :return: True, system
                 False, ret : if a an error ret occured
        """
        ret = self._hexapodCoordinateSysGet(system)
        if system == "Work":
            self.home = ret
        elif system == "Tool":
            self.tool_value = ret
        else:
            raise Exception("system : %s does not exist" % system)

        return ret

    def setSystem(self, system, posCoord):
        """setSystem
        Send new coordinate system to the controller

        :param system (Work or Home)
        :param posCoord : [x, y, z, u, v, w]

        :return: True, ''
                 False, ret : if a an error ret occured
        """
        return self._hexapodCoordinateSysSet(system, *posCoord)

    def shutdown(self, cmd):
        """shutdown.
        prepared controller for shutdown

        :param cmd:
        :return: True : if every steps are successfully operated, cmd is not finished
                 False: if the command fail, command is finished with cmd.fail
        """
        if self.fsm.current == "IDLE":
            cmd.inform("text='going to home ...'")
            self._hexapodMoveAbsolute(*[0, 0, 0, 0, 0, 0])

        cmd.inform("text='killing existing socket..._'")
        self._kill()

        cmd.inform("text='shutting down ..._'")
        self.fsm.shutdown()

    def abort(self, cmd):
        cmd.inform("text='aborting move..._'")
        self._kill()

    def compute(self, type, pix):
        """compute.
        compute array for moveTo relative to input parameters

        :param type: focus|dither
        :param pix: number of pixel
        :return: magnification*pix*[x, y, z, 0, 0, 0]
        """
        array = np.array(self.focus_axis) if type == "focus" else np.array(self.dither_axis)
        return list(self.magnification * pix * array)

    def _getCurrentPosition(self):
        """_getCurrentPosition.
         :return: True, position [x, y, z, u, v, w]
                  False, ret : if a an error ret occured
        """
        return self.errorChecker(self.myxps.GroupPositionCurrentGet, self.socketId, self.groupName, 6)

    def _getHxpStatus(self):
        """_getHxpStatus.
         :return: [error, code]
        """
        return self.errorChecker(self.myxps.GroupStatusGet, self.socketId, self.groupName)

    def _getHxpStatusString(self, code):
        """_getHxpStatusString.
         :param code, error code
         :return: [error, status string]
        """
        return self.errorChecker(self.myxps.GroupStatusStringGet, self.socketId, code)

    def _kill(self):
        """_kill.
         :return: True, ''
                  False, ret : if a an error ret occured
        """
        return self.errorChecker(self.myxps.GroupKill, self.socketId, self.groupName)

    def _initialize(self):
        """_initialize.
         :return: True, ''
                  False, ret : if a an error ret occured
        """
        return self.errorChecker(self.myxps.GroupInitialize, self.socketId, self.groupName)

    def _homeSearch(self):
        """_homeSearch.
         :return: True, ''
                  False, ret : if a an error ret occured
        """
        return self.errorChecker(self.myxps.GroupHomeSearch, self.socketId, self.groupName)

    def _hexapodCoordinateSysGet(self, coordSystem):
        """_hexapodCoordinateSysGet.
         :param coordSystem ( Work or Tool)
         :return: True, coordSystem [x, y, z, u, v, w]
                  False, ret : if a an error ret occured
        """
        return self.errorChecker(self.myxps.HexapodCoordinateSystemGet, self.socketId, self.groupName, coordSystem)

    def _hexapodCoordinateSysSet(self, coordSystem, x, y, z, u, v, w):
        """_hexapodCoordinateSysSet.
         :param coordSystem ( Work or Tool)
         :param x, x position
         :param y, y position
         :param z, z position
         :param u, u position
         :param v, v position
         :param w, w position
         :return: True, ''
                  False, ret : if a an error ret occured
        """
        return self.errorChecker(self.myxps.HexapodCoordinateSystemSet, self.socketId, self.groupName, coordSystem,
                                 x, y, z, u, v, w)

    def _hexapodMoveAbsolute(self, x, y, z, u, v, w):
        """_hexapodMoveAbsolute.
         :param coordSystem ( Work or Tool)
         :param x, x position
         :param y, y position
         :param z, z position
         :param u, u position
         :param v, v position
         :param w, w position
         :return: True, ''
                  False, ret : if a an error ret occured
        """
        for lim_inf, lim_sup, coord in zip(self.lowerBounds, self.upperBounds, [x, y, z, u, v, w]):
            if not lim_inf <= coord <= lim_sup:
                raise Exception("Warning: [X, Y, Z, U, V, W] exceed : %.5f not permitted" % coord)

        return self.errorChecker(self.myxps.HexapodMoveAbsolute, self.socketId, self.groupName, 'Work', x, y, z, u, v,
                                 w)

    def _hexapodMoveIncremental(self, coordSystem, x, y, z, u, v, w):
        """_hexapodMoveIncremental.
         :param coordSystem ( Work or Tool)
         :param x, x position
         :param y, y position
         :param z, z position
         :param u, u position
         :param v, v position
         :param w, w position
         :return: True, ''
                  False, ret : if a an error ret occured
        """

        for lim_inf, lim_sup, coord, pos in zip(self.lowerBounds, self.upperBounds, [x, y, z, u, v, w], self.currPos):
            if not lim_inf <= pos + coord <= lim_sup:
                raise Exception("Warning: [X, Y, Z, U, V, W] exceed : %.5f not permitted" % (pos + coord))

        return self.errorChecker(self.myxps.HexapodMoveIncremental, self.socketId, self.groupName, coordSystem, x,
                                 y, z, u, v, w)

    def errorChecker(self, func, *args):
        """ Kind of decorator who check error after routine.

        :returns: error, ret
        """

        buf = func(*args)
        if buf[0] != 0:
            if buf[0] == -2:
                raise Exception(func.func_name + 'TCP timeout')
            elif buf[0] == -108:
                raise Exception(func.func_name + 'TCP/IP connection was closed by an admin')
            else:
                [errorCode, errorString] = self.myxps.ErrorStringGet(self.socketId, buf[0])
                if buf[0] == -17:
                    raise Exception("Warning: [X, Y, Z, U, V, W] exceed : %s" % errorString)
                elif errorCode != 0:
                    raise Exception(func.func_name + ' : ERROR ' + str(errorCode))
                else:
                    raise Exception(func.func_name + ' : ' + errorString)

        return buf[1:]
