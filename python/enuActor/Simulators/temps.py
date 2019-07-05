#!/usr/bin/env python

import socket
import time

import numpy as np


class TempsSim(socket.socket):
    nProbes = 10

    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.offsets = np.zeros(TempsSim.nProbes)
        self.buf = []

    def connect(self, server):
        (ip, port) = server
        time.sleep(0.5)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def sendall(self, cmdStr, flags=None):
        cmdStr = cmdStr.decode()
        if 'MEAS:TEMP' in cmdStr:
            temps = np.random.normal(20, 0.035, size=TempsSim.nProbes)
            self.buf.append('%s\n' % ','.join(['%.3f' % t for t in temps]))
        elif 'MEAS:FRES' in cmdStr:
            res = np.random.normal(110, 0.035, size=TempsSim.nProbes) + self.offsets
            self.buf.append('%s\n' % ','.join(['%.3f' % t for t in res]))
        elif 'SYST:CTYP' in cmdStr:
            self.buf.append('Agilent Technologies,34901A,0,2.3\n')
        elif 'SYST:ERR?' in cmdStr:
            self.buf.append('+0,"No error"\n')
        elif 'SYST:VERS?' in cmdStr:
            self.buf.append('1994.0\n')

    def biaOn(self):
        self.offsets[3] = 5

    def biaOff(self):
        self.offsets[3] = 0

    def recv(self, buffersize, flags=None):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
