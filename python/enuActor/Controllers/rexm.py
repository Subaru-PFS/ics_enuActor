import copy
import logging
import time

import enuActor.Controllers.bufferedSocket as bufferedSocket
import numpy as np
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.Simulators.rexm import RexmSim
from enuActor.drivers.rexm_drivers import recvPacket, TMCM


class rexm(FSMDev, QThread, bufferedSocket.EthComm):
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

        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('MOVING', self.moveTo)

        self.switchA = 0
        self.switchB = 0
        self.speed = 0
        self.pulseDivisor = 0
        self.abortMotion = False

        self.samptime = time.time()
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

    def start(self, cmd=None, doInit=False, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        self.exit()
        FSMDev.stop(self, cmd=cmd)

    def loadCfg(self, cmd, mode=None):
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

    def startComm(self, cmd):
        """ Start socket with the rexm controller or simulate it.
        | Called by FSMDev.loadDevice()
        try to get controller statuses

        :param cmd: on going command
        :raise: Exception if the communication has failed with the controller
        """
        self.sim = RexmSim()  # Create new simulator
        s = self.connectSock()

        self.checkConfig(cmd)
        self.checkStatus(cmd, doClose=True)

    def init(self, cmd):
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

        self._goToPosition(cmd, position='low')

        cmd.inform('text="setting origin at 0..."')
        self._setHome(cmd=cmd)

    def getStatus(self, cmd):
        """| Get status from the controller and generate rexm keywords.

        :param cmd: on going command
        """
        cmd.inform('rexmFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('rexmMode=%s' % self.mode)

        if self.states.current in ['LOADED', 'ONLINE']:
            self.checkConfig(cmd)
            self.checkStatus(cmd, doClose=True)

        cmd.finish()

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

        time.sleep(0.5)
        self.checkStatus(cmd)

    def moveTo(self, e):
        """| Go to desired position (low|mid), or relative move

        :param cmd: on going command
        :param position: (low|mid)
        :type position: str
        :raise: Exception if move command fails
        """
        cmd, position = e.cmd, e.position

        try:
            if position:
                self._goToPosition(cmd, position)
            else:
                self._moveRelative(cmd,
                                   direction=e.direction,
                                   distance=e.distance,
                                   speed=TMCM.g_speed)
        except UserWarning:
            self.safeStop(cmd)
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        except:
            self.substates.fail()
            raise

        self.substates.idle()

    def checkStatus(self, cmd, doClose=False):
        """| Check current status from controller and generate rexmInfo keywords
        - rexmInfo = switchA state, switchB state, speed, position(ustep from origin)

        :param cmd: on going command
        :param doClose: close socket if doClose=True
        :raise: Exception if communication error occurs
        """
        try:
            self.switchA = self._getAxisParameter(paramId=11, cmd=cmd)
            self.switchB = self._getAxisParameter(paramId=10, cmd=cmd)
            self.speed = self._getSpeed(cmd=cmd)
            self.stepCount = self._getAxisParameter(1, doClose=doClose, fmtRet='>BBBBiB', cmd=cmd)

        except:
            cmd.warn('rexm=undef')
            raise

        if (time.time() - self.samptime) > 2:
            self.samptime = time.time()
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
                           speed=(TMCM.g_speed / 3))

        cmd.inform('text="adjusting position forward"')
        self._moveRelative(cmd,
                           direction=direction,
                           distance=10,
                           speed=(TMCM.g_speed / 3))

        cmd.inform('text="arrived at desired position %s"' % position)

    def _moveRelative(self, cmd, direction, distance, speed):
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
        expectedTime = start + (distance / speed)
        self.checkStatus(cmd)

        while not (self.hasStarted(startCount=startCount) and self.waitForCompletion(expectedTime=expectedTime)):
            self.checkStatus(cmd)
            elapsedTime = time.time() - start
            if self.limitSwitch(direction):
                break

            if elapsedTime > rexm.startingTimeout and not self.hasStarted(startCount=startCount):
                raise TimeoutError('Rexm motion has not started')

            if elapsedTime > rexm.travellingTimeout:
                raise TimeoutError("Maximum travelling time has been reached")

            if self.abortMotion:
                raise UserWarning('Abort motion requested')

        self.safeStop(cmd)

    def waitForCompletion(self, expectedTime):
        """| wait for motion completion

        :param expectedTime: expected time for motion completion
        :type expectedTime: float
        """
        return time.time() > expectedTime and not self.isMoving

    def hasStarted(self, startCount):
        """| demonstrate that motion that effectively started

        :param startCount: starting stepCount
        :type startCount: int
        """
        return abs(startCount - self.stepCount) > TMCM.mm2counts(stepIdx=self.stepIdx, valueMm=0.5)

    def limitSwitch(self, direction):
        """| Return limit switch state which will be reached by going in that direction.

        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :return: limit switch state
        """
        return self.switchA if direction == 0 else self.switchB

    def _setConfig(self, cmd=None):
        """| Set motor parameters.
        - set stepIdx = 2
        - set pulseDivisor = 5

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        self._setAxisParameter(paramId=140, data=2, cmd=cmd)
        self._setAxisParameter(paramId=154, data=5, cmd=cmd)

    def _getAxisParameter(self, paramId, doClose=False, fmtRet='>BBBBIB', cmd=None):
        """| Get axis parameter

        :param paramId: parameter id
        :type paramId:int
        :param fmtRet: return format to convert bytes to numeric value
        :type fmtRet:str
        :raise: Exception if communication error occurs
        """
        cmdBytes = TMCM.gap(paramId=paramId)
        return self.sendOneCommand(cmdBytes=cmdBytes, doClose=doClose, fmtRet=fmtRet, cmd=cmd)

    def _setAxisParameter(self, paramId, data, doClose=False, fmtRet='>BBBBIB', cmd=None):
        """| Set axis parameter

        :param paramId: parameter id
        :type paramId:int
        :param data: data to be sent
        :param fmtRet: return format to convert bytes to numeric value
        :type fmtRet:str
        :raise: Exception if communication error occur
        """
        cmdBytes = TMCM.sap(paramId=paramId, data=data)
        return self.sendOneCommand(cmdBytes=cmdBytes, doClose=doClose, fmtRet=fmtRet, cmd=cmd)

    def _getSpeed(self, cmd=None):
        """| Get current speed.

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        velocity = self._getAxisParameter(paramId=3, fmtRet='>BBBBiB', cmd=cmd)
        return velocity / (2 ** self.pulseDivisor * (65536 / 16e6))  # speed in ustep/sec

    def _setSpeed(self, speedMm, doClose=False, cmd=None):
        """| Set motor speed.

        :param speedMm motor speed in mm/s
        :type speedMm: float
        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        freq = TMCM.mm2counts(stepIdx=self.stepIdx, valueMm=speedMm) * (2 ** self.pulseDivisor * (65536 / 16e6))
        return self._setAxisParameter(paramId=4, data=freq, doClose=doClose, cmd=cmd)

    def _setHome(self, doClose=False, cmd=None):
        """| Set low position as 0.

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        cmdBytes = TMCM.sap(paramId=1, data=0)
        return self.sendOneCommand(cmdBytes=cmdBytes, doClose=doClose, cmd=cmd)

    def _MVP(self, direction, distance, doClose=False, cmd=None):
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

        return self.sendOneCommand(cmdBytes=cmdBytes, doClose=doClose, cmd=cmd)

    def _stop(self, cmd, doClose=False):
        """| Stop current motion

        :param cmd: on going command
        :raise: Exception if communication error occurs
        """
        cmdBytes = TMCM.stop()
        return self.sendOneCommand(cmdBytes=cmdBytes, doClose=doClose, cmd=cmd)

    def sendOneCommand(self, cmdBytes, doClose=False, cmd=None, fmtRet='>BBBBIB'):
        """| Send one command and return one response.

        :param cmdStr: (str) The command to send.
        :param doClose: If True (the default), the device socket is closed before returning.
        :param cmd: on going command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        time.sleep(0.01)
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

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
