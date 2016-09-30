#!/usr/bin/env python

import time

import numpy as np

from Controllers.device import Device
from Controllers.Simulator.slit_simu import SlitSimulator
from Controllers.utils import hxp_drivers

class slit(Device):
    timeout = 5

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

    def loadCfg(self, cmd):

        self.currMode = self.actor.config.get('slit', 'mode')
        self.host = self.actor.config.get('slit', 'host')
        self.port = int(self.actor.config.get('slit', 'port'))

        self.home = [float(val) for val in self.actor.config.get('slit', 'home').split(',')]
        self.slit_position = [float(val) for val in self.actor.config.get('slit', 'slit_position').split(',')]
        self.dither_axis = [float(val) for val in self.actor.config.get('slit', 'dither_axis').split(',')]
        self.focus_axis = [float(val) for val in self.actor.config.get('slit', 'focus_axis').split(',')]
        self.thicknessCarriage = float(self.actor.config.get('slit', 'thicknessCarriage'))
        self.magnification = float(self.actor.config.get('slit', 'magnification'))

        return True

    def startCommunication(self, cmd):

        """startCommunication
        Start socket with the controller or simulate it
        :param:cmd,
        :return: True : if every steps are successfully operated, cmd is not finished
                 False: if the command fail, command is finished with cmd.fail
        """
        #time.sleep(12)

        if self.currMode == 'operation':
            cmd.inform("text='Connecting to HXP...'")
            self.myxps = hxp_drivers.XPS()
            self.socketId = self.myxps.TCP_ConnectToServer(self.host, self.port, slit.timeout)

        else:
            cmd.inform("text='Connecting to Slit Simulator'")
            self.myxps = SlitSimulator(self.home)
            self.socketId = 1

        if self.socketId == -1:
            cmd.fail("text='Connection to Hexapod failed check IP & Port'")
            return False
        return True

    def initialise(self, cmd):
        """ Initialise slit

        - init hxp
        - search home
        - go home
        - check status

        :param cmd : current command
        :return: True : if every steps are successfully operated, cmd not finished,
                 False : if a command fail, command is finished with cmd.fail
        """
        import time
        time.sleep(10)
        # Kill existing socket
        if self._kill(cmd):
            cmd.inform("text='killing existing socket..._'")
        else:
            return False

        if self._initialize(cmd):
            cmd.inform("text='initialising hxp..._'")
        else:
            return False

        if self._homeSearch(cmd):
            cmd.inform("text='seeking home ...'")
        else:
            return False

        # Set Work to slit home coord
        if not self.setHome(cmd, self.home):
            return False

        # Tool z = 21 + z_slit with 21 height of upper carriage
        tool_value = [sum(i) for i in zip(self.slit_position, [0, 0, self.thicknessCarriage, 0, 0, 0])]
        # Set Tool to slit home coord instead of center of hexa
        if not self._hexapodCoordinateSysSet(cmd, 'Tool', *tool_value):
            return False

        if self._hexapodMoveAbsolute(cmd, *[0, 0, 0, 0, 0, 0]):
            cmd.inform("text='going to home ...'")
        else:
            return False

        return True

    def setHome(self, cmd, posCoord=None):
        """setHome.
        setHome to posCoord or to current if posCoord is None

        .. warning:: posCoord requires the position of slit in world\
        and not position of upper carriage of hexapod.

        :param cmd
        :param  posCoord: [x, y, z, u, v, w] or nothing if current
        :return: True : if every steps are successfully operated, cmd not finished,
                 False : if a command fail, command is finished with cmd.fail
        """
        if posCoord is None:
            # position related to work
            ok, posCoord = self._getCurrentPosition(cmd)
            if not ok:
                return False
            # work related to WORLD
            ok, curHome = self._hexapodCoordinateSysGet(cmd, 'Work')
            if not ok:
                return False
            # position related to WORLD
            posCoord = [sum(x) for x in zip(posCoord, curHome)]

        # update Home slit related to WORLD
        if not self._hexapodCoordinateSysSet(cmd, 'Work', *posCoord):
            return False
        else:
            # update Home hexapod
            self.homeHexa = [xi - xj for xi, xj in
                             zip(posCoord, self.slit_position)]
            self.home = posCoord
            return True

    def getHome(self, cmd, doFinish=True):
        """getHome.

        :param:cmd
        :param:doFinish
        :return: True : if every steps are successfully operated, cmd is finished if doFinish
                 False : if a command fail, command is finished with cmd.fail
        """
        ender = cmd.finish if doFinish else cmd.inform
        ok, ret = self._hexapodCoordinateSysGet(cmd, 'Work')
        if not ok:
            return False
        else:
            ender("home=%s" % ','.join(["%.2f" % p for p in ret]))
            return True

    # def getHome(self, cmd, doFinish=True):
    #     """getHome.
    #
    #     :param:cmd
    #     :param:doFinish
    #     :return: True : if every steps are successfully operated, cmd is finished if doFinish
    #              False : if a command fail, command is finished with cmd.fail
    #     """
    #     ender = cmd.finish if doFinish else cmd.inform
    #     ok, ret = self._hexapodCoordinateSysGet(cmd, 'Work')
    #     if not ok:
    #         return False
    #     else:
    #         ender("home=%s" % ','.join(["%.2f" % p for p in ret]))
    #         return True

    def getPosition(self, cmd):
        """getPosition
        position is nan if we can't ask the controller
        :param:cmd,
        :return: True, pos : if every steps are successfully operated, cmd is not finished
                 False, pos: if the command fail, command is finished with cmd.fail
        """

        if self.fsm.current in ['IDLE']:
            ok, ret = self._getCurrentPosition(cmd)
            self.currPos = ret if ok else [np.nan] * 6
        else:
            ok, self.currPos = True, [np.nan] * 6

        return ok, self.currPos

    def moveTo(self, cmd, reference, posCoord=None):
        """MoveTo.
        Move to posCoord or to home if posCoord is None

        :param reference: 'absolute' or 'relative'
        :param posCoord: [x, y, z, u, v, w] or nothing if home
        :return: True : if every steps are successfully operated, cmd is not finished
                 False: if the command fail, command is finished with cmd.fail
        """

        # Go to home related to work : [0,0,0,0,0,0]
        posCoord = [0] * 6 if posCoord is None else posCoord

        if reference == 'absolute':
            if not self._hexapodMoveAbsolute(cmd, *posCoord):
                return False

        elif reference == 'relative':
            if not self._hexapodMoveIncremental(cmd, 'Work', *posCoord):
                return False

        return True

    def shutdown(self, cmd):
        """shutdown.
        prepared controller for shutdown

        :param cmd:
        :return: True : if every steps are successfully operated, cmd is not finished
                 False: if the command fail, command is finished with cmd.fail
        """

        if self._hexapodMoveAbsolute(cmd, *[0, 0, 0, 0, 0, 0]):
            cmd.inform("text='going to home ...'")
        else:
            return False

        if self._kill(cmd):
            cmd.inform("text='killing existing socket..._'")
        else:
            return False

        return True

    def compute(self, type, pix):
        """compute.
        compute array for moveTo relative to input parameters

        :param type: focus|dither
        :param pix: number of pixel
        :return: magnification*pix*[x, y, z, 0, 0, 0]
        """

        return list(self.magnification * pix * np.array(getattr(self, "%s_axis" % type)))

    def _getCurrentPosition(self, cmd):
        err, ret = self.errorChecker(self.myxps.GroupPositionCurrentGet, self.socketId, self.groupName, 6)
        if not err:
            return True, ret

        cmd.fail("text='%s'" % ret)
        return False, ret

    def _kill(self, cmd):
        err, ret = self.errorChecker(self.myxps.GroupKill, self.socketId, self.groupName)
        if not err:
            return True

        cmd.fail("text='%s'" % ret)
        return False

    def _initialize(self, cmd):

        err, ret = self.errorChecker(self.myxps.GroupInitialize, self.socketId, self.groupName)
        if not err:
            return True
        cmd.fail("text='%s'" % ret)
        return False

    def _homeSearch(self, cmd):

        err, ret = self.errorChecker(self.myxps.GroupHomeSearch, self.socketId, self.groupName)
        if not err:
            return True
        cmd.fail("text='%s'" % ret)
        return False

    def _hexapodCoordinateSysGet(self, cmd, coordSystem):
        err, ret = self.errorChecker(self.myxps.HexapodCoordinateSystemGet, self.socketId, self.groupName, coordSystem)
        if not err:
            return True, ret
        cmd.fail("text='%s'" % ret)
        return False, ret

    def _hexapodCoordinateSysSet(self, cmd, coordSystem, x, y, z, u, v, w):

        err, ret = self.errorChecker(self.myxps.HexapodCoordinateSystemSet, self.socketId, self.groupName, coordSystem,
                                     x, y, z, u, v, w)
        if err:
            cmd.fail("text='%s'" % ret)
            return False
        else:
            ok, ret = self._hexapodCoordinateSysGet(cmd, coordSystem)
            coordSystem = "home" if coordSystem == "Work" else coordSystem
            if ok:
                cmd.inform("%s=%s'" % (coordSystem.lower(), ','.join(["%.2f" % p for p in ret])))
                return True
            else:
                return False

    def _hexapodMoveAbsolute(self, cmd, x, y, z, u, v, w):
        """
        ..note: coordSystem not specified because has to be 'Work'

        """
        err, ret = self.errorChecker(self.myxps.HexapodMoveAbsolute, self.socketId, self.groupName, 'Work', x, y, z, u,
                                     v, w)
        if not err:
            return True

        cmd.fail("text='%s'" % ret)
        return False

    def _hexapodMoveIncremental(self, cmd, coordSystem, x, y, z, u, v, w):
        """
        ..todo: Add algorithm for simulation mode

        """
        err, ret = self.errorChecker(self.myxps.HexapodMoveIncremental, self.socketId, self.groupName, coordSystem, x,
                                     y, z, u, v, w)
        if not err:
            return True

        cmd.fail("text='%s'" % ret)
        return False

    # def _getStatus(self, cmd):
    #     err, ret = self.errorChecker(self.myxps.GroupStatusGet, self.socketId, self.groupName)[0]
    #     if not err:
    #         return True, ret
    #
    #     cmd.fail("text='%s'" % ret)
    #     return False, ret
    #
    # def _getStatusString(self, cmd, code):
    #
    #     err, ret = self.errorChecker(self.myxps.GroupStatusStringGet, self.socketId, code)
    #     if not err:
    #         return True, ret
    #
    #     cmd.fail("text='%s'" % ret)
    #     return False, ret

    def errorChecker(self, func, *args):
        """ Kind of decorator who check error after routine.

        :returns: value receive from TCP
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        # Check if sending or receiving
        # if self.link_busy == True:
        #     time.sleep(0.1)
        #     return self.errorChecker(func, *args)
        # else:
        #     self.link_busy = True
        buf = func(*args)
        #self.link_busy = False
        if buf[0] != 0:
            if buf[0] not in [-2, -108]:
                [errorCode, errorString] = self.myxps.ErrorStringGet(self.socketId, buf[0])
                if buf[0] == -17:
                    err = "Warning: [X, Y, Z, U, V, W] exceed : %s" % errorString
                elif errorCode != 0:
                    err = func.func_name + ' : ERROR ' + str(errorCode)
                else:
                    err = func.func_name + ' : ' + errorString
            else:
                if buf[0] == -2:
                    err = func.func_name + 'TCP timeout'
                elif buf[0] == -108:
                    err = func.func_name + 'TCP/IP connection was closed by an admin'
            return True, err

        return False, buf[1:]
