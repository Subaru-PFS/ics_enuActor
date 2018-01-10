#!/usr/bin/env python

import sys

import numpy as np

from enuActor.Controllers.Simulator.slit_simu import SlitSimulator
from enuActor.Controllers.device import Device
from enuActor.Controllers.drivers import hxp_drivers
from enuActor.utils.wrap import busy, formatException


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
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        Device.__init__(self, actor, name)

        # Hexapod Attributes
        self.groupName = 'HEXAPOD'
        self.myxps = None
        self.socketId = None

        self.currPos = [np.nan] * 6

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice().
        | Convert to world tool and home.

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
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
        """| Start socket with the hexapod controller or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        if self.currMode == 'operation':
            self.myxps = hxp_drivers.XPS()
            self.socketId = self.myxps.TCP_ConnectToServer(self.host, self.port, slit.timeout)
        else:
            self.myxps = SlitSimulator()
            self.socketId = 1

        if self.socketId == -1:
            raise Exception('Connection to Hexapod failed check IP & Port')

    def initialise(self, cmd):
        """| Initialise hexapod, called y device.initDevice().

        - kill socket
        - init hxp
        - search home
        - set home and tool system
        - go home

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """

        cmd.inform("text='killing existing socket..._'")
        self._kill()

        cmd.inform("text='initialising hxp..._'")
        self._initialize()

        cmd.inform("text='seeking home ...'")
        self._homeSearch()

        self._hexapodCoordinateSysSet('Work', self.home)
        cmd.inform("slitHome=%s" % ','.join(["%.5f" % p for p in self.home]))

        self._hexapodCoordinateSysSet('Tool', self.tool_value)
        cmd.inform("slitTool=%s" % ','.join(["%.5f" % p for p in self.tool_value]))

        cmd.inform("text='going to home ...'")
        self._hexapodMoveAbsolute([0, 0, 0, 0, 0, 0])

    def getStatus(self, cmd=None, doFinish=True):
        """| Get status from the controller and publish slit keywords.

        - slit = state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
        - slitInfo = str : *an interpreted status returned by the controller*

        :param cmd: on going command
        :param doFinish: if True finish the command
        """
        ender = cmd.finish if doFinish else cmd.inform
        fender = cmd.fail if doFinish else cmd.warn
        self.currPos = 6 * [np.nan]

        # if self.fsm.current in ['LOADED', 'IDLE', 'BUSY']:
        try:
            ret = self._getHxpStatusString(self._getHxpStatus())
            cmd.inform("slitInfo='%s'" % ret)
            self.currPos = self._getCurrentPosition()
            cmd.inform('slitLocation=%s' % self.location)

        except Exception as e:
            cmd.warn(
                "text='%s getStatus failed %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))
            cmd.warn('slitLocation=undef')
            ender = fender

        ender("slit=%s,%s,%s" % (self.fsm.current, self.currMode, ','.join(["%.5f" % p for p in self.currPos])))

    @busy
    def moveTo(self, cmd, reference, posCoord):
        """| *wrapper @busy* handles the state machine.
        | Move to posCoord in the reference,

        :param cmd: on going command
        :param reference: 'absolute' or 'relative'
        :param posCoord: [x, y, z, u, v, w]
        :type reference: str
        :type posCoord: list
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False if the command fail,fsm (BUSY => FAILED)
        """
        try:
            if reference == 'absolute':
                ret = self._hexapodMoveAbsolute(posCoord)

            elif reference == 'relative':
                ret = self._hexapodMoveIncremental('Work', posCoord)

        except Exception as e:
            cmd.warn("text='%s move to %s failed failed %s'" % (self.name.upper(), reference,
                                                                formatException(e, sys.exc_info()[2])))
            if not "Warning: [X, Y, Z, U, V, W] exceed" in str(e):
                return False

        return True

    def getSystem(self, system):
        """| Get system from the controller and update the actor's current value.

        :param system: Work|Tool
        :type system: str
        :return:  [x, y, z, u, v, w] coordinate system definition
        :raise: Exception if the coordinate system does not exist
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
        """| Send new coordinate system to the controller

        :param system: Work|Tool
        :param posCoord: [x, y, z, u, v, w]
        :type system: str
        :type posCoord: list
        :raise: Exception if an error is raised by errorChecker
        """
        return self._hexapodCoordinateSysSet(system, posCoord)

    def shutdown(self, cmd, enable):
        """| Prepared controller for shutdown, fsm (IDLE => OFF).
        
        :param cmd: on going command:
        :raise: if a command fail, user if warned with error
        """
        if enable:
            ret = self._hexapodEnable()
            cmd.inform("text='loading Slit controller..._'")
            self.fsm.startLoading()
        else:
            ret = self._hexapodDisable()
            # cmd.inform("text='killing existing socket..._'")
            # self._kill()
            self.fsm.shutdown()

        return ret

    def abort(self, cmd):
        """| Aborting current move, fsm (BUSY -> ?).

        :param cmd: on going command:
        :raise: if a command fail, user if warned with error
        """

        cmd.inform("text='aborting move..._'")
        self._kill()

    def compute(self, type, pix):
        """| Compute array for moveTo relative to input parameters.

        :param type: focus|dither
        :param pix: number of pixel
        :type type: str
        :type pix: int
        :rtype: list
        :return: magnification*pix*[x, y, z, 0, 0, 0]
        """
        array = np.array(self.focus_axis) if type == "focus" else np.array(self.dither_axis)
        return list(self.magnification * pix * array)

    @property
    def location(self):
        delta = np.sum(np.abs(np.zeros(6) - np.array(self.currPos)))
        if delta > 0.001:
            return 'undef'
        else:
            return 'home'

    def _getCurrentPosition(self):
        """| Get current position.

        :return: position [x, y, z, u, v, w]
        :rtype: list
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupPositionCurrentGet, self.socketId, self.groupName, 6)

    def _getHxpStatus(self):
        """| Get hexapod status as an integer.

        :return: error code
        :rtype: int
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupStatusGet, self.socketId, self.groupName)

    def _getHxpStatusString(self, code):
        """| Get hexapod status interpreted as a string.

        :param code: error code
        :return: status_string
        :rtype: str
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupStatusStringGet, self.socketId, code)

    def _kill(self):
        """| Kill socket.

        :return: ''
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupKill, self.socketId, self.groupName)

    def _initialize(self):
        """| Initialize communication.

        :return: ''
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupInitialize, self.socketId, self.groupName)

    def _homeSearch(self):
        """| Home searching.

        :return: ''
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupHomeSearch, self.socketId, self.groupName)

    def _hexapodCoordinateSysGet(self, coordSystem):
        """| Get coordinates system definition from hexapod memory.

        :param coordSystem: Work|Tool
        :type coordSystem: str
        :rtype: list
        :return: coordSystem [x, y, z, u, v, w]
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.HexapodCoordinateSystemGet, self.socketId, self.groupName, coordSystem)

    def _hexapodCoordinateSysSet(self, coordSystem, posCoord):
        """| Set coordinates system from parameters.

        :param coordSystem: Work|Tool
        :param posCoord: [x, y, z, u, v, w]
        :type posCoord: list
        :return: ''
        :raise: Exception if an error occured
        """
        [x, y, z, u, v, w] = posCoord
        return self.errorChecker(self.myxps.HexapodCoordinateSystemSet, self.socketId, self.groupName, coordSystem,
                                 x, y, z, u, v, w)

    def _hexapodMoveAbsolute(self, posCoord):
        """| Move hexapod in absolute.
        | In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        | Software limits are set to prevent any risk of collision.

        :param posCoord: [x, y, z, u, v, w].
        :type posCoord: list
        :return: ''
        :raise: Exception if an error occured
        """
        [x, y, z, u, v, w] = posCoord

        for lim_inf, lim_sup, coord in zip(self.lowerBounds, self.upperBounds, [x, y, z, u, v, w]):
            if not lim_inf <= coord <= lim_sup:
                raise Exception("Warning: [X, Y, Z, U, V, W] exceed : %.5f not permitted" % coord)

        return self.errorChecker(self.myxps.HexapodMoveAbsolute, self.socketId, self.groupName, 'Work', x, y, z, u, v,
                                 w)

    def _hexapodMoveIncremental(self, coordSystem, posCoord):
        """| Move hexapod in relative.
        | In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        | Therefor software limit are set to prevent any risk of collision.

        :param posCoord: [x, y, z, u, v, w]
        :type posCoord: list
        :return: ''
        :raise: Exception if an error occured
        """
        [x, y, z, u, v, w] = posCoord

        for lim_inf, lim_sup, coord, pos in zip(self.lowerBounds, self.upperBounds, [x, y, z, u, v, w], self.currPos):
            if not lim_inf <= pos + coord <= lim_sup:
                raise Exception("Warning: [X, Y, Z, U, V, W] exceed : %.5f not permitted" % (pos + coord))

        return self.errorChecker(self.myxps.HexapodMoveIncremental, self.socketId, self.groupName, coordSystem, x,
                                 y, z, u, v, w)

    def _hexapodDisable(self):
        """| Disable hexapod.

        :return: ''
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupMotionDisable, self.socketId, self.groupName)

    def _hexapodEnable(self):
        """| Enable hexapod.

        :return: ''
        :raise: Exception if an error occured
        """
        return self.errorChecker(self.myxps.GroupMotionEnable, self.socketId, self.groupName)

    def errorChecker(self, func, *args):
        """| Decorator for slit lower level functions.

        :param func: function to check
        :param args: function arguments
        :returns: ret
        :rtype: str
        :raise: Exception if an error is returned by hxp drivers
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

        return buf[1:] if len(buf) > 2 else buf[1]
