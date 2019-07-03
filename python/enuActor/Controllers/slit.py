__author__ = 'alefur'
import logging
import socket

import numpy as np
from enuActor.Simulators.slit import SlitSim
from enuActor.drivers import hxp_drivers
from enuActor.utils.fsmThread import FSMThread


class slit(FSMThread):
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
        substates = ['IDLE', 'MOVING', 'SHUTDOWN', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'idle', 'src': ['MOVING', 'SHUTDOWN'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING', 'SHUTDOWN'], 'dst': 'FAILED'},
                  {'name': 'shutdown', 'src': ['IDLE'], 'dst': 'SHUTDOWN'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=False)

        self.addStateCB('MOVING', self.moving)
        self.addStateCB('SHUTDOWN', self.shutdown)
        self.sim = SlitSim()

        # Hexapod Attributes
        self.groupName = 'HEXAPOD'
        self.myxps = None
        self.socks = {'main': -1,
                      'emergency': -1}

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

    @property
    def position(self):
        delta = np.sum(np.abs(np.zeros(6) - self.coords))
        if ~np.isnan(delta) and delta < 0.005:
            return 'home'
        else:
            return 'undef'

    def disconnect(self):
        self.actor.callCommand('disconnect controller=%s' % self.name)

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by FSMDev.loadDevice().
        | Convert to world tool and home.

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: RuntimeError Config file badly formatted
        """
        self.coords = np.nan * np.ones(6)
        self.mode = self.actor.config.get('slit', 'mode') if mode is None else mode
        self.host = self.actor.config.get('slit', 'host')
        self.port = int(self.actor.config.get('slit', 'port'))
        self.homeHexa = [float(val) for val in self.actor.config.get('slit', 'home').split(',')]
        self.slit_position = [float(val) for val in self.actor.config.get('slit', 'slit_position').split(',')]
        self.thicknessCarriage = float(self.actor.config.get('slit', 'thicknessCarriage'))
        self.lowerBounds = [float(val) for val in self.actor.config.get('slit', 'lowerBounds').split(',')]
        self.upperBounds = [float(val) for val in self.actor.config.get('slit', 'upperBounds').split(',')]

        self.workSystem = slit.convertToWorld([sum(i) for i in zip(self.homeHexa[:3],
                                                                   self.slit_position[:3])] + self.homeHexa[3:])
        # Set Tool to slit home coord instead of center of hexa
        tool = self.slit_position[:3] + self.workSystem[3:]
        tool = slit.convertToWorld(tool)[:3] + self.slit_position[3:]
        # Tool z = 21 + z_slit with 21 height of upper carriage
        self.toolSystem = [sum(i) for i in zip(tool, [0, 0, self.thicknessCarriage, 0, 0, 0])]

    def _openComm(self, cmd):
        """| Open socket with hexapod controller or simulate it.
        | Called by FSMDev.loadDevice()

        :param cmd: on going command
        :raise: socket.error if the communication has failed with the controller
        """
        self.myxps = self.createSock()
        self.connectSock(sockName='main')
        self.connectSock(sockName='emergency')

    def _closeComm(self, cmd):
        """| Close communication.
        | Called by FSMThread.stop()

        :param cmd: on going command
        """
        self.closeSock(sockName='main')
        self.closeSock(sockName='emergency')

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: RuntimeError if the communication has failed with the controller
        """
        self.checkPosition(cmd)

    def _init(self, cmd, doHome=True):
        """| Initialise hexapod, called by self.initDevice().

        - kill socket
        - init hxp
        - search home
        - set home and tool system
        - go home

        :param cmd: on going command
        :param doHome: requesting homeSearch
        :type doHome:bool
        :raise: RuntimeError if a command fail, user if warned with error
        """
        hxpStatus = int(self._getHxpStatus())
        if doHome:
            cmd.inform('text="killing existing socket..."')
            self._kill()

            cmd.inform('text="initialising hxp..."')
            self._initialize()

            cmd.inform('text="seeking home ..."')
            self._homeSearch()

        else:
            if hxpStatus in [0, 7]:
                cmd.inform('text="initializing from saved position..."')
                self._initializeFromRegistration()

            elif hxpStatus in [10, 11, 12, 13, 14, 15, 16, 17, 18]:
                cmd.inform('text="hxp is ready..."')

            elif hxpStatus == 20:
                self.motionEnable(cmd=cmd)

            else:
                raise RuntimeError('hxp needs to be fully initialize')

        self._hexapodCoordinateSysSet('Work', self.workSystem)
        self.getSystem(cmd, 'Work')

        self._hexapodCoordinateSysSet('Tool', self.toolSystem)
        self.getSystem(cmd, 'Tool')

        if int(self._getHxpStatus()) not in [10, 11, 12, 13, 14, 15, 16, 17, 18]:
            raise RuntimeError('hexapod not in ready state, going home aborted ...')

        cmd.inform('text="going to home ..."')
        self._hexapodMoveAbsolute([0, 0, 0, 0, 0, 0])

    def getStatus(self, cmd):
        """| Get status from the controller and generates slit keywords.

        - slit = state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
        - slitInfo = str : *an interpreted status returned by the controller*

        :param cmd: on going command
        """
        self.checkPosition(cmd=cmd)
        self.checkStatus(cmd=cmd)

    def checkPosition(self, cmd):
        """| Get current coordinates from the controller and generate slit position.

        :param cmd: on going command
        """
        self.coords = [np.nan] * 6

        try:
            self.coords = self._getCurrentPosition()
        finally:
            genKeys = cmd.inform if np.nan not in self.coords else cmd.warn
            genKeys('slit=%s' % ','.join(['%.5f' % p for p in self.coords]))
            genKeys('slitPosition=%s' % self.position)

    def checkStatus(self, cmd):
        """|  Get status from hxp100 controller

        :param cmd: on going command
        """
        hxpStatus = self._getHxpStatus()
        cmd.inform('hxpStatus=%d,"%s' % (int(hxpStatus), self._getHxpStatusString(hxpStatus)))

    def moving(self, cmd, reference, coords):
        """| Move to coords in the reference,

        :param cmd: on going command
        :param reference: 'absolute' or 'relative'
        :param coords: [x, y, z, u, v, w]
        :type reference: str
        :type coords: list
        :raise: RuntimeError if move command fails
        """
        if reference == 'absolute':
            ret = self._hexapodMoveAbsolute(coords)
        elif reference == 'relative':
            ret = self._hexapodMoveIncremental('Work', coords)
        else:
            raise ValueError('unknown ref')

    def shutdown(self, cmd):
        """| Save current controller position

        :param cmd: on going command
        :raise: RuntimeError if TCLScriptExecute fails
                """
        cmd.inform('text="Kill and save hexapod position..."')
        self._TCLScriptExecute('KillWithRegistration.tcl')

    def getSystem(self, cmd, system):
        """| Get system from the controller and update the actor's current value.

        :param system: Work|Tool|Base
        :type system: str
        :return:  [x, y, z, u, v, w] coordinate system definition
        :raise: RuntimeError if the coordinate system does not exist
        """
        ret = self._hexapodCoordinateSysGet(system)
        if system == 'Work':
            self.workSystem = ret
        elif system == 'Tool':
            self.toolSystem = ret
        elif system == 'Base':
            pass
        else:
            raise ValueError('system : %s does not exist' % system)

        cmd.inform('slit%s=%s' % (system, ','.join(['%.5f' % p for p in ret])))
        return ret

    def setSystem(self, system, coords):
        """| Send new coordinate system to the controller

        :param system: Work|Tool
        :param coords: [x, y, z, u, v, w]
        :type system: str
        :type coords: list
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self._hexapodCoordinateSysSet(system, coords)

    def motionEnable(self, cmd):
        """| Enabling controller actuators

        :param cmd: on going command:
        :raise: RuntimeError if an error is raised by errorChecker
        """
        cmd.inform('text="Enabling Slit controller..."')
        self._hexapodEnable()

    def motionDisable(self, cmd):
        """| Disabling controller actuators

        :param cmd: on going command:
        :raise: RuntimeError if an error is raised by errorChecker
        """
        cmd.inform('text="Disabling Slit controller..."')
        self._hexapodDisable()

    def abort(self, cmd):
        """| Aborting current move

        :param cmd: on going command:
        :raise: RuntimeError if an error is raised by errorChecker
        """
        cmd.inform('text="aborting move..._"')
        self._abort()

    def _getCurrentPosition(self):
        """| Get current position.

        :return: position [x, y, z, u, v, w]
        :rtype: list
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupPositionCurrentGet, self.groupName, 6)

    def _getHxpStatus(self):
        """| Get hexapod status as an integer.

        :return: error code
        :rtype: int
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupStatusGet, self.groupName)

    def _getHxpStatusString(self, code):
        """| Get hexapod status interpreted as a string.

        :param code: error code
        :return: status_string
        :rtype: str
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupStatusStringGet, code)

    def _kill(self):
        """| Kill socket.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupKill, self.groupName)

    def _initialize(self):
        """| Initialize communication.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupInitialize, self.groupName)

    def _homeSearch(self):
        """| Home searching.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupHomeSearch, self.groupName)

    def _hexapodCoordinateSysGet(self, coordSystem):
        """| Get coordinates system definition from hexapod memory.

        :param coordSystem: Work|Tool
        :type coordSystem: str
        :rtype: list
        :return: coordSystem [x, y, z, u, v, w]
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.HexapodCoordinateSystemGet, self.groupName, coordSystem)

    def _hexapodCoordinateSysSet(self, coordSystem, coords):
        """| Set coordinates system from parameters.

        :param coordSystem: Work|Tool
        :param coords: [x, y, z, u, v, w]
        :type coords: list
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.HexapodCoordinateSystemSet, self.groupName, coordSystem,
                                 *coords)

    def _hexapodMoveAbsolute(self, absCoords):
        """| Move hexapod in absolute.
        | In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        | Software limits are set to prevent any risk of collision.

        :param coords: [x, y, z, u, v, w].
        :type coords: list
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        for lim_inf, lim_sup, coord in zip(self.lowerBounds, self.upperBounds, absCoords):
            if not lim_inf <= coord <= lim_sup:
                raise UserWarning("[X, Y, Z, U, V, W] exceed : %.5f not permitted" % coord)

        return self.errorChecker(self.myxps.HexapodMoveAbsolute, self.groupName, 'Work', *absCoords)

    def _hexapodMoveIncremental(self, coordSystem, relCoords):
        """| Move hexapod in relative.
        | In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        | Therefore software limits are set to prevent any risk of collision.

        :param coords: [x, y, z, u, v, w]
        :type coords: list
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        for lim_inf, lim_sup, relCoord, coord in zip(self.lowerBounds, self.upperBounds, relCoords, self.coords):
            if not lim_inf <= relCoord + coord <= lim_sup:
                raise UserWarning("[X, Y, Z, U, V, W] exceed : %.5f not permitted" % (relCoord + coord))

        return self.errorChecker(self.myxps.HexapodMoveIncremental, self.groupName, coordSystem,
                                 *relCoords)

    def _hexapodDisable(self):
        """| Disable hexapod.
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupMotionDisable, self.groupName)

    def _hexapodEnable(self):
        """| Enable hexapod.
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupMotionEnable, self.groupName)

    def _initializeFromRegistration(self):
        """| Initialize hexapod from saved position
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self._TCLScriptExecute('InitializeFromRegistration.tcl')

    def _TCLScriptExecute(self, fileName, taskName='0', parametersList='0'):
        """| Execute TCL Script and wait for return
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.TCLScriptExecuteAndWait, fileName, taskName, parametersList)

    def _abort(self):
        """| Abort current motion
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker
        """
        return self.errorChecker(self.myxps.GroupMoveAbort, self.groupName, sockName='emergency')

    def errorChecker(self, func, *args, sockName='main'):
        """| Decorator for slit lower level functions.

        :param func: function to check
        :param args: function arguments
        :returns: ret
        :rtype: str
        :raise: RuntimeError if an error is returned by hxp drivers
        """

        socketId = self.connectSock(sockName)

        buf = func(socketId, *args)
        if buf[0] != 0:
            if buf[0] == -2:
                self.closeSock(sockName)
                raise RuntimeError(func.__name__ + 'TCP timeout')

            elif buf[0] == -108:
                self.closeSock(sockName)
                raise RuntimeError(func.__name__ + 'TCP/IP connection was closed by an admin')

            else:
                [errorCode, errorString] = self.myxps.ErrorStringGet(socketId, buf[0])
                if buf[0] == -17:
                    raise UserWarning('[X, Y, Z, U, V, W] exceed : %s' % errorString)
                elif errorCode != 0:
                    raise RuntimeError(func.__name__ + ' : ERROR ' + str(errorCode))
                else:
                    raise RuntimeError(func.__name__ + ' : ' + errorString)

        return buf[1:] if len(buf) > 2 else buf[1]

    def connectSock(self, sockName):
        if self.socks[sockName] == -1:
            socketId = self.myxps.TCP_ConnectToServer(self.host, self.port, slit.timeout)

            if socketId == -1:
                raise socket.error('Connection to Hexapod failed check IP & Port')

            self.socks[sockName] = socketId

        return self.socks[sockName]

    def closeSock(self, sockName='main'):
        socketId = self.socks[sockName]

        self.socks[sockName] = -1
        self.myxps.TCP_CloseSocket(socketId)

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = hxp_drivers.XPS()

        return s
