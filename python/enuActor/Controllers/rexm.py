import copy
import logging
import time

import ics.utils.tcp.bufferedSocket as bufferedSocket
import numpy as np
from astropy import time as astroTime
from enuActor.Simulators.rexm import RexmSim
from enuActor.drivers.rexm_drivers import recvPacket, TMCM
from ics.utils.fsm.fsmThread import FSMThread


class rexm(FSMThread, bufferedSocket.EthComm):
    travellingTimeout = 150
    stoppingTimeout = 5
    startingTimeout = 3

    switch = {(1, 0): 'low', (0, 1): 'med', (0, 0): 'undef', (1, 1): 'error'}
    toPos = {0: 'low', 1: 'med'}
    toDir = {'low': 0, 'med': 1}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
        :type name: str
        """
        substates = ['IDLE', 'MOVING', 'FAILED', 'SAFESTOP']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'safestop', 'src': 'IDLE', 'dst': 'SAFESTOP'},
                  {'name': 'idle', 'src': ['MOVING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING'], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('MOVING', self.moving)
        self.sim = RexmSim()

        self.switchA = 0
        self.switchB = 0
        self.speed = 0
        self.abortMotion = False
        self.forcePersistedPosition = False

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

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
    def position(self):
        current = self.positionFromSwitch

        if current == 'undef' and (self.brokenLimitSwitches or self.forcePersistedPosition):
            current = self.persisted

        elif current == 'error' and self.forcePersistedPosition:
            current = self.persisted

        return current

    @property
    def positionFromSwitch(self):
        """Interpret rexm current position from limit switches state."""
        return rexm.switch[self.switchA, self.switchB]

    @property
    def isMoving(self):
        """True if self.speed>0 else False."""
        return 1 if abs(self.speed) > 0 else 0

    @property
    def pulseDivisor(self):
        """The exponent of the scaling factor for the pulse (step) generator."""
        return self.motorConfig[154]

    @property
    def stepIdx(self):
        """Microstep resolution"""
        return self.motorConfig[140]

    @property
    def persisted(self):
        try:
            position, = self.actor.instData.loadKey('rexm')
        except:
            position = 'undef'

        return position

    @property
    def motorConfigParameters(self):
        config = TMCM.defaultConfig
        if self.brokenLimitSwitches:
            oldConfig = {4: 268, 5: 1759, 149: 0, 153: 11, 154: 5}
            config.update(oldConfig)

        return config

    def _loadCfg(self, cmd, mode=None):
        """Load rexm configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        self.mode = self.actor.config.get('rexm', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('rexm', 'host'),
                                        port=int(self.actor.config.get('rexm', 'port')))

        try:
            self.brokenLimitSwitches = self.actor.config.getboolean('rexm', 'brokenLimitSwitches')
        except:
            self.brokenLimitSwitches = False

    def _openComm(self, cmd):
        """Open socket with rexm controller or simulate it.
        
        :param cmd: current command.
        :raise: socket.error if the communication has failed.
        """
        s = self.connectSock()

    def _closeComm(self, cmd):
        """Close socket.

        :param cmd: current command.
        """
        self.closeSock()

    def _testComm(self, cmd):
        """Test communication.

        :param cmd: current command.
        :raise: Exception if the communication has failed with the controller.
        """
        self.checkConfig(cmd)
        self.ensureLimitSwitchesOK(cmd)

    def _init(self, cmd, doHome=True):
        """Set motor config, go to low resolution position, set this position at 0 (steps).

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        cmd.inform('text="setting motor config ..."')
        self._setConfig(cmd)
        self.checkConfig(cmd)

        if doHome:
            self.moving(cmd, position='low')

            cmd.inform('text="setting origin at 0..."')
            self._setHome(cmd=cmd)

    def getStatus(self, cmd):
        """Get status and generate rexm keywords.

        :param cmd: current command.
        """
        self.checkSafeStop(cmd)
        self.checkStatus(cmd)

    def stopMotion(self, cmd, forceStop=False):
        """Abort current motion and retry until speed=0.

        :param cmd: current command.
        :param forceStop: if True send MST command directly.
        :raise: Exception with warning message.
        """
        if forceStop:
            self.declareNewGratingPosition(cmd)
            self.stopAndCheck(cmd)
        else:
            self.checkStatus(cmd)

        start = time.time()

        while self.isMoving:
            if (time.time() - start) > rexm.stoppingTimeout:
                raise TimeoutError('failed to stop rexm motion')

            self.stopAndCheck(cmd=cmd)

        self.getStatus(cmd)

    def stopAndCheck(self, cmd):
        """Send MST command and check status.

        :param cmd: current command.
        """
        cmd.inform('text="stopping rexm motion"')
        self._stop(cmd=cmd)

        # wait 1 sec and check status again...
        time.sleep(1)
        self.checkStatus(cmd)

    def moving(self, cmd, position=None, **kwargs):
        """Go to desired position (low|med), or relative move, forceStop to stop holding current.

        :param cmd: current command.
        :param kwargs: keywords arguments.
        :raise: Exception with warning message.
        """
        self.abortMotion = False
        self.ensureLimitSwitchesOK(cmd)
        self.declareNewGratingPosition(cmd, invalid=True)

        if position is not None:
            self._goToPosition(cmd, position)
        else:
            self._moveRelative(cmd, **kwargs)

        # wait few seconds before we drop holding current...
        time.sleep(5)
        self.stopMotion(cmd, forceStop=True)

    def checkStatus(self, cmd, genKeys=True):
        """Check current status and generate rexm and rexmInfo keywords.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        try:
            self.switchA = self._getAxisParameter(paramId=11, cmd=cmd)
            self.switchB = self._getAxisParameter(paramId=10, cmd=cmd)
            self.speed = self._getSpeed(cmd=cmd)
            self.steps = self._getSteps(cmd=cmd)

        except:
            cmd.warn('rexm=undef')
            raise

        if not genKeys and (time.time() - self.last) < 2:
            return

        self.last = time.time()
        cmd.inform(f'rexmInfo={self.switchA},{self.switchB},{self.speed},{self.steps}')
        cmd.inform(f'rexm={self.position}')

    def checkConfig(self, cmd):
        """Check current config from controller and generate rexmConfig keywords.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self.motorConfig = dict([(paramId, self._getAxisParameter(paramId=paramId, cmd=cmd)) for paramId in
                                 self.motorConfigParameters.keys()])

        cmd.inform('rexmConfig=%s' % (','.join(['%d' % value for value in self.motorConfig.values()])))

    def checkParameters(self, direction, distance, speed):
        """Check relative move parameters.

        :param direction: (0 : low resolution, 1 : medium resolution).
        :param distance: distance in mm.
        :param speed: distance in mm/sec.
        :type direction: int
        :type distance: float
        :type speed: float
        :raise: ValueError if a value is out of range.
        """
        if direction not in [0, 1]:
            raise ValueError('unknown direction')

        if not (TMCM.DISTANCE_MIN <= distance <= TMCM.DISTANCE_MAX):
            raise ValueError(f'{distance} out of range : {TMCM.DISTANCE_MIN} <= distance <= {TMCM.DISTANCE_MAX}')

        if not (TMCM.SPEED_MIN <= speed <= TMCM.SPEED_MAX):
            raise ValueError(f'{speed} out of range : {TMCM.SPEED_MIN} <= speed <= {TMCM.SPEED_MAX}')

    def checkSafeStop(self, cmd):
        """Check emergency button and emergency flag. generate rexmStop keyword.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        buttonState = self._getEmergencyButtonState(cmd=cmd)
        flagState = self._getEmergencyFlag(cmd=cmd)

        cmd.inform('rexmStop=%d,%d' % (buttonState, flagState))

        if buttonState:
            if self.substates.current == 'IDLE':
                self.substates.safestop(cmd)
            elif self.substates.current in ['INITIALISING', 'MOVING']:
                raise UserWarning('Emergency Button is triggered')

    def ensureLimitSwitchesOK(self, cmd):
        """Check that both switches are not triggered, meaning that cable between controller and motor is likely to be
        disconnected, or revealing and even weirder behaviour.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self.checkStatus(cmd)

        if self.positionFromSwitch == 'error':
            raise RuntimeError('both limit switches report to be triggered, connection between the controller and the '
                               'motor is likely to be disconnected...')

    def _goToPosition(self, cmd, position):
        """| Go accurately to the required position.

        - go to desired position at nominal speed
        - adjusting position backward to unswitch at nominal speed/3
        - adjusting position forward to switch at nominal speed/3

        :param cmd: current command.
        :param position: low|med .
        :type position: str
        :raise: Exception with warning message.
        """
        direction = rexm.toDir[position]
        self.checkStatus(cmd)
        if self.limitSwitch(direction):
            cmd.inform('text="already at position %s"' % position)
            return

        self._moveRelative(cmd,
                           direction=direction,
                           distance=TMCM.DISTANCE_MAX,
                           speed=TMCM.g_speed)

        if not self.limitSwitch(direction):
            raise ValueError('limit switch is not triggered')

        cmd.inform('text="arrived at position %s"' % position)

        if self.brokenLimitSwitches:
            cmd.inform('text="adjusting position backward"')
            self._moveRelative(cmd,
                               direction=not direction,
                               distance=5,
                               speed=(TMCM.g_speed / 3),
                               hitSwitch=False)

            cmd.inform('text="adjusting position forward"')
            self._moveRelative(cmd,
                               direction=direction,
                               distance=10,
                               speed=(TMCM.g_speed / 3))

            if not self.limitSwitch(direction):
                raise ValueError('limit switch is not triggered')

            cmd.inform('text="arrived at position %s"' % position)

    def _moveRelative(self, cmd, direction, distance, speed, hitSwitch=True):
        """| Go to specified distance, direction with desired speed.

        - Stop motion
        - Check status until limit switch is reached

        :param cmd: current command.
        :param direction: (0 : low resolution, 1 : medium resolution).
        :param distance: distance to go in mm.
        :param speed: specified speed in ustep/s .
        :param bool: switch state at the beginning of motion.
        :type direction: int
        :type distance: float
        :type speed: float
        :raise: Exception with warning message.
        """
        self.stopMotion(cmd)

        self.checkParameters(direction, distance, speed)
        startCount = copy.deepcopy(self.steps)

        if self.limitSwitch(direction):
            cmd.inform('text="limit switch already triggered"')
            return

        cmd.inform('text="setting motor speed at %.2fmm/sec"' % speed)
        self._setSpeed(speed, cmd=cmd)

        cmd.inform('text="moving %dmm toward %s position"' % (distance, rexm.toPos[direction]))
        self._MVP(direction, distance, cmd=cmd)

        start = time.time()

        try:
            while not self.hasStarted(startCount=startCount) or self.isMoving:
                self.checkStatus(cmd, genKeys=False)
                elapsedTime = time.time() - start

                if self.exitASAP:
                    raise SystemExit()

                if self.limitSwitch(direction, hitSwitch=hitSwitch):
                    break

                if elapsedTime > rexm.startingTimeout and not self.hasStarted(startCount=startCount):
                    raise TimeoutError('Rexm motion has not started')

                if elapsedTime > rexm.travellingTimeout:
                    raise TimeoutError("Maximum travelling time has been reached")

                if self.abortMotion:
                    raise UserWarning('Abort motion requested')

        except:
            self.stopMotion(cmd, forceStop=True)
            raise

        self.stopMotion(cmd)

    def hasStarted(self, startCount):
        """Demonstrate that motion that effectively started.

        :param startCount: starting stepCount.
        :type startCount: int
        """
        return abs(startCount - self.steps) > 500

    def limitSwitch(self, direction, hitSwitch=True):
        """Return limit switch state which will be reached by going in that direction.

        :param direction: (0 : low resolution, 1 : medium resolution).
        :param hitSwitch: if True return switch expected to be triggered going in that direction.
        :type direction: int
        :return: limit switch state.
        """
        if hitSwitch:
            return self.switchA if direction == 0 else self.switchB
        else:
            return not self.switchB if direction == 0 else not self.switchA

    def resetEmergencyFlag(self, cmd):
        """Reset emergency flag state.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        if self._getEmergencyButtonState(cmd=cmd):
            raise ValueError('Emergency stop is still triggered')

        return self._setGlobalParameter(paramId=11, motorAddress=2, data=0, cmd=cmd)  # reset emergency stop flag

    def distFromParking(self, cmd):
        """Return distance from parking in mm

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        usteps = TMCM.mm2ustep(stepIdx=self.stepIdx, valueMm=TMCM.PARKING) - self._getAxisParameter(1, cmd=cmd)
        return TMCM.ustep2mm(stepIdx=self.stepIdx, usteps=usteps)

    def declareNewGratingPosition(self, cmd=None, invalid=False):
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

        # Use MJD seconds.
        if invalid:
            position = 'undef'
            self.forcePersistedPosition = False
        else:
            position = self.positionFromSwitch
        now = float(astroTime.Time.now().mjd)

        self.actor.instData.persistKey('rexm', position)
        self.actor.instData.persistKey('gratingMoved', now)

        cmd = self.actor.bcast if cmd is None else cmd

        cmd.inform(f'gratingMoved={now:0.6f}')

    def _setConfig(self, cmd=None):
        """Set motor parameters.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self._setGlobalParameter(paramId=80, motorAddress=0, data=2, cmd=cmd)  # shutdown pin set to low active
        self.resetEmergencyFlag(cmd=cmd)

        for paramId, value in self.motorConfigParameters.items():
            self._setAxisParameter(paramId=paramId, data=value, cmd=cmd)

    def _getSteps(self, cmd=None):
        """Get current step count.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        ustep = self._getAxisParameter(1, cmd=cmd)  # get microstep count
        return int(round(ustep / (2 ** self.stepIdx)))

    def _getSpeed(self, cmd=None):
        """Get current speed.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        velocity = self._getAxisParameter(paramId=3, cmd=cmd)
        return int(round(velocity / (2 ** (self.pulseDivisor + self.stepIdx) * (65536 / 16e6))))  # speed in step/sec

    def _setSpeed(self, speedMm, cmd=None):
        """Set motor speed.

        :param speedMm: motor speed in mm per s.
        :param cmd: current command.
        :type speedMm: float
        :raise: Exception with warning message.
        """
        ustepPerSec = TMCM.mm2ustep(stepIdx=self.stepIdx, valueMm=speedMm)
        velocity = ustepPerSec * (2 ** self.pulseDivisor * (65536 / 16e6))
        return self._setAxisParameter(paramId=4, data=velocity, cmd=cmd)

    def _setHome(self, cmd=None):
        """Set low position as 0.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self._setAxisParameter(paramId=1, data=0, cmd=cmd)

    def _MVP(self, direction, distance, cmd=None):
        """Move in relative for a specified distance and direction.

        :param direction: (0 : low resolution, 1 : medium resolution).
        :param distance: distance in mm.
        :param cmd: current command.
        :type direction: int
        :type distance: float
        :raise: Exception with warning message.
        """
        usteps = np.int32(TMCM.mm2ustep(stepIdx=self.stepIdx, valueMm=distance))
        cmdBytes = TMCM.MVP(direction, usteps)

        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def _stop(self, cmd):
        """Stop current motion.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        cmdBytes = TMCM.stop()
        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def _getEmergencyFlag(self, cmd):
        """Get emergency flag state.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        return self._getGlobalParameter(paramId=11, motorAddress=2, cmd=cmd)  # emergency stop flag

    def _getEmergencyButtonState(self, cmd):
        """Get emergency button state.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        cmdBytes = TMCM.gio(paramId=10, motorAddress=0)
        return not (int(self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)))

    def _getAxisParameter(self, paramId, cmd=None):
        """Get axis parameter.

        :param paramId: parameter id.
        :type paramId: int
        :raise: Exception with warning message.
        """
        cmdBytes = TMCM.gap(paramId=paramId)
        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def _setAxisParameter(self, paramId, data, cmd=None):
        """Set axis parameter.

        :param paramId: parameter id.
        :param data: parameter value.
        :type paramId: int 
        :raise: Exception with warning message.
        """
        cmdBytes = TMCM.sap(paramId=paramId, data=data)
        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def _getGlobalParameter(self, paramId, motorAddress, cmd=None):
        """Get global parameter.

        :param paramId: parameter id.
        :type paramId: int
        :param motorAddress: motor address.
        :type motorAddress: int
        :raise: Exception with warning message.
        """
        cmdBytes = TMCM.ggp(paramId=paramId, motorAddress=motorAddress)
        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def _setGlobalParameter(self, paramId, motorAddress, data, cmd=None):
        """Set global parameter.

        :param paramId: parameter id.
        :param motorAddress: motor address.
        :param data: parameter value.
        :type motorAddress: int
        :type paramId: int
        :raise: Exception with warning message.
        """
        cmdBytes = TMCM.sgp(paramId=paramId, motorAddress=motorAddress, data=data)
        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def sendOneCommand(self, cmdBytes, doClose=False, cmd=None):
        """Send cmdBytes to rexm controller.

        :param cmdBytes: bytes to send.
        :param doClose: close socket.
        :param cmd: current command.
        :type cmdStr: bytes
        :type doClose: bool
        :return: response decoded
        """
        if cmd is None:
            cmd = self.actor.bcast
        if len(cmdBytes) != 9:
            raise ValueError('cmdStr is badly formatted')

        self.logger.debug('sending %r', cmdBytes)

        s = self.connectSock()

        try:
            s.sendall(cmdBytes)
        except:
            self.closeSock()
            raise

        reply = self.getOneResponse(sock=s, cmd=cmd)

        if doClose:
            self.closeSock()

        return reply

    def getOneResponse(self, sock=None, cmd=None):
        """Attempt to receive data from the socket.

        :param sock: socket.
        :param cmd: command.
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        time.sleep(0.05)
        if sock is None:
            sock = self.connectSock()

        ret = recvPacket(sock.recv(9))
        if ret.status != 100:
            raise RuntimeError(TMCM.controllerStatus[ret.status])

        reply = ret.data
        self.logger.debug('received %r', reply)

        return reply

    def createSock(self):
        """Create socket in operation, simulator otherwise."""
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def doAbort(self):
        """Abort current motion."""
        self.abortMotion = True

        # see ics.utils.fsm.fsmThread.LockedThread
        self.waitForCommandToFinish()

        return

    def leaveSafely(self, cmd):
        """clear and leave.

        :param cmd: current command.
        """
        self.monitor = 0
        self.doAbort()

        try:
            self.getStatus(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self._closeComm(cmd=cmd)
