#!/usr/bin/env python


import sys
import time
from datetime import datetime as dt

import enuActor.Controllers.bufferedSocket as bufferedSocket
from enuActor.Controllers.Simulator.bsh_simu import BshSimulator
from enuActor.Controllers.device import Device
from enuActor.utils.wrap import busy, formatException

reload(bufferedSocket)


class bsh(Device):
    ilock_s_machine = {0: ("close", "off"), 1: ("open", "off"), 2: ("close", "on")}
    shut_stat = [{0: "close", 1: "open"}, {0: "open", 1: "close"}, {0: "ok", 1: "error"}]
    in_position = {0: '01001000', 1: '10010000', 2: '01001000'}

    def __init__(self, actor, name):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        Device.__init__(self, actor, name)

        self.shState = "undef"
        self.biaState = "undef"

        self.stopExposure = False
        self.ilockState = 0
        self.sock = None
        self.simulator = None
        self.EOL = '\r\n'

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='ok\r\n')

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice().
        | Convert to world tool and home.

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.actor.reloadConfiguration(cmd=cmd)

        self.currMode = self.actor.config.get('bsh', 'mode') if mode is None else mode
        self.host = self.actor.config.get('bsh', 'host')
        self.port = int(self.actor.config.get('bsh', 'port'))
        self.biaPeriod = int(self.actor.config.get('bsh', 'bia_period'))
        self.biaDuty = int(self.actor.config.get('bsh', 'bia_duty'))
        self.biaStrobe = self.actor.config.get('bsh', 'bia_strobe')

    def startCommunication(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        self.simulator = BshSimulator() if self.currMode == "simulation" else None  # Create new simulator

        s = self.connectSock()

    def initialise(self, cmd):
        """| Initialise the interlock board, called y device.initDevice().

        - Send the bia config to the interlock board
        - Init the interlock state machine

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """

        self.sendBiaConfig(cmd)

        reply = self.sendOneCommand("init", doClose=False, cmd=cmd)
        if reply != "":
            raise Exception("%s has replied nok" % self.name)
        time.sleep(0.4)  # Shutters closing/opening time is 0.4 need to be remove once limit check is implemented

    @busy
    def switch(self, cmd, cmdStr, doForce=False):
        """| *wrapper @busy* handles the state machine.
        | Call bsh._safeSwitch() 

        :param cmd: on going command
        :param cmdStr: String command sent to the board
        :type cmdStr: str
        :param doForce: Force transition (without breaking interlock) even if same state is required
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """

        return self._safeSwitch(cmd, cmdStr, doForce=doForce)

    @busy
    def expose(self, cmd, exptime, doForce=False):
        """| Command opening and closing of shutters with a chosen exposure time and publish keywords:

        - dateobs : exposure starting time isoformatted
        - transientTime : opening+closing shutters transition time
        - exptime : absolute exposure time

        :param cmd: on going command
        :param exptime: Exposure time
        :type exptime: float
        :param doForce: Force transition (without breaking interlock) even if same state is required
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """

        try:
            expStart = dt.utcnow()

            if not self._safeSwitch(cmd, "shut_open", doForce=doForce):
                raise Exception("exposure has failed")

            transientTime1 = (dt.utcnow() - expStart).total_seconds()

            self.getStatus(cmd, doFinish=False)
            if (self.shState != "open") or self.stopExposure:
                raise Exception("%s exposure stopped")

            self.safeTempo(cmd, exptime - (dt.utcnow() - expStart).total_seconds())
            transientTime2 = dt.utcnow()

            if not self._safeSwitch(cmd, "shut_close", doForce=doForce):
                raise Exception("exposure has failed")

            expEnd = dt.utcnow()
            transientTime2 = (expEnd - transientTime2).total_seconds()

            self.getStatus(cmd, doFinish=False)
            if (self.shState != "close") or self.stopExposure:
                raise Exception("%s exposure stopped")

            cmd.inform("dateobs=%s" % expStart.isoformat())
            cmd.inform("transientTime=%.3f" % (transientTime1 + transientTime2))
            cmd.inform("exptime=%.3f" % ((expEnd - expStart).total_seconds() - 0.5 * (transientTime1 + transientTime2)))

            return True

        except Exception as e:
            cmd.warn("text='%s expose failed %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))
            cmd.warn("exptime=nan")
            if self.stopExposure:
                return self._safeSwitch(cmd, "shut_close", doForce=doForce)

            return False

    def getStatus(self, cmd, doFinish=True):
        """| Call bsh._checkStatus() and publish shutters, bia keywords:

        - shutters = fsm_state, mode, position
        - bia = fsm_state, mode, state

        :param cmd: on going command
        :param doFinish: if True finish the command
        """

        ender = cmd.finish if doFinish else cmd.inform
        fender = cmd.fail if doFinish else cmd.warn
        self.shState, self.biaState = "undef", "undef"

        if self.fsm.current in ['LOADED', 'IDLE', 'BUSY']:
            try:
                (self.shState, self.biaState) = self._checkStatus(cmd)

            except Exception as e:
                cmd.warn("text='%s getStatus failed %s'" % (self.name.upper(),
                                                            formatException(e, sys.exc_info()[2])))
                ender = fender

        talk = cmd.inform if ender != fender else cmd.warn

        talk("shutters=%s,%s,%s" % (self.fsm.current, self.currMode, self.shState))
        ender("bia=%s,%s,%s" % (self.fsm.current, self.currMode, self.biaState))

    def _safeSwitch(self, cmd, cmdStr, doForce=False):
        """| Send the command string to the interlock board.

        - Command bia or shutters
        - check is not cmdStr is breaking interlock

        :param cmd: on going command
        :param cmdStr: String command sent to the board
        :type cmdStr: str
        :param doForce: Force transition (without breaking interlock) even if same state is required
        :return: - True if the command raise no error
                 - False if the command fail
        """

        try:
            self.checkInterlock(self.shState, self.biaState, cmdStr, doForce=doForce)
        except Exception as e:
            cmd.warn("text='%s switch failed %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))
            return True

        try:
            reply = self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            if reply != "":
                raise Exception("warning %s return %s" % (cmdStr, reply))

        except Exception as e:
            cmd.warn("text='%s switch failed %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))
            return False

        time.sleep(0.4)  # Shutters closing/opening time is 0.4

        return True

    def _checkStatus(self, cmd):
        """| Get status from bsh board and update controller's attributes.
        | Warn the user if the shutters limits switch state does not match with interlock state machine

        :param cmd: on going command
        :raise: Exception if a command has failed
        :rtype: tuple
        :return: (shuttersPosition, biaState)
        """

        reply = self.sendOneCommand("status", doClose=False, cmd=cmd)
        self.ilockState = int(reply)

        statword = self.sendOneCommand("statword", doClose=True, cmd=cmd)
        if bsh.in_position[self.ilockState] != statword:
            cmd.warn("text='shutters not in position'")
            for i, shutter in enumerate(["shr", "shb"]):
                cmd.warn("%s=%s" % (
                    shutter, ','.join([bsh.shut_stat[j % 3][int(statword[j])] for j in range(i * 3, (i + 1) * 3)])))

        return bsh.ilock_s_machine[self.ilockState]

    def sendBiaConfig(self, cmd, biaPeriod=None, biaDuty=None, biaStrobe=None, doClose=False):
        """| Send new parameters for bia and publish bia configuration keywords.

        - biaStrobe=off|on
        - biaConfig=period,duty

        :param cmd: current command,
        :param biaPeriod: bia period for strobe mode
        :param biaDuty: bia duty cycle
        :param biaStrobe: **on** | **off**
        :type biaPeriod: int
        :type biaDuty: int
        :type biaStrobe: str
        :raise: Exception if a command has failed
        """

        biaPeriod = self.biaPeriod if biaPeriod is None else biaPeriod
        biaDuty = self.biaDuty if biaDuty is None else biaDuty
        biaStrobe = self.biaStrobe if biaStrobe is None else biaStrobe

        reply = self.sendOneCommand("set_period%i" % biaPeriod, doClose=False, cmd=cmd)
        reply = self.sendOneCommand("set_duty%i" % biaDuty, doClose=False, cmd=cmd)

        period = self.sendOneCommand("get_period", doClose=False, cmd=cmd)
        duty = self.sendOneCommand("get_duty", doClose=False, cmd=cmd)

        reply = self.sendOneCommand("pulse_%s" % biaStrobe, doClose=doClose, cmd=cmd)

        self.biaStrobe = biaStrobe
        cmd.inform("biaStrobe=%s" % biaStrobe)

        self.biaPeriod, self.biaDuty = int(period), int(duty)
        cmd.inform("biaConfig=%s,%s" % (period, duty))

    def checkInterlock(self, shState, biaState, cmdStr, doForce=False):
        """| Check transition and raise Exception if cmdStr is violating shutters/bia interlock.

        :param shState: shutter state,
        :param biaState: bia state,
        :param cmdStr: command string
        :param doForce: Force transition (without breaking interlock) even if same state is required
        :type shState: str
        :type biaState: str
        :type cmdStr: str
        :raise: Exception("Transition not allowed")
        """

        transition = {
            (("close", "off"), "shut_open"): (True, ""),
            (("close", "off"), "bia_off"): (doForce, "bia already off"),
            (("close", "off"), "bia_on"): (True, ""),
            (("close", "off"), "shut_close"): (doForce, "shutters already closed"),
            (("close", "on"), "shut_close"): (doForce, "shutters already closed"),
            (("close", "on"), "shut_open"): (False, "Interlock !"),
            (("close", "on"), "bia_off"): (True, ""),
            (("close", "on"), "bia_on"): (doForce, "bia already on"),
            (("open", "off"), "shut_close"): (True, ""),
            (("open", "off"), "shut_open"): (doForce, "shutters already open"),
            (("open", "off"), "bia_off"): (doForce, "bia already off"),
            (("open", "off"), "bia_on"): (False, "Interlock !")}

        (ok, ret) = transition[(shState, biaState), cmdStr]
        if not ok:
            raise Exception("Transition not allowed : %s" % ret)

    def safeTempo(self, cmd, exptime):
        """| Temporization, check every 0.1 sec for a user abort command.

        :param cmd: current command,
        :param exptime: exposure time,
        :type exptime: float
        :raise: Exception("Exposure aborted by user") if the an abort command has been received
        """

        ti = 0.1
        cmd.inform("integratingTime=%.2f" % exptime)
        for i in range(int(exptime // ti)):
            if self.stopExposure:
                raise Exception("Exposure aborted by user")
            time.sleep(ti)

        time.sleep(exptime % ti)
