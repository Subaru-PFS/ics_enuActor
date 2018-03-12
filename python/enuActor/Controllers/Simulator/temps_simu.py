#!/usr/bin/env python

from random import randrange
import time
import socket
import numpy as np


class TempsSimulator(socket.socket):
    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.send = self.fakeSend
        self.recv = self.fakeRecv
        self.buf = []

    def connect(self, xxx_todo_changeme):
        (ip, port) = xxx_todo_changeme
        time.sleep(0.25)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def fakeSend(self, message):
        temps = 20 * np.ones(8)
        self.buf.append(','.join(['%.2f' % (t + 0.1 * randrange(-2, 2)) for t in temps])+'\r\n')

    def fakeRecv(self, buffer_size):
        time.sleep(0.25)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return ret

    def sendall(self, fullCmd):
        self.fakeSend(fullCmd)

    def close(self):
        pass