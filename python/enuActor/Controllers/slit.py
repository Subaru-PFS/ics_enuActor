#!/usr/bin/env python

import numpy as np

from enuActor.Controllers.Simulator.slit_simu import SlitSimulator
from enuActor.Controllers.device import Device
from enuActor.Controllers.utils import hxp_drivers
from enuActor.Controllers.wrap import safeCheck, busy


class slit(Device):
    timeout = 5

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
        super(slit, self).__init__(actor, name)
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

        try:
            self.currMode = self.actor.config.get('slit', 'mode') if mode is None else mode
            self.host = self.actor.config.get('slit', 'host')
            self.port = int(self.actor.config.get('slit', 'port'))
            self.home = [float(val) for val in self.actor.config.get('slit', 'home').split(',')]
            self.slit_position = [float(val) for val in self.actor.config.get('slit', 'slit_position').split(',')]
            self.dither_axis = [float(val) for val in self.actor.config.get('slit', 'dither_axis').split(',')]
            self.focus_axis = [float(val) for val in self.actor.config.get('slit', 'focus_axis').split(',')]
            self.thicknessCarriage = float(self.actor.config.get('slit', 'thicknessCarriage'))
            self.magnification = float(self.actor.config.get('slit', 'magnification'))
            self.lowBounds = [float(val) for val in self.actor.config.get('slit', 'low_bounds').split(',')]
            self.highBounds = [float(val) for val in self.actor.config.get('slit', 'high_bounds').split(',')]

        except Exception as e:
            return False, 'Config file badly formatted, Exception : %s ' % str(e)

        self.homeHexa = self.home
        self.home = slit.convertToWorld(
            [sum(i) for i in zip(self.homeHexa[:3], self.slit_position[:3])] + self.homeHexa[3:])

        # Set Tool to slit home coord instead of center of hexa

        tool_value = self.slit_position[:3] + self.home[3:]
        tool_value = slit.convertToWorld(tool_value)[:3] + self.slit_position[3:]
        # Tool z = 21 + z_slit with 21 height of upper carriage
        self.tool_value = [sum(i) for i in zip(tool_value, [0, 0, self.thicknessCarriage, 0, 0, 0])]

        cmd.inform("text='config File successfully loaded")
        return True, ''

    def startCommunication(self, cmd):

        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the controller, fsm goes to LOADED
                 False, ret: if the communication failed with the controller, ret is the error, fsm goes to FAILED
        """

        if self.currMode == 'operation':
            cmd.inform("text='Connecting to HXP...'")
            self.myxps = hxp_drivers.XPS()
            self.socketId = self.myxps.TCP_ConnectToServer(self.host, self.port, slit.timeout)

        else:
            cmd.inform("text='Connecting to Slit Simulator'")
            self.myxps = SlitSimulator(self.home)
            print type(self.myxps)
            self.socketId = 1

        if self.socketId == -1:
            return False, 'Connection to Hexapod failed check IP & Port'

        return True, 'Connected to Hexapod'

    @safeCheck
    def initialise(self, e):
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

        cmd = e.cmd if hasattr(e, "cmd") else self.actor.bcast

        cmd.inform("text='killing existing socket..._'")
        ok, ret = self._kill()
        if not ok:
            return False, ret

        cmd.inform("text='initialising hxp..._'")
        ok, ret = self._initialize()
        if not ok:
            return False, ret

        cmd.inform("text='seeking home ...'")
        ok, ret = self._homeSearch()
        if not ok:
            return False, ret

        ok, ret = self._hexapodCoordinateSysSet('Work', *self.home)
        if ok:
            cmd.inform("slitHome=%s" % ','.join(["%.5f" % p for p in self.home]))
        else:
            return False, ret

        ok, ret = self._hexapodCoordinateSysSet('Tool', *self.tool_value)
        if ok:
            cmd.inform("slitTool=%s" % ','.join(["%.5f" % p for p in self.tool_value]))
        else:
            return False, ret

        cmd.inform("text='going to home ...'")
        ok, ret = self._hexapodMoveAbsolute(*[0, 0, 0, 0, 0, 0])
        if ok:
            return True, 'Slit Successfully initialised'
        else:
            return False, ret

    def getStatus(self, cmd=None):
        """getStatus
        position is nan if the controller is unreachable
        :param cmd,
        :return True, state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
                 False, state, mode, nan, nan, nan, nan, nan, nan if not initialised or an error had occured
        """

        if self.fsm.current in ['IDLE', 'BUSY']:
            ok, ret = self._getCurrentPosition()

            self.currPos = ret if ok else [np.nan] * 6
        else:
            ok, self.currPos = True, [np.nan] * 6

        return ok, "%s,%s,%s" % (self.fsm.current, self.currMode, ','.join(["%.5f" % p for p in self.currPos]))

    def getInfo(self):
        """getInfo
        text information from the controller

        :return: error_code, status

        """
        if self.fsm.current in ['LOADED', 'IDLE', 'BUSY']:
            [error, code] = self._getHxpStatus()
            if error == 0:
                return self._getHxpStatusString(code)
            elif error == -2:
                return [error, 'getHxpStatusString TCP timeout']
            elif error == -108:
                return [error, 'getHxpStatusString TCP/IP connection was closed by an admin']
            else:
                return [error, 'unknown error : %i' % error]
        return [-1, "Connection to Hexapod failed"]

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
        if reference == 'absolute':
            return self._hexapodMoveAbsolute(*posCoord)

        elif reference == 'relative':
            return self._hexapodMoveIncremental('Work', *posCoord)

    def getSystem(self, system):
        """getSystem
        Get system from the controller and update the actor's current value

        :param system (Work or Home)

        :return: True, system
                 False, ret : if a an error ret occured
        """

        ok, ret = self._hexapodCoordinateSysGet(system)
        if ok:
            if system == "Work":
                self.home = ret
            elif system == "Tool":
                self.tool_value = ret
            else:
                return False, "system : %s does not exist" % system
        return ok, ret

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
            ok, ret = self.moveTo("absolute", [0, 0, 0, 0, 0, 0])
            if not ok:
                cmd.warn("text='error : %s'" % ret)

        cmd.inform("text='killing existing socket..._'")
        ok, ret = self._kill()
        if ok:
            self.fsm.shutdown()

        return ok, ret

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
        return self.myxps.GroupStatusGet(self.socketId, self.groupName)

    def _getHxpStatusString(self, code):
        """_getHxpStatusString.
         :param code, error code
         :return: [error, status string]
        """
        return self.myxps.GroupStatusStringGet(self.socketId, code)

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
        for lim_inf, lim_sup, coord in zip(self.lowBounds, self.highBounds, [x, y, z, u, v, w]):
            if not lim_inf <= coord <= lim_sup:
                return False, "error %.5f not in boundaries" % coord

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
        if not self.currPos == [np.nan] * 6:
            for lim_inf, lim_sup, coord, pos in zip(self.lowBounds, self.highBounds, [x, y, z, u, v, w],
                                                    self.currPos):
                if not lim_inf <= pos + coord <= lim_sup:
                    return False, "error %.5f not in boundaries" % (pos + coord)

        return self.errorChecker(self.myxps.HexapodMoveIncremental, self.socketId, self.groupName, coordSystem, x,
                                 y, z, u, v, w)

    def errorChecker(self, func, *args):
        """ Kind of decorator who check error after routine.

        :returns: error, ret
        """

        buf = func(*args)

        if buf[0] != 0:
            if buf[0] == -2:
                return False, func.func_name + 'TCP timeout'
            elif buf[0] == -108:
                return False, func.func_name + 'TCP/IP connection was closed by an admin'
            else:
                [errorCode, errorString] = self.myxps.ErrorStringGet(self.socketId, buf[0])
                if buf[0] == -17:
                    return False, "Warning: [X, Y, Z, U, V, W] exceed : %s" % errorString
                elif errorCode != 0:
                    return False, func.func_name + ' : ERROR ' + str(errorCode)
                else:
                    return False, func.func_name + ' : ' + errorString
        else:
            return True, buf[1:]
