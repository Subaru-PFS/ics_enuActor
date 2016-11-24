#!/usr/bin/env python
# encoding: utf-8

import logging

import numpy as np

from Controllers.device import Device
from Controllers.Simulator.temps_simu import TempsSimulator
import enuActor.Controllers.bufferedSocket as bufferedSocket


class temps(Device):
    timeout = 5

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        super(temps, self).__init__(actor, name)

        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.sock = None
        self.simulator = None
        self.EOL = '\n'
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')

    def loadCfg(self, cmd, mode=None):
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """
        self.actor.reloadConfiguration(cmd=cmd)

        self.currMode = self.actor.config.get('temps', 'mode') if mode is None else mode
        self.host = self.actor.config.get('temps', 'host')
        self.port = int(self.actor.config.get('temps', 'port'))

    def startCommunication(self, cmd):
        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the board, fsm (LOADING => LOADED)
                 False, ret: if the communication failed with the board, ret is the error, fsm (LOADING => FAILED)
        """
        self.simulator = TempsSimulator() if self.currMode == "simulation" else None  # Create new simulator

        s = self.connectSock()

    def initialise(self, cmd):
        """ Initialise the temperature controller

        wrapper @safeCheck handles the state machine
        :param e : fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """

        reply = self.sendOneCommand("MEAS", doClose=False, cmd=cmd)

        temps = reply.split(',')
        if len(temps) == 8:
            for t in temps:
                if not 0 <= float(t) < 30:
                    raise Exception("Temperatures values wrong : %.1f" % t)
        else:
            raise Exception("Controller is not returning correct values")

    def getStatus(self, cmd=None, doFinish=True):
        """getStatus
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, state, mode, 8*temperature
                 False, state, mode, 8*nan if not initialised or an error had occured
        """

        if self.fsm.current in ['IDLE']:
            ok, temps = self.fetchTemps(cmd)
        else:
            ok, temps = True, ','.join(["%.2f" % t for t in [np.nan] * 8])

        ender = cmd.finish if doFinish else cmd.inform
        fender = cmd.fail if doFinish else cmd.warn

        ender = ender if ok else fender
        ender("temps=%s,%s,%s" % (self.fsm.current, self.currMode, temps))

    def fetchTemps(self, cmd):
        """fetchTemps
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, 8*temperature
                 False, 8*nan if not initialised or an error had occured
        """

        try:
            reply = self.sendOneCommand("MEAS", doClose=True, cmd=cmd)
            return True, reply
        except Exception as e:
            cmd.warn("text='failed to get Temperature :%s'" % e)
            return False, ','.join(["%.2f" % t for t in [np.nan] * 8])
