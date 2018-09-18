__author__ = 'alefur'
import logging

import numpy as np
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.drivers import hxp_drivers
from enuActor.simulator.slit_simu import SlitSim
import socket


class slit(FSMDev, QThread):
    timeout = 2

    @staticmethod
    def convertToWorld(array):
        def degToRad(deg):
            return 2 * np.pi * deg / 360

        [X, Y, Z, U, V, W] = array
        x = X * np.cos(degToRad(W)) - Y * np.sin(degToRad(W))
        y = X * np.sin(degToRad(W)) + Y * np.cos(degToRad(W))
        return [round(x, 5), round(y, 5), float(Z), float(U), float(V), float(W)]

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        substates = ['IDLE', 'MOVING', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'idle', 'src': ['MOVING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING'], 'dst': 'FAILED'},
                  ]

        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('MOVING', self.moveTo)

        # Hexapod Attributes
        self.groupName = 'HEXAPOD'
        self.myxps = None
        self.socketId = None

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    def start(self, cmd=None, doInit=False, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice().
        | Convert to world tool and home.

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.coords = np.nan * np.ones(6)

        self.mode = self.actor.config.get('slit', 'mode') if mode is None else mode
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

    def startComm(self, cmd):
        """| Start socket with the hexapod controller or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        self.sim = SlitSim()  # Create new simulator

        self.myxps = self.createSock()
        self.socketId = self.myxps.TCP_ConnectToServer(self.host, self.port, slit.timeout)

        if self.socketId == -1:
            raise socket.error('Connection to Hexapod failed check IP & Port')

        self.getPosition(cmd=cmd)

    def init(self, cmd):
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

    def getStatus(self, cmd):
        """| Get status from the controller and publish slit keywords.

        - slit = state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
        - slitInfo = str : *an interpreted status returned by the controller*

        :param cmd: on going command
        :param doFinish: if True finish the command
        """

        cmd.inform('slitFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('slitMode=%s' % self.mode)

        if self.states.current in ['LOADED', 'ONLINE']:
            self.getPosition(cmd=cmd)

            cmd.inform('slitInfo="%s"' % self._getHxpStatusString(self._getHxpStatus()))
            cmd.inform('slitLocation=%s' % self.location)

        cmd.finish()

    def getPosition(self, cmd):
        try:
            self.coords = self._getCurrentPosition()
        except:
            self.coords = np.nan * np.ones(6)
            cmd.warn("slit=%s" % ','.join(["%.5f" % p for p in self.coords]))
            cmd.warn('slitLocation=undef')
            raise

        cmd.inform("slit=%s" % ','.join(["%.5f" % p for p in self.coords]))

    def moveTo(self, e):
        """|
        | Move to coords in the reference,

        :param cmd: on going command
        :param reference: 'absolute' or 'relative'
        :param coords: [x, y, z, u, v, w]
        :type reference: str
        :type coords: list
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False if the command fail,fsm (BUSY => FAILED)
        """

        cmd, reference, coords = e.cmd, e.reference, e.coords
        try:
            if reference == 'absolute':
                ret = self._hexapodMoveAbsolute(coords)

            elif reference == 'relative':
                ret = self._hexapodMoveIncremental('Work', coords)

        except UserWarning:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        except:
            self.substates.fail()
            raise

        self.substates.idle()

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
            raise ValueError("system : %s does not exist" % system)

        return ret

    def setSystem(self, system, coords):
        """| Send new coordinate system to the controller

        :param system: Work|Tool
        :param coords: [x, y, z, u, v, w]
        :type system: str
        :type coords: list
        :raise: Exception if an error is raised by errorChecker
        """
        return self._hexapodCoordinateSysSet(system, coords)

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
        delta = np.sum(np.abs(np.zeros(6) - self.coords))
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

    def _hexapodCoordinateSysSet(self, coordSystem, coords):
        """| Set coordinates system from parameters.

        :param coordSystem: Work|Tool
        :param coords: [x, y, z, u, v, w]
        :type coords: list
        :return: ''
        :raise: Exception if an error occured
        """

        return self.errorChecker(self.myxps.HexapodCoordinateSystemSet, self.socketId, self.groupName, coordSystem,
                                 *coords)

    def _hexapodMoveAbsolute(self, absCoords):
        """| Move hexapod in absolute.
        | In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        | Software limits are set to prevent any risk of collision.

        :param coords: [x, y, z, u, v, w].
        :type coords: list
        :return: ''
        :raise: Exception if an error occured
        """

        for lim_inf, lim_sup, coord in zip(self.lowerBounds, self.upperBounds, absCoords):
            if not lim_inf <= coord <= lim_sup:
                raise UserWarning("[X, Y, Z, U, V, W] exceed : %.5f not permitted" % coord)

        return self.errorChecker(self.myxps.HexapodMoveAbsolute, self.socketId, self.groupName, 'Work', *absCoords)

    def _hexapodMoveIncremental(self, coordSystem, relCoords):
        """| Move hexapod in relative.
        | In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        | Therefore software limit are set to prevent any risk of collision.

        :param coords: [x, y, z, u, v, w]
        :type coords: list
        :return: ''
        :raise: Exception if an error occured
        """

        for lim_inf, lim_sup, relCoord, coord in zip(self.lowerBounds, self.upperBounds, relCoords, self.coords):
            if not lim_inf <= relCoord + coord <= lim_sup:
                raise UserWarning("[X, Y, Z, U, V, W] exceed : %.5f not permitted" % (relCoord + coord))

        return self.errorChecker(self.myxps.HexapodMoveIncremental, self.socketId, self.groupName, coordSystem,
                                 *relCoords)

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
                raise Exception(func.__name__ + 'TCP timeout')
            elif buf[0] == -108:
                raise Exception(func.__name__ + 'TCP/IP connection was closed by an admin')
            else:
                [errorCode, errorString] = self.myxps.ErrorStringGet(self.socketId, buf[0])
                if buf[0] == -17:
                    raise UserWarning("[X, Y, Z, U, V, W] exceed : %s" % errorString)
                elif errorCode != 0:
                    raise Exception(func.__name__ + ' : ERROR ' + str(errorCode))
                else:
                    raise Exception(func.__name__ + ' : ' + errorString)

        return buf[1:] if len(buf) > 2 else buf[1]

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = hxp_drivers.XPS()

        return s

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
