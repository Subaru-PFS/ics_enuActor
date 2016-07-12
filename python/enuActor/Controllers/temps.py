#!/usr/bin/env python
# encoding: utf-8

import logging
import socket

from Controllers.device import Device
from Controllers.Simulator.tempsimulator import TempSimulator


class temps(Device):
    timeout = 5

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        super(temps, self).__init__(actor, name)

        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.EOL = '\n'

    def loadCfg(self, cmd):
        self.currMode = self.actor.config.get('temps', 'mode')
        self.host = self.actor.config.get('temps', 'host')
        self.port = int(self.actor.config.get('temps', 'port'))
        cmd.finish("text='com ok'")
        return True

    def startCommunication(self, cmd):
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) if self.currMode == 'operation' else TempSimulator()
        self._s.settimeout(temps.timeout)
        cmd.inform("text='Connecting to LAKESHORE Controller in %s ...'"% self.currMode)

        try:
            self._s.connect((self.host, self.port))
        except Exception as inst:
            cmd.fail("text=error : %s " % inst)
            return False

        return True

    def fetchTemps(self, cmd):
        message = "MEAS"
        if self.safeSend(cmd, message):
            ok, ret = self.safeRecv(cmd)
            if ok:
                return True, ret

        return False, ''

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
