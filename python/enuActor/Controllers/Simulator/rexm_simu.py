#!/usr/bin/env python
import time
from serial import Serial

class RexmSimulator(object):
    def __init__(self):
        super(RexmSimulator, self).__init__()

        self.buf = []
        self.portOpen = False

    def readable(self):
        return True

    def writable(self):
        return True

    def isOpen(self):
        return self.portOpen

    def open(self):
        self.portOpen = True

    def write(self, data):
        if data == "move":
            self.buf.append("ok")

    def readline(self, *args, **kwargs):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return ret