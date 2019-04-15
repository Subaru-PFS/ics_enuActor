import copy
import logging
import time

import enuActor.utils.bufferedSocket as bufferedSocket
import numpy as np
from enuActor.Simulators.rexm import RexmSim
from enuActor.drivers.rexm_drivers import recvPacket, TMCM
from enuActor.utils.fsmThread import FSMThread


class rexm(FSMThread, bufferedSocket.EthComm):
    travellingTimeout = 150
    stoppingTimeout = 5
    startingTimeout = 3

    switch = {(1, 0): 'low', (0, 1): 'mid', (0, 0): 'undef', (1, 1): 'error'}
    toPos = {0: 'low', 1: 'mid'}
    toDir = {'low': 0, 'mid': 1}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        substates = ['IDLE', 'MOVING', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'idle', 'src': ['MOVING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING'], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=False)

        self.addStateCB('MOVING', self.moving)
        self.sim = RexmSim()

        self.switchA = 0
        self.switchB = 0
        self.speed = 0
        self.pulseDivisor = 0
        self.abortMotion = False

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
        return rexm.switch[self.switchA, self.switchB]

    @property
    def isMoving(self):
        return 1 if abs(self.speed) > 0 else 0

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file, called by device.loadDevice().

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('rexm', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('rexm', 'host'),
                                        port=int(self.actor.config.get('rexm', 'port')))

    def _openComm(self, cmd):
        """| Open socket with rexm controller or simulate it.
        | Called by FSMDev.loadDevice()

        :param cmd: on going command
        :raise: socket.error if the communication has failed with the controller
        """
        s = self.connectSock()

    def _closeComm(self, cmd):
        """| Close communication.
        | Called by FSMThread.stop()

        :param cmd: on going command
        """
        self.closeSock()

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: RuntimeError if the communication has failed with the controller
        """
        self.checkConfig(cmd)

    def _init(self, cmd, doHome=True):
        """| Initialise rexm controller, called by self.initDevice().
        - set motor config
        - go to low resolution position
        - set this position at 0 => Home

        :param cmd: on going command
        :raise: Exception if a command fail, user is warned with error ret.
        """
        cmd.inform('text="setting motor config ..."')
        self._setConfig(cmd)
        self.checkConfig(cmd)

        if doHome:
            self._goToPosition(cmd, position='low')

            cmd.inform('text="setting origin at 0..."')
            self._setHome(cmd=cmd)

    def getStatus(self, cmd):
        """| Get status from the controller and generate rexm keywords.

        :param cmd: on going command
        """
        self.checkConfig(cmd)
        self.checkStatus(cmd)

    def safeStop(self, cmd):
        """| Abort current motion and retry until speed=0

        :param cmd: on going command
        :raise: Exception if a communication error occurs.
        :raise: Timeout if the command takes too long.
        """
        start = time.time()
        self.stopMotion(cmd=cmd)

        while self.isMoving:
            if (time.time() - start) > rexm.stoppingTimeout:
                raise TimeoutError('failed to stop rexm motion')

            self.stopMotion(cmd=cmd)

    def stopMotion(self, cmd):
        """| Abort current motion and check status

        :param cmd: on going command
        """
        cmd.inform('text="stopping rexm motion"')
        self._stop(cmd=cmd)

        time.sleep(1)
        self.checkStatus(cmd)

    def moving(self, cmd, kwargs):
        """| Go to desired position (low|mid), or relative move

        :param cmd: on going command
        :param position: (low|mid)
        :type position: str
        :raise: Exception if move command fails
        """
        self.abortMotion = False
        position = kwargs.pop('position', None)

        if position is not None:
            self._goToPosition(cmd, position)
        else:
            self._moveRelative(cmd, **kwargs)

    def checkStatus(self, cmd, genKeys=True):
        """| Check current status from controller and generate rexmInfo keywords
        - rexmInfo = switchA state, switchB state, speed, position(ustep from origin)

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        try:
            self.switchA = self._getAxisParameter(paramId=11, cmd=cmd)
            self.switchB = self._getAxisParameter(paramId=10, cmd=cmd)
            self.speed = self._getSpeed(cmd=cmd)
            self.stepCount = self._getStepCount(cmd=cmd)

        except:
            cmd.warn('rexm=undef')
            raise

        if not genKeys and (time.time() - self.last) < 2:
            return

        self.last = time.time()
        cmd.inform('rexmInfo=%i,%i,%i,%i' % (self.switchA, self.switchB, self.speed, self.stepCount))
        cmd.inform('rexm=%s' % self.position)

    def checkConfig(self, cmd):
        """| Check current config from controller and generate rexmConfig keywords)

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        self.stepIdx = self._getAxisParameter(paramId=140, cmd=cmd)
        self.pulseDivisor = self._getAxisParameter(paramId=154, cmd=cmd)

        cmd.inform('rexmConfig=%d,%d' % (self.stepIdx, self.pulseDivisor))

    def checkParameters(self, direction, distance, speed):
        """| Check relative move parameters

        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :param distance: distance in mm
        :type distance: float
        :param speed: distance in mm/sec
        :type speed: float
        :raise: ValueError if a value is out of range
        """
        if direction not in [0, 1]:
            raise ValueError('unknown direction')

        if not 0 < distance <= TMCM.DISTANCE_MAX:
            raise ValueError('requested distance out of range')

        if not (0 < speed <= TMCM.SPEED_MAX):
            raise ValueError('requested speed out of range')

    def _goToPosition(self, cmd, position):
        """| Go accurately to the required position.

        - go to desired position at nominal speed
        - adjusting position backward to unswitch at nominal speed/3
        - adjusting position forward to switch at nominal speed/3

        :param cmd: on going command
        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :raise: Exception if communication error occurs
        :raise: Timeout if the command takes too long
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

        cmd.inform('text="arrived at position %s"' % position)

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

        cmd.inform('text="arrived at desired position %s"' % position)

    def _moveRelative(self, cmd, direction, distance, speed, hitSwitch=True):
        """| Go to specified distance, direction with desired speed.

        - Stop motion
        - Check status until limit switch is reached

        :param cmd: on going command
        :param direction: 0 (go to low position ) 1 (go to mid position)
        :param distance: distance to go in mm
        :param speed: specified speed in ustep/s
        :param bool: switch state at the beginning of motion
        :type direction: int
        :type distance: float
        :type speed: float
        :raise: Exception if communication error occurs
        :raise: timeout if commanding takes too long
        """
        self.checkParameters(direction, distance, speed)
        self.safeStop(cmd)
        startCount = copy.deepcopy(self.stepCount)

        if self.limitSwitch(direction):
            cmd.inform('text="limit switch already triggered"')
            return

        cmd.inform('text="setting motor speed at %.2fmm/sec"' % speed)
        self._setSpeed(speed, cmd=cmd)

        cmd.inform('text="moving %dmm toward %s position"' % (distance, rexm.toPos[direction]))
        self._MVP(direction, distance, cmd=cmd)

        start = time.time()
        self.checkStatus(cmd)

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

        finally:
            self.safeStop(cmd)

    def hasStarted(self, startCount):
        """| demonstrate that motion that effectively started

        :param startCount: starting stepCount
        :type startCount: int
        """
        return abs(startCount - self.stepCount) > 500

    def limitSwitch(self, direction, hitSwitch=True):
        """| Return limit switch state which will be reached by going in that direction.

        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :return: limit switch state
        """
        if hitSwitch:
            return self.switchA if direction == 0 else self.switchB
        else:
            return not self.switchB if direction == 0 else not self.switchA

    def _setConfig(self, cmd=None):
        """| Set motor parameters.
        - set stepIdx = 2
        - set pulseDivisor = 5

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        self._setAxisParameter(paramId=140, data=2, cmd=cmd)
        self._setAxisParameter(paramId=154, data=5, cmd=cmd)

    def _getAxisParameter(self, paramId, fmtRet='>BBBBIB', cmd=None):
        """| Get axis parameter

        :param paramId: parameter id
        :type paramId:int
        :param fmtRet: return format to convert bytes to numeric value
        :type fmtRet:str
        :raise: Exception if communication error occurs
        """
        cmdBytes = TMCM.gap(paramId=paramId)
        return self.sendOneCommand(cmdBytes=cmdBytes, fmtRet=fmtRet, cmd=cmd)

    def _setAxisParameter(self, paramId, data, fmtRet='>BBBBIB', cmd=None):
        """| Set axis parameter

        :param paramId: parameter id
        :type paramId:int
        :param data: data to be sent
        :param fmtRet: return format to convert bytes to numeric value
        :type fmtRet:str
        :raise: Exception if communication error occur
        """
        cmdBytes = TMCM.sap(paramId=paramId, data=data)
        return self.sendOneCommand(cmdBytes=cmdBytes, fmtRet=fmtRet, cmd=cmd)

    def _getStepCount(self, cmd=None):
        """| Get current step count.

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        ustep = self._getAxisParameter(1, fmtRet='>BBBBiB', cmd=cmd)  # get microstep count
        return ustep / (2 ** self.stepIdx)

    def _getSpeed(self, cmd=None):
        """| Get current speed.

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        velocity = self._getAxisParameter(paramId=3, fmtRet='>BBBB  iB', cmd=cmd)
        return velocity / (2 ** (self.pulseDivisor + self.stepIdx) * (65536 / 16e6))  # speed in step/sec

    def _setSpeed(self, speedMm, cmd=None):
        """| Set motor speed.

        :param speedMm motor speed in mm/s
        :type speedMm: float
        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        freq = TMCM.mm2counts(stepIdx=self.stepIdx, valueMm=speedMm)
        velocity = freq * (2 ** self.pulseDivisor * (65536 / 16e6))
        return self._setAxisParameter(paramId=4, data=velocity, cmd=cmd)

    def _setHome(self, cmd=None):
        """| Set low position as 0.

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        cmdBytes = TMCM.sap(paramId=1, data=0)
        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def _MVP(self, direction, distance, cmd=None):
        """| Move in relative for a specified distance and direction.

        :param direction 0 => to low, direction 1=> to mid
        :type direction: int
        :param distance distance in mm
        :type distance: float
        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        counts = np.int32(TMCM.mm2counts(stepIdx=self.stepIdx, valueMm=distance))
        cmdBytes = TMCM.MVP(direction, counts)

        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def _stop(self, cmd):
        """| Stop current motion

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        cmdBytes = TMCM.stop()
        return self.sendOneCommand(cmdBytes=cmdBytes, cmd=cmd)

    def sendOneCommand(self, cmdBytes, doClose=False, cmd=None, fmtRet='>BBBBIB'):
        """| Send one command and return one response.

        :param cmdStr: (str) The command to send.
        :param doClose: If True (the default), the device socket is closed before returning.
        :param cmd: on going command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
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

        reply = self.getOneResponse(sock=s, cmd=cmd, fmtRet=fmtRet)

        if doClose:
            self.closeSock()

        return reply

    def getOneResponse(self, sock=None, cmd=None, fmtRet='>BBBBIB'):
        """| Attempt to receive data from the socket.

        :param sock: socket
        :param cmd: command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        time.sleep(0.05)
        if sock is None:
            sock = self.connectSock()

        ret = recvPacket(sock.recv(9), fmtRet=fmtRet)
        if ret.status != 100:
            raise RuntimeError(TMCM.controllerStatus[ret.status])

        reply = ret.data
        self.logger.debug('received %r', reply)

        return reply

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
