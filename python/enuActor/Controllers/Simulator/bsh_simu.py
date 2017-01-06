#!/usr/bin/env python

import time
import socket


class BshSimulator(socket.socket):
    statword = {0: "01001000", 1: "10010000", 2: "01001000"}

    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.send = self.fakeSend
        self.recv = self.fakeRecv
        self.g_aduty = 0
        self.g_aperiod = 100
        self.bia_mode = 0
        self.pulse_on = 0
        self.statword = BshSimulator.statword[self.bia_mode]

        self.buf = []

    def connect(self, (ip, port)):
        time.sleep(0.5)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def fakeSend(self, mycommand):
        time.sleep(0.1)
        self.cmdnok = 2
        self.statword = BshSimulator.statword[self.bia_mode]
        if self.bia_mode == 0:  # IDLE STATE
            if mycommand == "bia_on\r\n":
                self.bia_mode = 2
                self.cmdnok = 0
            elif mycommand == "shut_open\r\n":
                self.bia_mode = 1
                self.cmdnok = 0

        elif self.bia_mode == 1:  # SHUTTER STATE
            if mycommand == "shut_close\r\n":
                self.bia_mode = 0
                self.cmdnok = 0
            elif mycommand == "bia_on\r\n":
                self.buf.append("intlk")
                self.cmdnok = 1

        elif self.bia_mode == 2:  # BIA STATE
            if mycommand == "bia_off\r\n":
                self.bia_mode = 0
                self.cmdnok = 0
            elif mycommand == "shut_open\r\n":
                self.buf.append("intlk")
                self.cmdnok = 1

        if mycommand == "init\r\n":
            self.bia_mode = 0
            self.cmdnok = 0

        if mycommand == "statword\r\n":
            self.buf.append(self.statword)
            self.cmdnok = 1

        if mycommand == "status\r\n":
            self.buf.append(self.bia_mode)
            self.cmdnok = 1

        if mycommand[:10] == "set_period":
            self.g_aperiod = int(mycommand[10:])
            self.cmdnok = 0

        if mycommand[:8] == "set_duty":
            self.g_aduty = int(mycommand[8:])
            self.cmdnok = 0

        if mycommand == "get_period\r\n":
            self.buf.append(self.g_aperiod)
            self.cmdnok = 1

        if mycommand == "get_duty\r\n":
            self.buf.append(self.g_aduty)
            self.cmdnok = 1

        if mycommand == "pulse_on\r\n":
            self.pulse_on = 1
            self.cmdnok = 0

        if mycommand == "pulse_off\r\n":
            self.pulse_on = 0
            self.cmdnok = 0

        if self.cmdnok < 2:
            self.buf.append("ok\r\n")

        else:
            self.buf.append("nok\r\n")

    def sendall(self, fullCmd):
        self.fakeSend(fullCmd)

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret)

    def close(self):
        pass
