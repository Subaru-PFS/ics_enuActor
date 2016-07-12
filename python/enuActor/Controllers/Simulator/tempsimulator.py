#!/usr/bin/env python

from random import randrange
import time

import numpy as np


class TempSimulator(object):
    def __init__(self):
        super(TempSimulator, self).__init__()
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
        temps = 20 * np.ones(8)
        self.buf.append(','.join(['%.2f' % (t + 0.1 * randrange(-2, 2)) for t in temps]))

    def recv(self, buffer_size):
        time.sleep(0.5)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return ret
