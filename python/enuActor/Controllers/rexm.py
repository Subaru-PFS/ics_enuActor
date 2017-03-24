#!/usr/bin/env python

import logging
import sys
import time
from datetime import datetime as dt

from enuActor.Controllers.Simulator.rexm_simu import RexmSimulator
from enuActor.Controllers.device import Device
from enuActor.Controllers.drivers import rexm_drivers
from enuActor.utils.wrap import busy, formatException


class rexm(Device):
    timeout = 5
    switch = {(1, 0): "low", (0, 1): "mid"}
    toPos = {0: 'low', 1: 'mid'}
    toDir = {'low': 0, 'mid': 1}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """| This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name:str
        """
        Device.__init__(self, actor, name)

        self.logger = logging.getLogger('rexm')
        self.logger.setLevel(loglevel)

        self.EOL = '\n'
        self.currPos = 'undef'
        self.serial = None
        self.positionA = 0
        self.positionB = 0
        self.speed = 0

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
        self.actor.reloadConfiguration(cmd=cmd)

        self.currMode = self.actor.config.get('rexm', 'mode') if mode is None else mode
        self.port = self.actor.config.get('rexm', 'port')

    def startCommunication(self, cmd=None):
        """| Start serial communication with the controller or simulate it.
        | Called by device.loadDevice().

        - try to get an axis parameter to check that the communication is working

        :param cmd: on going command
        :raise: Exception if the communication has failed with the controller
        """
        self.myTMCM = rexm_drivers.TMCM(self.port) if self.currMode == 'operation' else RexmSimulator()

        ret = self.myTMCM.gap(11)

    def initialise(self, cmd):
        """| Initialise rexm controller, called y device.initDevice().

        - search for low position
        - set this position at 0 => Home
        - if every steps are successfully operated

        :param cmd: on going command
        :raise: Exception if a command fail, user is warned with error ret.
        """

        cmd.inform("text='seeking home ...'")
        self._moveAccurate(cmd, rexm.toDir['low'])

        ret = self.myTMCM.sap(1, 0)  # set 0 as home

    def getStatus(self, cmd=None, doFinish=True):
        """| Get status from the controller and publish rexm keywords.

        - rexm = state, mode, position(undef if device is not initialised or both limit switches not activated)

        :param cmd: on going command
        :param doFinish: if True finish the command
        """
        self.currPos = "undef"
        ender = cmd.finish if doFinish else cmd.inform
        fender = cmd.fail if doFinish else cmd.warn

        if self.fsm.current in ['IDLE', 'BUSY', 'LOADED']:
            try:
                self._checkStatus(cmd, doClose=doFinish)
                self.currPos = rexm.switch[(self.positionA, self.positionB)] if (self.positionA, self.positionB) \
                                                                                in rexm.switch else "undef"
            except Exception as e:
                cmd.warn("text='%s getStatus failed %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))

                ender = fender

        ender("rexm=%s,%s,%s" % (self.fsm.current, self.currMode, self.currPos))

    def abort(self, cmd):
        """| Abort current motion

        :param cmd: on going command
        :raise: Exception if a communication error occurs.
        :raise: Timeout if the command takes too long.
        """
        t = dt.now()
        ts = dt.now()
        try:
            self.myTMCM.stop()
            cmd.inform("text='stopping rexm motion'")
            while self.isMoving:
                if (dt.now() - t).total_seconds() > 5:
                    raise Exception("timeout aborting motion")
                if (dt.now() - ts).total_seconds() > 2:
                    self._checkStatus(cmd)
                    self.myTMCM.stop()
                    ts = dt.now()
                else:
                    self._checkStatus(cmd, doShow=False)
            self._checkStatus(cmd)
        except:
            cmd.warn("text='%s failed to stop motion '" % self.name)
            raise


    @busy
    def moveTo(self, cmd, position):
        """ |  *Wrapper busy* handles the state machine.
        | Move to desired position (low|mid).

        :param cmd: on going command
        :param position: (low|mid)
        :type position: str
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """

        try:
            self._moveAccurate(cmd, rexm.toDir[position])
            return True

        except Exception as e:
            cmd.warn("text='%s failed to command motion %s'" % (self.name.upper(),
                                                                formatException(e, sys.exc_info()[2])))

            return False
        
    def _checkStatus(self, cmd, doClose=False, doShow=True):
        """| Check current status from controller and publish rexmInfo keywords

        - rexmInfo = switchA state, switchB state, speed, position(ustep from origin)

        :param cmd: on going command
        :param doClose: close serial if doClose=True
        :param doShow: publish keyword if doShow=True
        :raise: Exception if communication error occurs

        """
        time.sleep(0.01)

        self.positionA = self.myTMCM.gap(11)
        self.positionB = self.myTMCM.gap(10)
        self.speed = self.myTMCM.gap(3, fmtRet='>BBBBiB')
        self.currPos = self.myTMCM.gap(1, doClose=doClose, fmtRet='>BBBBiB')

        if doShow:
            cmd.inform("rexmInfo=%i,%i,%i,%i" % (self.positionA, self.positionB, self.speed, self.currPos))  
        

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
        self._checkStatus(cmd)
        if not self.switchOn(direction):
            self._stopAndMove(cmd, direction, self.myTMCM.DISTANCE_MAX, self.myTMCM.g_speed)

        else:
            cmd.inform("text='already at position %s'" % rexm.toPos[direction])
            return

        cmd.inform("text='arrived at position %s" % rexm.toPos[direction])

        cmd.inform("text='adjusting position backward %s" % rexm.toPos[direction])
        self._stopAndMove(cmd, not direction, 20, self.myTMCM.g_speed / 3, bool=True)

        cmd.inform("text='adjusting position forward %s" % rexm.toPos[direction])
        self._stopAndMove(cmd, direction, 20.2, self.myTMCM.g_speed / 3)

        cmd.inform("text='arrived at desired position %s" % rexm.toPos[direction])

    def _stopAndMove(self, cmd, direction, distance, speed, bool=False):
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
        self.hasStarted = False
        cond = direction if not bool else not direction
        time.sleep(0.5)
        self.abort(cmd)

        cmd.inform("text='moving to %s, %i, %.2f" % (rexm.toPos[direction], distance, speed))
        time.sleep(0.5)
        ok = self.myTMCM.MVP(direction, distance, speed)

        t = dt.now()
        ts = dt.now()

        while self.switchOn(cond) == bool:
            self.checkStart(t)
            if (dt.now() - t).total_seconds() > 200:
                raise Exception("timeout commanding MOVE")

            if (dt.now() - ts).total_seconds() > 2:
                self._checkStatus(cmd)
                ts = dt.now()
            else:
                self._checkStatus(cmd, doShow=False)

        self.abort(cmd)
        time.sleep(0.5)
        self._checkStatus(cmd)

    def switchOn(self, direction):
        """| Return limit switch state which will be reached by going in that direction.

        :param direction: 0 (go to low position ) 1 (go to mid position)
        :type direction: int
        :return: limit switch state
        """
        return self.positionA if direction == 0 else self.positionB

    def checkStart(self, t0):
        """checkStart
        - check if the motion has actually begun after a MVP command

        :param t0: timestamp before send MVP command
        :type t0: datetime.datetime
        :raise: timeout if commanding takes too long
        """

        if (dt.now() - t0).total_seconds() > 5 and not self.hasStarted:
            if not self.isMoving:
                raise Exception("timeout isMoving")
            self.hasStarted = True
