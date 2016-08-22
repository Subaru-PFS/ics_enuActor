#!/usr/bin/env python
import time


class RexmSimulator(object):
    def __init__(self):
        super(RexmSimulator, self).__init__()

        self.buf = []

    def settimeout(self, timeout):
        if type(timeout) not in [int, float]:
            raise TypeError

    def connect(self, (ip, port)):
        time.sleep(0.5)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def send(self, message):

        self.buf.append("medium")

    def recv(self, buffer_size):
        time.sleep(0.5)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return ret