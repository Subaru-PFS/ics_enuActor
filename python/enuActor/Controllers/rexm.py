#!/usr/bin/env python

import logging
import time
from datetime import datetime as dt

from Controllers.Simulator.rexm_simu import RexmSimulator
from Controllers.device import Device
from enuActor.Controllers.utils import rexm_drivers
from enuActor.Controllers.wrap import busy


class rexm(Device):
    timeout = 5
    switch = {(1, 0): "low", (0, 1): "mid"}
    toPos = {0: 'low', 1: 'mid'}
    toDir = {'low': 0, 'mid': 1}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        super(rexm, self).__init__(actor, name)

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
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """
        self.actor.reloadConfiguration(cmd=cmd)

        self.currMode = self.actor.config.get('rexm', 'mode') if mode is None else mode
        self.port = self.actor.config.get('rexm', 'port')

    def startCommunication(self, cmd=None):

        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the controller, fsm goes to LOADED
                 False, ret: if the communication failed with the controller, ret is the error, fsm goes to FAILED
        """
        self.myTMCM = rexm_drivers.TMCM(self.port) if self.currMode == 'operation' else RexmSimulator()

        ret = self.myTMCM.gap(11)

    def initialise(self, cmd):
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

        cmd.inform("text='seeking home ...'")
        self.moveAccurate(cmd, rexm.toDir['low'])

        ret = self.myTMCM.sap(1, 0)  # set 0 as home

    def getStatus(self, cmd=None, doFinish=True):
        """getStatus
        position is nan if the controller is unreachable
        :param cmd,
        :return True, state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
                 False, state, mode, nan, nan, nan, nan, nan, nan if not initialised or an error had occured
        """

        self.currPos = "undef"
        ender = cmd.finish if doFinish else cmd.inform
        fender = cmd.fail if doFinish else cmd.warn

        if self.fsm.current in ['IDLE', 'BUSY', 'LOADED']:
            try:
                self.checkStatus(cmd, doClose=doFinish)
                self.currPos = rexm.switch[(self.positionA, self.positionB)] if (self.positionA,
                                                                                 self.positionB) in rexm.switch else "undef"
            except Exception as e:
                cmd.warn("text='error during status : %s" % e)
                ender = fender

        ender("rexm=%s,%s,%s" % (self.fsm.current, self.currMode, self.currPos))

    def abort(self, cmd):
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
        t = dt.now()
        ts = dt.now()
        try:
            self.myTMCM.stop()
            cmd.inform("text='stopping rexm movement'")
            while self.isMoving:
                if (dt.now() - t).total_seconds() > 5:
                    raise Exception("timeout aborting")
                if (dt.now() - ts).total_seconds() > 2:
                    self.checkStatus(cmd)
                    self.myTMCM.stop()
                    ts = dt.now()
                else:
                    self.checkStatus(cmd, doShow=False)
            self.checkStatus(cmd)
        except Exception as e:
            cmd.warn("text='failed to stop rexm movement %s'" % e)
            raise

    def checkStatus(self, cmd, doClose=False, doShow=True):
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
        time.sleep(0.01)

        self.positionA = self.myTMCM.gap(11)
        self.positionB = self.myTMCM.gap(10)
        self.speed = self.myTMCM.gap(3, fmtRet='>BBBBiB')
        self.currPos = self.myTMCM.gap(1, doClose=doClose, fmtRet='>BBBBiB')

        if doShow:
            cmd.inform("rexmInfo=%i,%i,%i,%i" % (self.positionA, self.positionB, self.speed, self.currPos))

    @busy
    def moveTo(self, cmd, position):
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

        try:
            self.moveAccurate(cmd, rexm.toDir[position])
            return True
        except Exception as e:
            cmd.warn("text='failed to command rexm movement %s'" % e)
            return False

    def moveAccurate(self, cmd, direction):
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
        self.checkStatus(cmd)
        if not self.switchOn(direction):
            self.stopAndMove(cmd, direction, self.myTMCM.DISTANCE_MAX, self.myTMCM.g_speed)

        else:
            cmd.inform("text='already at position %s'" % rexm.toPos[direction])
            return

        cmd.inform("text='arrived at position %s" % rexm.toPos[direction])

        cmd.inform("text='adjusting position backward %s" % rexm.toPos[direction])
        self.stopAndMove(cmd, not direction, 10, self.myTMCM.g_speed / 3, bool=True)

        cmd.inform("text='adjusting position forward %s" % rexm.toPos[direction])
        self.stopAndMove(cmd, direction, 10, self.myTMCM.g_speed / 3)

        cmd.inform("text='arrived at desired position %s" % rexm.toPos[direction])

    def stopAndMove(self, cmd, direction, distance, speed, bool=False):

        self.hasStarted = False
        cond = direction if not bool else not direction
        time.sleep(0.1)
        self.abort(cmd)

        cmd.inform("text='moving to %s, %i, %.2f" % (rexm.toPos[direction], distance, speed))
        time.sleep(0.1)
        ok = self.myTMCM.MVP(direction, distance, speed)

        t = dt.now()
        ts = dt.now()

        while self.switchOn(cond) == bool:
            self.checkStart(t)
            if (dt.now() - t).total_seconds() > 200:
                raise Exception("timeout commanding MOVE")

            if (dt.now() - ts).total_seconds() > 2:
                self.checkStatus(cmd)
                ts = dt.now()
            else:
                self.checkStatus(cmd, doShow=False)

        self.abort(cmd)
        time.sleep(0.1)
        self.checkStatus(cmd)

    def switchOn(self, direction):
        return self.positionA if direction == 0 else self.positionB

    def checkStart(self, t0):

        if (dt.now() - t0).total_seconds() > 3 and not self.hasStarted:
            if not self.isMoving:
                raise Exception("timeout isMoving")
            self.hasStarted = True
