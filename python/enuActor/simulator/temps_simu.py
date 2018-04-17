#!/usr/bin/env python

import random
import time
import socket
import numpy as np


class TempsSim(socket.socket):
    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
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

        temps = 20 * np.ones(4) + np.array([random.gauss(mu=0, sigma=0.2) for i in range(4)])
        self.buf.append('%s\r\n' % ','.join(['%.2f' % t for t in temps]))

    def recv(self, buffersize, flags=None):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()


    def close(self):
        pass
