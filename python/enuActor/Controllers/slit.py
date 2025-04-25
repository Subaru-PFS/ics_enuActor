__author__ = 'alefur'

import logging
import socket
import time
from importlib import reload

import enuActor.Simulators.slit as simulator
import ics.utils.time as pfsTime
import numpy as np
from enuActor.drivers import hxp_drivers
from ics.utils.fsm.fsmThread import FSMThread
from twisted.internet import reactor

reload(simulator)


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

    @staticmethod
    def slitPosition(coords, config):
        """Interpret slit position from current coordinates."""
        # consider any nans or angle out of tolerance as undef.
        if any(np.isnan(coords)) or np.max(np.abs(coords[3:])) > config['positionTolerance']:
            return 'undef'

        # eerk
        [xPixToMm, yPixToMm] = config['pix_to_mm']

        posStr = []

        [focus, ditherY, ditherX, _, _, _] = coords
        if abs(focus) > config['positionTolerance']:
            sign = '+' if focus > 0 else '-'
            posStr.append(f'focus{sign}{round(abs(focus), 2)}mm')
        if abs(ditherX) > config['positionTolerance']:
            sign = '+' if ditherX > 0 else '-'
            posStr.append(f'ditherFib{sign}{round(abs(ditherX) / xPixToMm, 1)}pix')
        if abs(ditherY) > config['positionTolerance']:
            sign = '+' if ditherY > 0 else '-'
            posStr.append(f'ditherWav{sign}{round(abs(ditherY) / yPixToMm, 1)}pix')

        if posStr:
            # format correctly with space.
            return f'''"{' '.join(posStr)}"'''
        else:
            return 'home'

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
        :type name: str
        """
        substates = ['IDLE', 'MOVING', 'SLIDING', 'SHUTDOWN', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'slide', 'src': 'IDLE', 'dst': 'SLIDING'},
                  {'name': 'idle', 'src': ['MOVING', 'SLIDING', 'SHUTDOWN'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING', 'SLIDING', 'SHUTDOWN'], 'dst': 'FAILED'},
                  {'name': 'shutdown', 'src': ['IDLE'], 'dst': 'SHUTDOWN'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('MOVING', self.moving)
        self.addStateCB('SLIDING', self.sliding)

        self.sim = simulator.SlitSim()

        # Hexapod Attributes
        self.groupName = 'HEXAPOD'
        self.myxps = None
        self.socks = {'main': -1,
                      'emergency': -1,
                      'slitPosition': -1}

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)
        self.doPersist = False

    @property
    def simulated(self):
        """Return True if self.mode=='simulation', return False if self.mode='operation'."""
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    @property
    def hxpSoftwareLimits(self):
        return 'on' if self.softwareLimitsActivated else 'off'

    def _loadCfg(self, cmd, mode=None):
        """Load slit configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        self.coords = np.nan * np.ones(6)
        self.mode = self.controllerConfig['mode'] if mode is None else mode
        self.host = self.controllerConfig['host']
        self.port = self.controllerConfig['port']
        self.homeHexa = self.controllerConfig['home']
        self.slit_position = self.controllerConfig['slit_position']
        self.thicknessCarriage = self.controllerConfig['thicknessCarriage']
        self.lowerBounds = self.controllerConfig['lowerBounds']
        self.upperBounds = self.controllerConfig['upperBounds']

        self.workSystem = slit.convertToWorld([sum(i) for i in zip(self.homeHexa[:3],
                                                                   self.slit_position[:3])] + self.homeHexa[3:])
        # Set Tool to slit home coord instead of center of hexa
        tool = self.slit_position[:3] + self.workSystem[3:]
        tool = slit.convertToWorld(tool)[:3] + self.slit_position[3:]
        # Tool z = 21 + z_slit with 21 height of upper carriage
        self.toolSystem = [sum(i) for i in zip(tool, [0, 0, self.thicknessCarriage, 0, 0, 0])]
        self.hysteresisCorrection = np.array(self.controllerConfig['hysteresisCorrection'])
        # activate software limits by defaults.
        try:
            self.softwareLimitsActivated = self.controllerConfig['activateSoftwareLimits']
        except:
            self.softwareLimitsActivated = True

    def _openComm(self, cmd):
        """Open socket slit hexapod controller or simulate it.

        :param cmd: current command.
        :raise: socket.error if the communication has failed.
        """
        self.myxps = self.createSock()
        self.connectSock(sockName='main')
        self.connectSock(sockName='emergency')

    def _closeComm(self, cmd):
        """Close socket.

        :param cmd: current command.
        """
        self.closeSock(sockName='main')
        self.closeSock(sockName='emergency')

    def _testComm(self, cmd):
        """Test communication.

        :param cmd: current command.
        :raise: Exception if the communication has failed with the controller.
        """
        self.checkPosition(cmd)

    def _init(self, cmd, doHome=True):
        """Initialise hexapod:

        - kill socket
        - init hxp
        - search home
        - set work and tool coordinate system
        - go home

        :param cmd: current command.
        :param doHome: if true requesting homeSearch.
        :type doHome: bool
        :raise: Exception with warning message.
        """
        # Make sure that the outside world knows that the axis positions are soon to be invalid.
        # There are many failures out of the loop, so declare now.
        self.declareNewHexapodPosition(cmd, invalid=True)

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
        self.doPersist = True

    def getStatus(self, cmd):
        """Get status and generates slit keywords.

        :param cmd: current command.
        """
        self.checkPosition(cmd=cmd)
        self.checkStatus(cmd=cmd)

    def checkPosition(self, cmd):
        """Get 6-tuple current coordinates, generate slit and slitPosition keywords.

        :param cmd: current command.
        """
        self.coords = [np.nan] * 6

        try:
            self.coords = self._getCurrentPosition()
            self.declareNewHexapodPosition(cmd)

        finally:
            genKeys = cmd.inform if np.nan not in self.coords else cmd.warn
            genKeys('slit=%s' % ','.join(['%.5f' % p for p in self.coords]))
            genKeys('slitPosition=%s' % self.slitPosition(self.coords, config=self.controllerConfig))

    def checkStatus(self, cmd, sockName='main'):
        """
        Retrieve and report the current status of the hexapod controller.

        This method:
        - Queries the hexapod status code and interprets it as a human-readable string.
        - Sends this information to the commander via `cmd.inform()`.
        - Also informs the current software limits state.

        Parameters
        ----------
        cmd :
            Command object used to report status back to the user.
        sockName : str, optional
            Socket name to use for communication with the controller (default: 'main').
        """
        hxpStatus = self._getHxpStatus(sockName=sockName)
        cmd.inform('hxpStatus=%d,"%s"' % (int(hxpStatus), self._getHxpStatusString(hxpStatus, sockName=sockName)))
        cmd.inform(f'hxpSoftwareLimits={self.hxpSoftwareLimits}')

    def moving(self, cmd, reference, coords):
        """Move to coords in the reference.

        :param cmd: current command.
        :param reference: 'absolute' or 'relative'.
        :param coords: [x, y, z, u, v, w].
        :type reference: str
        :type coords: list
        :raise: Exception with warning message.
        """
        self.doPersist = True
        try:
            if reference == 'absolute':
                # First check if desired position is within range.
                self._checkHexaLimits(coords)
                # Then move to the desired position + the hysteresis correction.
                self._hexapodMoveAbsolute(np.array(coords) + self.hysteresisCorrection)
                self.checkPosition(cmd)
                # then move to the desired position.
                return self._hexapodMoveAbsolute(coords)
            else:
                return self._hexapodMoveIncremental('Work', coords)
        except UserWarning:
            self.doPersist = False
            raise

    def sliding(self, cmd, speed, startPosition, coords):
        """Move to coords in the reference.
        :param cmd: current command.
        :param speed: mm/s
        :param totalMotion:
        :raise: Exception with warning message.
        """

        def waitToReachStartPosition():
            if not self.substates.current == 'SLIDING':
                return

            [x, y, z, u, v, w] = self.errorChecker(self.myxps.GroupPositionCurrentGet, self.groupName, 6,
                                                   sockName='slitPosition')
            direction = 1 if speed > 0 else -1

            # wait until you reach desired startPosition
            while direction * (z - startPosition) < 0:
                [x, y, z, u, v, w] = self.errorChecker(self.myxps.GroupPositionCurrentGet, self.groupName, 6,
                                                       sockName='slitPosition')
                time.sleep(0.01)

            self.coords = [x, y, z, u, v, w]

            cmd.inform('slitAtSpeed=True')
            cmd.inform('slit=%s' % ','.join(['%.5f' % p for p in self.coords]))
            cmd.inform('slitPosition=%s' % self.slitPosition(self.coords, config=self.controllerConfig))

            self.closeSock(sockName='slitPosition')

        reactor.callLater(1, waitToReachStartPosition)

        ret = self._HexapodMoveIncrementalControlWithTargetVelocity(*coords[:3], abs(speed))
        cmd.inform('slitAtSpeed=False')

        return ret

    def shutdown(self, cmd):
        """Save current controller position and kill connection.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self.doPersist = True

        cmd.inform('text="Kill and save hexapod position..."')
        self._TCLScriptExecute('KillWithRegistration.tcl')

        # the script actually return immediately, so we need to wait, pretty ugly but has been proven to work...
        time.sleep(10)

    def getSystem(self, cmd, system):
        """Get system from the controller and update the actor's current value.

        :param system: Work|Tool|Base.
        :type system: str
        :return:  [x, y, z, u, v, w] coordinate system definition.
        :raise: ValueError if the coordinate system does not exist
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
        """Send new coordinate system to the controller.

        :param system: Work|Tool.
        :param coords: [x, y, z, u, v, w].
        :type system: str
        :type coords: list
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self._hexapodCoordinateSysSet(system, coords)

    def motionEnable(self, cmd):
        """Enabling hexapod actuators.

        :param cmd: current command.
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        self.doPersist = True
        cmd.inform('text="Enabling Slit controller..."')
        self._hexapodEnable()

    def motionDisable(self, cmd):
        """Disabling hexapod actuators.

        :param cmd: current command.
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        self.doPersist = True
        cmd.inform('text="Disabling Slit controller..."')
        self._hexapodDisable()

    def declareNewHexapodPosition(self, cmd=None, invalid=False):
        """Called when hexapod has been moved, homed, shutdown...

        Args
        ----
        cmd : `Command`
          Where to send keywords.
        invalid : `bool`
          Whether the current positions are trash/unknown.
          Used right before homing.

        For now we just generate the MHS keyword which declares that the
        old motor positions have been invalidated.
        """
        if invalid:
            self.doPersist = True

        if not self.doPersist:
            return

        coords = ['nan'] * 6 if invalid else self.coords
        coords = [float(c) for c in coords]
        # Use MJD seconds.
        now = float(pfsTime.Time.now().mjd)

        self.actor.actorData.persistKey('slit', *coords)
        self.actor.actorData.persistKey('hexapodMoved', now)
        self.doPersist = False

        cmd = self.actor.bcast if cmd is None else cmd

        cmd.inform(f'hexapodMoved={now:0.6f}')

    def doAbort(self, cmd):
        """
        Execute an abort sequence to stop the hexapod and check its status.

        This function:
        - Informs the user that motion is being aborted.
        - Attempts to call `_abort()` to stop motion.
        - Catches and reports any exception raised during the abort.
        - Finally checks and reports the hexapod status and waits for the FSM to clear.

        Parameters
        ----------
        cmd :
            Command object used to report status and errors to the user.

        Raises
        ------
        RuntimeError
            If `_abort()` or the status check fails.
        """
        cmd.inform('text="aborting motion..."')
        try:
            self._abort()
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        # Check status after abort
        self.checkStatus(cmd, sockName='emergency')

        # Wait for command to fully terminate (FSM integration)
        self.waitForCommandToFinish()

    def leaveCleanly(self, cmd):
        """Aborting current move.

        :param cmd: current command.
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        self.monitor = 0
        self.doAbort(cmd)

        if self.substates.current == 'SHUTDOWN':
            self.shutdown(cmd)

        try:
            self.getStatus(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self._closeComm(cmd=cmd)

    def _getCurrentPosition(self):
        """Get current position.

        :return: position [x, y, z, u, v, w].
        :rtype: list
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.GroupPositionCurrentGet, self.groupName, 6)

    def _getHxpStatus(self, sockName='main'):
        """
        Query the raw numeric status code of the hexapod controller.

        This value is useful for programmatic checks of hexapod state, such as whether it's moving,
        homed, or in an error condition.

        Parameters
        ----------
        sockName : str, optional
            Socket name to use for communication (default: 'main').

        Returns
        -------
        int
            Numeric status code returned by the controller.

        Raises
        ------
        RuntimeError
            If the controller returns an error or if communication fails.
        """
        return self.errorChecker(self.myxps.GroupStatusGet, self.groupName, sockName=sockName)

    def _getHxpStatusString(self, code, sockName='main'):
        """
        Translate a numeric hexapod status code into a descriptive string.

        Parameters
        ----------
        code : int
            Numeric status code returned by the controller (e.g. 11, 12).
        sockName : str, optional
            Socket name to use for communication (default: 'main').

        Returns
        -------
        str
            Human-readable description of the hexapod status.

        Raises
        ------
        RuntimeError
            If the controller returns an error or if communication fails.
        """
        return self.errorChecker(self.myxps.GroupStatusStringGet, code, sockName=sockName)

    def _kill(self):
        """Kill socket.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.GroupKill, self.groupName)

    def _initialize(self):
        """Initialize communication.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.GroupInitialize, self.groupName)

    def _homeSearch(self):
        """Home searching.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.GroupHomeSearch, self.groupName)

    def _hexapodCoordinateSysGet(self, coordSystem):
        """Get coordinates system definition from hexapod memory.

        :param coordSystem: Work|Tool
        :type coordSystem: str
        :rtype: list
        :return: coordSystem [x, y, z, u, v, w]
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.HexapodCoordinateSystemGet, self.groupName, coordSystem)

    def _hexapodCoordinateSysSet(self, coordSystem, coords):
        """Set coordinates system from parameters.

        :param coordSystem: Work|Tool
        :param coords: [x, y, z, u, v, w]
        :type coords: list
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.HexapodCoordinateSystemSet, self.groupName, coordSystem,
                                 *coords)

    def _hexapodMoveAbsolute(self, absCoords):
        """
        Move hexapod in absolute.
        In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        Therefore software limits are set to prevent any risk of collision.

        :param coords: [x, y, z, u, v, w].
        :type coords: list
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        self._checkHexaLimits(absCoords)
        return self.errorChecker(self.myxps.HexapodMoveAbsolute, self.groupName, 'Work', *absCoords)

    def _hexapodMoveIncremental(self, coordSystem, relCoords):
        """
        Move hexapod in relative.
        In our application, hexapod has a smaller range of motion due to the mechanical interfaces.
        Therefore software limits are set to prevent any risk of collision.

        :param coords: [x, y, z, u, v, w].
        :type coords: list
        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        futureCoords = np.array(self.coords) + np.array(relCoords)
        self._checkHexaLimits(futureCoords)

        return self.errorChecker(self.myxps.HexapodMoveIncremental, self.groupName, coordSystem,
                                 *relCoords)

    def _hexapodDisable(self):
        """Disable hexapod.

        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.GroupMotionDisable, self.groupName)

    def _hexapodEnable(self):
        """Enable hexapod.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.GroupMotionEnable, self.groupName)

    def _initializeFromRegistration(self):
        """Initialize hexapod from saved position.

        :return: ''
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self._TCLScriptExecute('InitializeFromRegistration.tcl')

    def _TCLScriptExecute(self, fileName, taskName='0', parametersList='0'):
        """Execute TCL Script and wait for return.

        :param fileName: filename.
        :raise: RuntimeError if an error is raised by errorChecker.
        :return: ''.
        """
        return self.errorChecker(self.myxps.TCLScriptExecuteAndWait, fileName, taskName, parametersList)

    def _HexapodMoveIncrementalControlWithTargetVelocity(self, dX, dY, dZ, Velocity):
        """Linear trajectory in work coordinate system.
        :raise: RuntimeError if an error is raised by errorChecker.
        """
        return self.errorChecker(self.myxps.HexapodMoveIncrementalControlWithTargetVelocity,
                                 self.groupName, 'Work', 'Line', dX, dY, dZ, Velocity)

    def _abort(self):
        """
        Abort the current hexapod motion immediately.

        This sends a GroupMoveAbort command to the hexapod controller over the emergency socket.
        If the hexapod was not moving, an informational message is logged instead of raising an error.

        Raises
        ------
        RuntimeError
            If the controller returns an error or if communication fails.
        """
        ret = self.errorChecker(self.myxps.GroupMoveAbort, self.groupName, sockName='emergency',
                                handleDeviceError=False)

        if ret == -22:
            self.logger.info("Hexapod was not moving — no need to stop (Error -22: Not allowed action).")

    def _checkHexaLimits(self, futureCoords):
        """Check hexapod future coordinates.
        :return: ''
        :raise: UserWarning if a coord exceed
        """
        if not self.softwareLimitsActivated:
            return

        for lim_inf, lim_sup, coord in zip(self.lowerBounds, self.upperBounds, futureCoords):
            if not lim_inf <= coord <= lim_sup:
                raise UserWarning("[X, Y, Z, U, V, W] exceed : %.5f not permitted" % coord)

    def errorChecker(self, func, *args, sockName='main', handleDeviceError=True):
        """
        Execute a driver-level function with structured error handling for Newport HXP100Meca controllers.

        This method:
        - Connects to the specified socket.
        - Executes the provided function with arguments.
        - Handles known controller initialization delays.
        - Detects and raises exceptions for common network or device-level errors.
        - Optionally skips device error decoding based on the `handleDeviceError` flag.

        Parameters
        ----------
        func : callable
            The low-level controller function to invoke. Must return a response buffer
            where the first element is an error code (0 if no error).
        *args : tuple
            Arguments passed directly to `func`.
        sockName : str, optional
            Name of the controller socket to use (default: 'main').
        handleDeviceError : bool, optional
            Whether to decode and raise detailed device-level errors (default: True).

        Returns
        -------
        Any
            The result from the function call (excluding the error code), either a scalar or a tuple.

        Raises
        ------
        RuntimeError
            For unrecoverable communication or device errors.
        UserWarning
            For expected device limits or user-level constraints (e.g., motion bounds exceeded).
        """
        socketId = self.connectSock(sockName)
        buf = func(socketId, *args)

        errorCode = buf[0]

        # no error are reported, just return the buffer.
        if not errorCode:
            return buf[1:] if len(buf) > 2 else buf[1]

        # Retry if controller still initializing
        if errorCode == -21:
            self.logger.debug('Hxp controller in initialization...')
            time.sleep(2)
            return self.errorChecker(func, *args, sockName=sockName)

        # checking for network error.
        self._handleNetworkErrors(errorCode, sockName, func.__name__)

        if handleDeviceError:
            self._handleDeviceErrors(errorCode, socketId, func.__name__)

        return errorCode

    def _handleNetworkErrors(self, errorCode, sockName, funcName):
        """
        Handle low-level network-related errors from the hexapod controller.

        This method handles cases such as TCP timeout or closed connections
        and raises appropriate exceptions. It also ensures the associated socket is closed.

        Parameters
        ----------
        errorCode : int
            Error code returned from the driver function.
        sockName : str
            Identifier of the socket connection (e.g., 'main').
        funcName : str
            Name of the function being executed (for error context).

        Raises
        ------
        RuntimeError
            Raised with a descriptive message for known network error codes.
        """
        if errorCode == -2:
            self.closeSock(sockName)
            raise RuntimeError(f"{funcName}: TCP timeout")
        elif errorCode == -108:
            self.closeSock(sockName)
            raise RuntimeError(f"{funcName}: TCP/IP connection was closed by an admin")

    def _handleDeviceErrors(self, errorCode, socketId, funcName):
        """
        Handle device-level errors returned by the hexapod controller.

        This method interprets known hardware-related error codes, retrieves
        the corresponding error message using `ErrorStringGet`, and raises
        appropriate exceptions with detailed context.

        Parameters
        ----------
        errorCode : int
            Error code returned by the hardware function.
        socketId : int
            Socket ID used to communicate with the controller.
        funcName : str
            Name of the function being checked (for clearer error messages).

        Raises
        ------
        UserWarning
            For recoverable or expected hardware limits (e.g., motion bounds or velocity limits).
        RuntimeError
            For unexpected or generic device-level errors.
        """
        errorStatus, errorStr = self.myxps.ErrorStringGet(socketId, errorCode)

        if errorCode == -17:
            raise UserWarning(f'{funcName}: [X, Y, Z, U, V, W] exceed — {errorStr}')
        elif errorCode == -76:
            raise UserWarning(f'{funcName}: Target velocity out of range')
        elif errorCode == -27:
            raise UserWarning(f'{funcName}: Error -27 : Move Aborted')
        elif errorStatus != 0:
            raise RuntimeError(f"{funcName}: failed with code {errorCode}")
        else:
            raise RuntimeError(f"{funcName}: {errorStr}")

    def connectSock(self, sockName):
        """Connect socket using hexapod drivers.

        :param sockName: socketName to connect.
        :type sockName: str
        :raise: socket.error if connection fails
        """
        if self.socks[sockName] == -1:
            socketId = self.myxps.TCP_ConnectToServer(self.host, self.port, slit.timeout)

            if socketId == -1:
                raise socket.error('Connection to Hexapod failed check IP & Port')

            self.socks[sockName] = socketId

        return self.socks[sockName]

    def closeSock(self, sockName='main'):
        """close socket.

        :param sockName: socketName to close.
        :type sockName: str
        """
        socketId = self.socks[sockName]

        self.socks[sockName] = -1
        self.myxps.TCP_CloseSocket(socketId)

    def createSock(self):
        """create socket in operation, simulator otherwise."""
        if self.simulated:
            s = self.sim
        else:
            s = hxp_drivers.XPS()

        return s
