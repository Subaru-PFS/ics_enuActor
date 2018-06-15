import logging
import time
from functools import partial
import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.simulator.rexm_simu import RexmSim
from enuActor.drivers import rexm_drivers


class rexm(FSMDev, QThread):
    timeout = 5
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

        self.EOL = '\n'
        self.position = 'undef'
        self.serial = None
        self.switchA = 0
        self.switchB = 0
        self.speed = 0

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

    def start(self, cmd=None, doInit=False, mode=None):
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)
        QThread.start(self)

    def stop(self, cmd=None):
        self.exit()
        FSMDev.stop(self, cmd=cmd)

    @property
    def isMoving(self):
        return 1 if abs(self.speed) > 0 else 0

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file, called by device.loadDevice().

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.mode = self.actor.config.get('rexm', 'mode') if mode is None else mode
        self.port = self.actor.config.get('rexm', 'port')

    def startComm(self, cmd):
        """| Start serial communication with the controller or simulate it.
        | Called by device.loadDevice().

        - try to get an axis parameter to check that the communication is working

        :param cmd: on going command
        :raise: Exception if the communication has failed with the controller
        """
        self.sim = RexmSim()  # Create new simulator
        self.myTMCM = self.createSock()

        ret = self.myTMCM.gap(11)

    def init(self, cmd):
        """| Initialise rexm controller, called y device.initDevice().

        - search for low position
        - set this position at 0 => Home
        - if every steps are successfully operated

        :param cmd: on going command
        :raise: Exception if a command fail, user is warned with error ret.
        """

        cmd.inform('text="seeking home ..."')
        self._moveAccurate(cmd, rexm.toDir['low'])

        ret = self.myTMCM.sap(1, 0)  # set 0 as home

    def getStatus(self, cmd):
        """| Get status from the controller and publish slit keywords.

        - slit = state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
        - slitInfo = str : *an interpreted status returned by the controller*

        :param cmd: on going command
        :param doFinish: if True finish the command
        """

        cmd.inform('rexmFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('rexmMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            try:
                self._checkStatus(cmd=cmd, doClose=True)
                self._checkPosition(cmd=cmd)

            except:
                cmd.warn('rexm=undef')
                raise

        cmd.finish()

    def abort(self, cmd):
        """| Abort current motion

        :param cmd: on going command
        :raise: Exception if a communication error occurs.
        :raise: Timeout if the command takes too long.
        """
        start = time.time()
        self._checkStatus(cmd)

        try:
            cmd.inform('text="stopping rexm motion"')

            while self.isMoving:
                self.myTMCM.stop(temp=1)
                self._checkStatus(cmd)

                if (time.time() - start) > 5:
                    raise TimeoutError('timeout aborting motion')
        except:
            cmd.warn('text="rexm failed to stop motion"')
            raise

    def moveTo(self, e):
        """ |  *Wrapper busy* handles the state machine.
        | Move to desired position (low|mid).

        :param cmd: on going command
        :param position: (low|mid)
        :type position: str
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """

        cmd, position = e.cmd, e.position
        try:
            self._moveAccurate(cmd, rexm.toDir[position])

        except UserWarning:
            self.abort(cmd)
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        except:
            self.substates.fail()
            raise

        self.substates.idle()

    def _checkStatus(self, cmd, doClose=False):
        """| Check current status from controller and publish rexmInfo keywords

        - rexmInfo = switchA state, switchB state, speed, position(ustep from origin)

        :param cmd: on going command
        :param doClose: close serial if doClose=True
        :param doShow: publish keyword if doShow=True
        :raise: Exception if communication error occurs

        """
        time.sleep(0.01)

        self.switchA = self.myTMCM.gap(11)
        self.switchB = self.myTMCM.gap(10)
        self.speed = self.myTMCM.gap(3, fmtRet='>BBBBiB')
        self.stepCount = self.myTMCM.gap(1, doClose=doClose, fmtRet='>BBBBiB')

        if (time.time() - self.samptime) > 2:
            self.samptime = time.time()
            cmd.inform('rexmInfo=%i,%i,%i,%i' % (self.switchA, self.switchB, self.speed, self.stepCount))

    def _checkPosition(self, cmd):

        self.position = rexm.switch[self.switchA, self.switchB]
        cmd.inform('rexm=%s' % self.position)

    def _moveAccurate(self, cmd, direction):
        """| Move accurately to the required direction.

        - go to desired position at nominal speed
        - adjusting position backward to unswitch at nominal speed/3
        - adjusting position forward to switch at nominal speed/3

        :param cmd: on going command
        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :raise: Exception if communication error occurs
        :raise: Timeout if the command takes too long
        """
        self.stopMotion = False
        self._checkStatus(cmd)
        if not self.switchOn(direction):
            self._stopAndMove(cmd,
                              direction=direction,
                              distance=self.myTMCM.DISTANCE_MAX,
                              speed=self.myTMCM.g_speed,
                              hitSwitch=True)
        else:
            cmd.inform('text="already at position %s"' % rexm.toPos[direction])
            return

        cmd.inform('text="arrived at position %s"' % rexm.toPos[direction])

        cmd.inform('text="adjusting position backward %s"' % rexm.toPos[direction])
        self._stopAndMove(cmd,
                          direction=not direction,
                          distance=20,
                          speed=(self.myTMCM.g_speed / 3),
                          hitSwitch=False)

        cmd.inform('text="adjusting position forward %s"' % rexm.toPos[direction])
        self._stopAndMove(cmd,
                          direction=direction,
                          distance=20.1,
                          speed=(self.myTMCM.g_speed / 3),
                          hitSwitch=True)

        cmd.inform('text="arrived at desired position %s"' % rexm.toPos[direction])

    def _stopAndMove(self, cmd, direction, distance, speed, hitSwitch=True):
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

        # cond = direction if not bool else not direction
        self.abort(cmd)

        cmd.inform('text="moving to %s, %i, %.2f"' % (rexm.toPos[direction], distance, speed))
        ok = self.myTMCM.MVP(direction, distance, speed)

        start = time.time()
        self._checkStatus(cmd)

        while not self.isMoving:
            self._checkStatus(cmd)
            if (time.time() - start) > 5:
                raise TimeoutError('Rexm is not moving')

        endOfMotion = partial(self.switchOn, direction) if hitSwitch else partial(self.switchOff, direction)

        while not endOfMotion():
            if (time.time() - start) > 200:
                raise TimeoutError("Rexm haven't reach the limit switch")

            if self.stopMotion:
                raise UserWarning('Motion aborted by user')

            self._checkStatus(cmd)

        self.abort(cmd)

    def switchOn(self, direction):
        """| Return limit switch state which will be reached by going in that direction.

        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :return: limit switch state
        """
        if direction == 0:
            return self.switchA
        elif direction == 1:
            return self.switchB
        else:
            raise ValueError('unknown direction')

    def switchOff(self, direction):
        """| Return limit switch state which will be reached by going in that direction.

        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :return: limit switch state
        """
        if direction == 0:
            return not self.switchB
        elif direction == 1:
            return not self.switchA
        else:
            raise ValueError('unknown direction')

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = rexm_drivers.TMCM(self.port)

        return s

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
