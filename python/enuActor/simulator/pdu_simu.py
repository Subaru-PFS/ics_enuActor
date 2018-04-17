#!/usr/bin/env python

import socket
import time


class PduSim(socket.socket):
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

        self.buf.append('ok\r\n')

    def recv(self, buffersize, flags=None):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()


    def close(self):
        pass
