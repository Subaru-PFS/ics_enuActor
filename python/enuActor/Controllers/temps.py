#!/usr/bin/env python
# encoding: utf-8

import logging
import socket

import numpy as np

from Controllers.device import Device
from Controllers.Simulator.temps_simu import TempsSimulator
from enuActor.Controllers.wrap import safeCheck
import enuActor.Controllers.bufferedSocket as bufferedSocket


class temps(Device):
    timeout = 5

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        super(temps, self).__init__(actor, name)

        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.sock = None
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

        try:
            self.currMode = self.actor.config.get('temps', 'mode') if mode is None else mode
            self.host = self.actor.config.get('temps', 'host')
            self.port = int(self.actor.config.get('temps', 'port'))

        except Exception as e:
            return False, 'Config file badly formatted, Exception : %s ' % str(e)

        cmd.inform("text='config File successfully loaded")
        return True, ''

    def startCommunication(self, cmd):
        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the board, fsm (LOADING => LOADED)
                 False, ret: if the communication failed with the board, ret is the error, fsm (LOADING => FAILED)
        """

        self.tempsSimu = TempsSimulator() if self.currMode == "simulation" else None  # Create new simulator
        cmd.inform("text='Connecting to lakeshore Controller in ...%s'" % self.currMode)
        try:
            s = self.connectSock(cmd)
            return True, "Connected to lakeshore Controller"
        except Exception as e:
            return False, e

    @safeCheck
    def initialise(self, e):
        """ Initialise the temperature controller

        wrapper @safeCheck handles the state machine
        :param e : fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """
        cmd = e.cmd if hasattr(e, "cmd") else self.actor.bcast

        try:
            reply = self.sendOneCommand("MEAS", doClose=False, cmd=cmd)
            temps = reply.split(',')
            if len(temps) == 8:
                for t in temps:
                    if not 0 <= float(t) < 30:
                        return False, "Temperatures values wrong : %.1f" % t
                return True, 'Temps Successfully initialised'
            else:
                return False, "Controller is not returning correct values"

        except Exception as e:
            return False, "failed to initialise for %s: %s" % (self.name, e)

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

    def connectSock(self, cmd):
        """ Connect socket if self.sock is None

        :param cmd : current command,
        :return: sock in operation
                 temps simulator in simulation
        """
        if self.sock is None:
            try:
                s = socket.socket(socket.AF_INET,
                                  socket.SOCK_STREAM) if self.currMode == "operation" else self.tempsSimu
                s.settimeout(1.0)
            except socket.error as e:
                cmd.warn('text="failed to create socket for %s: %s"' % (self.name, e))
                raise
            try:
                s.connect((self.host, self.port))
            except socket.error as e:
                cmd.warn('text="failed to connect to %s: %s"' % (self.name, e))
                raise
            self.sock = s

        return self.sock

    def closeSock(self, cmd):
        """ close socket

        :param cmd : current command,
        :return: sock in operation
                 temps simulator in simulation
        """
        if self.sock is not None:
            try:
                self.sock.close()
            except socket.error as e:
                cmd.warn('text="failed to close socket for %s: %s"' % (self.name, e))

        self.sock = None

    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
        """ Send one command and return one response.

        Args
        ----
        cmdStr : str
           The command to send.
        doClose : bool
           If True (the default), the device socket is closed before returning.

        Returns
        -------
        str : the single response string, with EOLs stripped.

        Raises
        ------
        IOError : from any communication errors.
        """

        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        s = self.connectSock(cmd)
        try:
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to send to temperature controller: %s"' % (e))
            raise

        reply = self.getOneResponse(sock=s, cmd=cmd)
        if doClose:
            self.closeSock(cmd)

        return reply

    def getOneResponse(self, sock=None, cmd=None):
        if sock is None:
            sock = self.connectSock(cmd)

        ret = self.ioBuffer.getOneResponse(sock=sock, cmd=cmd)
        reply = ret.strip()

        self.logger.debug('received %r', reply)
        if cmd is not None:
            cmd.diag('text="received %r"' % reply)

        return reply
