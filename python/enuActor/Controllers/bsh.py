#!/usr/bin/env python


from datetime import datetime as dt
import sys

from enuActor.Controllers.device import Device
import enuActor.Controllers.bufferedSocket as bufferedSocket
from enuActor.utils.wrap import busy
from enuActor.Controllers.Simulator.bsh_simu import BshSimulator

reload(bufferedSocket)


class bsh(Device):
    ilock_s_machine = {0: ("close", "off"), 1: ("open", "off"), 2: ("close", "on")}
    shut_stat = [{0: "close", 1: "open"}, {0: "open", 1: "close"}, {0: "ok", 1: "error"}]
    in_position = {0: '01001000', 1: '10010000', 2: '01001000'}

    def __init__(self, actor, name):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #

        Device.__init__(self, actor, name)

        self.shState = "undef"
        self.biaState = "undef"
        self.ilockState = 0
        self.sock = None
        self.simulator = None
        self.EOL = '\r\n'

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='ok\r\n')

    def loadCfg(self, cmd, mode=None):
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """
        self.actor.reloadConfiguration(cmd=cmd)

        self.currMode = self.actor.config.get('bsh', 'mode') if mode is None else mode
        self.host = self.actor.config.get('bsh', 'host')
        self.port = int(self.actor.config.get('bsh', 'port'))
        self.biaPeriod = int(self.actor.config.get('bsh', 'bia_period'))
        self.biaDuty = int(self.actor.config.get('bsh', 'bia_duty'))

    def startCommunication(self, cmd):
        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the board, fsm (LOADING => LOADED)
                 False, ret: if the communication failed with the board, ret is the error, fsm (LOADING => FAILED)
        """

        self.simulator = BshSimulator() if self.currMode == "simulation" else None  # Create new simulator

        s = self.connectSock()

    def initialise(self, cmd):
        """ Initialise the bsh board

        - send the bia config to the board
        - init the interlock state machine

        :param e : fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """
        self.sendBiaConfig(cmd)

        reply = self.sendOneCommand("init", doClose=False, cmd=cmd)
        if reply != "":
            raise Exception("%s has replied nok" % self.name)

    @busy
    def switch(self, cmd, cmdStr, doForce=False):
        """switch
        Command bia or shutters
        check that cmdStr is not breaking interlock

        :param cmd
        :return: True, ''
                 False, ret : if a an error ret occured
        """
        try:
            self.checkInterlock(self.shState, self.biaState, cmdStr, doForce=doForce)
        except Exception as e:
            cmd.warn("text='%s switch failed %s'" % (self.name.upper(), self.formatException(e, sys.exc_info()[2])))
            return True

        try:
            reply = self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            if reply == "":
                return True
            else:
                raise Exception("warning %s return %s" % (cmdStr, reply))

        except Exception as e:
            cmd.warn("text='%s switch failed %s'" % (self.name.upper(), self.formatException(e, sys.exc_info()[2])))
            return False

    def getStatus(self, cmd, doFinish=True):
        """getStatus
        Get status from bsh board if it has been initialised

        :param cmd
        :return: True, [(shutters=state, mode, position),(bia=state, mode, position)]
                 False, [(shutters=state, mode, undef),(bia=state, mode, undef)]
        """
        ender = cmd.finish if doFinish else cmd.inform
        fender = cmd.fail if doFinish else cmd.warn
        (self.shState, self.biaState) = ("undef", "undef")

        if self.fsm.current in ['LOADED', 'IDLE', 'BUSY']:
            try:
                (self.shState, self.biaState) = self._getCurrentStatus(cmd)

            except Exception as e:
                cmd.warn("text='%s getStatus failed %s'" % (self.name.upper(),
                                                            self.formatException(e, sys.exc_info()[2])))
                ender = fender

        talk = cmd.inform if ender != fender else cmd.warn

        talk("shutters=%s,%s,%s,%s" % (self.fsm.current, self.currMode, self.shState, dt.utcnow().isoformat()))
        ender("bia=%s,%s,%s" % (self.fsm.current, self.currMode, self.biaState))

    def _getCurrentStatus(self, cmd):
        """getStatus
        Get status from bsh board if it has been initialised

        :param cmd
        :return: True, current position from interlock state machine
                 False, (undef, undef) if an error has occured
        """

        reply = self.sendOneCommand("status", doClose=False, cmd=cmd)
        self.ilockState = int(reply)

        statword = self.sendOneCommand("statword", doClose=True, cmd=cmd)
        if bsh.in_position[self.ilockState] != statword:
            cmd.warn("text='shutters not in position'")
            for i, shutter in enumerate(["shb", "shr"]):
                cmd.warn("%s=%s" % (
                    shutter, ','.join([bsh.shut_stat[j % 3][int(statword[j])] for j in range(i * 3, (i + 1) * 3)])))

        return bsh.ilock_s_machine[self.ilockState]

    def sendBiaConfig(self, cmd, biaPeriod=None, biaDuty=None, doClose=False):
        """ Send and Display bia config

        :param cmd : current command,
               biaPeriod : bia period,
               biaDuty: bia duty,
        :return: True : if every steps are successfully operated, cmd not finished,
                 False : if a command fail, command is finished with cmd.fail
        """
        biaPeriod = self.biaPeriod if biaPeriod is None else biaPeriod
        biaDuty = self.biaDuty if biaDuty is None else biaDuty

        reply = self.sendOneCommand("set_period%i" % biaPeriod, doClose=False, cmd=cmd)
        reply = self.sendOneCommand("set_duty%i" % biaDuty, doClose=False, cmd=cmd)

        period = self.sendOneCommand("get_period", doClose=False, cmd=cmd)
        duty = self.sendOneCommand("get_duty", doClose=doClose, cmd=cmd)

        self.biaPeriod, self.biaDuty = period, duty
        cmd.inform("biaConfig=%s,%s" % (period, duty))

    def checkInterlock(self, shState, biaState, cmdStr, doForce=False):

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
