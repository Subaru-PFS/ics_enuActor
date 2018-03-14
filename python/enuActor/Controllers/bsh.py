#!/usr/bin/env python


import sys
import time
import datetime
from datetime import datetime as dt

import enuActor.Controllers.bufferedSocket as bufferedSocket
from enuActor.Controllers.Simulator.bsh_simu import BshSimulator
from enuActor.Controllers.device import Device
from enuActor.utils.wrap import busy



class bsh(Device):
    ilock_s_machine = {0: ("close", "off"),
                       10: ("close", "on"),
                       20: ("open", "off"),
                       30: ("openblue", "off"),
                       40: ("openred", "off")}

    shut_stat = [{0: "close", 1: "open"}, {0: "open", 1: "close"}, {0: "ok", 1: "error"}]
    in_position = {0: '010010',
                   10: '010010',
                   20: '100100',
                   30: '100010',
                   40: '010100'}

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

        self.mode = self.actor.config.get('bsh', 'mode') if mode is None else mode
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

        self.simulator = BshSimulator() if self.mode == "simulation" else None  # Create new simulator

        s = self.connectSock()

    def initialise(self, cmd):
        """| Initialise the interlock board, called y device.initDevice().

        - Send the bia config to the interlock board
        - Init the interlock state machine

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """

        self.setBiaConfig(cmd, self.biaPeriod, self.biaDuty, self.biaStrobe, doClose=False)
        self._sendOrder(cmd, 'init')

    @busy
    def switch(self, cmd, cmdStr):
        """| *wrapper @busy* handles the state machine.
        | Call bsh._safeSwitch() 

        :param cmd: on going command
        :param cmdStr: String command sent to the board
        :type cmdStr: str
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """

        return self._safeSwitch(cmd, cmdStr)

    @busy
    def expose(self, cmd, exptime, shutter):
        """| Command opening and closing of shutters with a chosen exposure time and publish keywords:

        - dateobs : exposure starting time isoformatted
        - transientTime : opening+closing shutters transition time
        - exptime : absolute exposure time

        :param cmd: on going command
        :param exptime: Exposure time
        :type exptime: float
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """
        try:
            expStart = dt.utcnow()

            if not self._safeSwitch(cmd, "%s_open" % shutter):
                raise Exception("OPEN failed")

            transientTime1 = (dt.utcnow() - expStart).total_seconds()

            self.getStatus(cmd, doFinish=False)
            if (self.shState not in ['open', 'openred', 'openblue']) or self.stopExposure:
                raise Exception("OPEN failed or exposure stopped")

            self.safeTempo(cmd, exptime - (dt.utcnow() - expStart).total_seconds())
            transientTime2 = dt.utcnow()

            if not self._safeSwitch(cmd, "%s_close" % shutter):
                raise Exception("CLOSE failed")

            expEnd = dt.utcnow()
            transientTime2 = (expEnd - transientTime2).total_seconds()

            self.getStatus(cmd, doFinish=False)
            if (self.shState not in ['close', 'openblue']) or self.stopExposure:
                raise Exception("CLOSE failed or exposure stopped")

            cmd.inform("dateobs=%s" % expStart.isoformat())
            cmd.inform("transientTime=%.3f" % (transientTime1 + transientTime2))
            cmd.inform("exptime=%.3f" % ((expEnd - expStart).total_seconds() - 0.5 * (transientTime1 + transientTime2)))

            return True

        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            cmd.warn("exptime=nan")
            if self.stopExposure:
                return self._safeSwitch(cmd, "shut_close")

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
                self.shState, self.biaState = self.checkStatus(cmd)
                self.getBiaConfig(cmd, doClose=True)

            except Exception as e:
                cmd.warn('text=%s' % self.actor.strTraceback(e))
                ender = fender

        talk = cmd.inform if ender != fender else cmd.warn

        talk("shutters=%s,%s,%s" % (self.fsm.current, self.mode, self.shState))
        ender("bia=%s,%s,%s" % (self.fsm.current, self.mode, self.biaState))

    def checkStatus(self, cmd):
        """| Get status from bsh board and update controller's attributes.
        | Warn the user if the shutters limits switch state does not match with interlock state machine

        :param cmd: on going command
        :raise: Exception if a command has failed
        :rtype: tuple
        :return: (shuttersPosition, biaState)
        """

        self.ilockState = self._ilockStat(cmd)
        statword = self._shutstat(cmd)

        if bsh.in_position[self.ilockState] != statword:
            cmd.warn("text='shutters not in position'")
            for i, shutter in enumerate(["shr", "shb"]):
                cmd.warn("%s=%s" % (
                    shutter, ','.join([bsh.shut_stat[j % 3][int(statword[j])] for j in range(i * 3, (i + 1) * 3)])))

        return bsh.ilock_s_machine[self.ilockState]

    def getBiaConfig(self, cmd, doClose=False):
        """|publish bia configuration keywords.

        - biaStrobe=off|on
        - biaConfig=period,duty

        :param cmd: current command,
        :param doClose: if True close socket
        :raise: Exception if a command has failed
        """
        biaStrobe, biaPeriod, biaDuty = self._biastat(cmd, doClose=doClose)
        cmd.inform("biaStrobe=%s" % biaStrobe)
        cmd.inform("biaConfig=%i,%i" % (biaPeriod, biaDuty))

        return biaStrobe, biaPeriod, biaDuty

    def setBiaConfig(self, cmd, biaPeriod=None, biaDuty=None, biaStrobe=None, doClose=False):
        """| Send new parameters for bia

        :param cmd: current command,
        :param biaPeriod: bia period for strobe mode
        :param biaDuty: bia duty cycle
        :param biaStrobe: **on** | **off**
        :type biaPeriod: int
        :type biaDuty: int
        :type biaStrobe: str
        :raise: Exception if a command has failed
        """

        if biaPeriod is not None:
            self._sendOrder(cmd, "set_period%i" % biaPeriod)

        if biaDuty is not None:
            self._sendOrder(cmd, "set_duty%i" % biaDuty)

        if biaStrobe is not None:
            self._sendOrder(cmd, "pulse_%s" % biaStrobe)

        self.biaStrobe, self.biaPeriod, self.biaDuty = self.getBiaConfig(cmd, doClose=doClose)

    def checkInterlock(self, shState, biaState, cmdStr):
        """| Check transition and raise Exception if cmdStr is violating shutters/bia interlock.

        :param shState: shutter state,
        :param biaState: bia state,
        :param cmdStr: command string
        :type shState: str
        :type biaState: str
        :type cmdStr: str
        :raise: Exception("Transition not allowed")
        """

        transition = {
            (("close", "off"), "shut_open"): (True, ""),
            (("close", "off"), "red_open"): (True, ""),
            (("close", "off"), "blue_open"): (True, ""),
            (("close", "off"), "shut_close"): (False, "shutters already closed"),
            (("close", "off"), "red_close"): (False, "red shutter already closed"),
            (("close", "off"), "blue_close"): (False, "blue shutter already closed"),
            (("close", "off"), "bia_off"): (False, "bia already off"),
            (("close", "off"), "bia_on"): (True, ""),

            (("close", "on"), "shut_open"): (False, "Interlock !"),
            (("close", "on"), "red_open"): (False, "Interlock !"),
            (("close", "on"), "blue_open"): (False, "Interlock !"),
            (("close", "on"), "shut_close"): (False, "shutters already closed"),
            (("close", "on"), "red_close"): (False, "red shutter already closed"),
            (("close", "on"), "blue_close"): (False, "blue shutter already closed"),
            (("close", "on"), "bia_off"): (True, ""),
            (("close", "on"), "bia_on"): (False, "bia already on"),

            (("open", "off"), "shut_open"): (False, "shutters already open"),
            (("open", "off"), "red_open"): (False, "shutters already open"),
            (("open", "off"), "blue_open"): (False, "shutters already open"),
            (("open", "off"), "shut_close"): (True, ""),
            (("open", "off"), "red_close"): (True, ""),
            (("open", "off"), "blue_close"): (True, ""),
            (("open", "off"), "bia_off"): (False, "bia already off"),
            (("open", "off"), "bia_on"): (False, "Interlock !"),

            (("openred", "off"), "shut_open"): (True, ""),
            (("openred", "off"), "red_open"): (False, "shutter red already open"),
            (("openred", "off"), "blue_open"): (True, ""),
            (("openred", "off"), "shut_close"): (True, ""),
            (("openred", "off"), "red_close"): (True, ""),
            (("openred", "off"), "blue_close"): (False, "shutter blue already closed"),
            (("openred", "off"), "bia_off"): (False, "bia already off"),
            (("openred", "off"), "bia_on"): (False, "Interlock !"),

            (("openblue", "off"), "shut_open"): (True, ""),
            (("openblue", "off"), "red_open"): (True, ""),
            (("openblue", "off"), "blue_open"): (False, "shutter blue already open"),
            (("openblue", "off"), "shut_close"): (True, ""),
            (("openblue", "off"), "red_close"): (False, "shutter red already closed"),
            (("openblue", "off"), "blue_close"): (True, ""),
            (("openblue", "off"), "bia_off"): (False, "bia already off"),
            (("openblue", "off"), "bia_on"): (False, "Interlock !"),

        }

        (ok, ret) = transition[(shState, biaState), cmdStr]
        if not ok:
            raise Exception("Transition not allowed : %s" % ret)

    def safeTempo(self, cmd, exptime, ti=0.01):
        """| Temporization, check every 0.01 sec for a user abort command.

        :param cmd: current command,
        :param exptime: exposure time,
        :type exptime: float
        :raise: Exception("Exposure aborted by user") if the an abort command has been received
        """

        t0 = dt.utcnow()
        tlim = t0 + datetime.timedelta(seconds=exptime)

        cmd.inform("integratingTime=%.2f" % exptime)
        cmd.inform("elapsedTime=%.2f" % (dt.utcnow() - t0).total_seconds())
        inform = dt.utcnow()

        while dt.utcnow() < tlim:
            if self.stopExposure:
                raise Exception("Exposure aborted by user")
            if (dt.utcnow() - inform).total_seconds() > 2:
                cmd.inform("elapsedTime=%.2f" % (dt.utcnow() - t0).total_seconds())
                inform = dt.utcnow()
            time.sleep(ti)

    def _safeSwitch(self, cmd, cmdStr):
        """| Send the command string to the interlock board.

        - Command bia or shutters
        - check is not cmdStr is breaking interlock

        :param cmd: on going command
        :param cmdStr: String command sent to the board
        :type cmdStr: str
        :return: - True if the command raise no error
                 - False if the command fail
        """

        try:
            self.checkInterlock(self.shState, self.biaState, cmdStr)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            return True

        try:
            self._sendOrder(cmd, cmdStr)

        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            return False

        return True

    def _ilockStat(self, cmd):
        """| check and return interlock board current state .

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        ilockState = self.sendOneCommand("status", doClose=False, cmd=cmd)

        return int(ilockState)

    def _shutstat(self, cmd):
        """| check and return shutter status word .

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        statword = self.sendOneCommand("statword", doClose=False, cmd=cmd)

        return bin(int(statword))[-6:]

    def _biastat(self, cmd, doClose=False):
        """| check and return current bia configuration.

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        biastat = self.sendOneCommand("get_param", doClose=doClose, cmd=cmd)
        strobe, period, duty = biastat.split(',')
        strobe = 'on' if int(strobe) else 'off'

        return strobe, int(period), int(duty)

    def _sendOrder(self, cmd, cmdStr):
        reply = self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
        if reply != "":
            raise Exception("%s  %s cmd has replied nok" % (cmdStr, self.name))
