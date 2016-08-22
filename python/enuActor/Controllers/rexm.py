#!/usr/bin/env python

import logging
import socket

from Controllers.device import Device
from Controllers.Simulator.rexm_simu import RexmSimulator


class rexm(Device):
    timeout = 5

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        super(rexm, self).__init__(actor, name)

        self.logger = logging.getLogger('rexm')
        self.logger.setLevel(loglevel)

        self.EOL = '\n'
        self.currPos = 'nan'


    def loadCfg(self, cmd):
        self.currMode = self.actor.config.get('rexm', 'mode')
        self.host = self.actor.config.get('rexm', 'host')
        self.port = int(self.actor.config.get('rexm', 'port'))
        return True

    def startCommunication(self, cmd):
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) if self.currMode == 'operation' else RexmSimulator()
        self._s.settimeout(rexm.timeout)
        cmd.inform("text='Connecting to REXM Controller in %s ...'" % self.currMode)

        try:
            self._s.connect((self.host, self.port))
        except Exception as inst:
            cmd.fail("text=error : %s " % inst)
            return False

        return True

    def initialise(self, cmd):
        message = "origin search"
        if self.safeSend(cmd, message):
            ok, ret = self.safeRecv(cmd)
            if ok:
                return True
        return False

    def getPosition(self, cmd):
        message = "position ?"
        if self.safeSend(cmd, message):
            ok, pos = self.safeRecv(cmd)
            if ok:
                self.currPos = pos
                return True
        return False


    def safeSend(self, cmd, message):
        try:
            self._s.send(message)
            return True
        except Exception as inst:
            cmd.fail("text='error : %s '" % inst)
            return False

    def safeRecv(self, cmd):
        try:
            ret = self._s.recv(1024)
            return True, ret
        except Exception as inst:
            cmd.fail("text='error : %s '" % inst)
            return False, ''
