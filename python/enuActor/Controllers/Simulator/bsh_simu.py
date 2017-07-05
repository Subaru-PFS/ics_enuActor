# !/usr/bin/env python

import time
import socket


class BshSimulator(socket.socket):
    statword = {0: 82, 10: 82, 20: 100, 30: 98, 40: 84}

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
        cmdOk = False
        self.statword = BshSimulator.statword[self.bia_mode]
        if self.bia_mode == 0:  # IDLE STATE
            if mycommand == "bia_on\r\n":
                bia_mode = 10
                cmdOk = True
            elif mycommand == "shut_open\r\n":
                bia_mode = 20
                cmdOk = True
            elif mycommand == "blue_open\r\n":
                bia_mode = 30
                cmdOk = True
            elif mycommand == "red_open\r\n":
                bia_mode = 40
                cmdOk = True
            elif mycommand == "init\r\n":
                bia_mode = 0
                cmdOk = True

        elif self.bia_mode == 10:  # BIA IS ON
            if mycommand == "bia_off\r\n":
                bia_mode = 0
                cmdOk = True
            elif mycommand == "init\r\n":
                bia_mode = 0
                cmdOk = True

        elif self.bia_mode == 20:  # SHUTTERS OPEN
            if mycommand == "shut_close\r\n":
                bia_mode = 0
                cmdOk = True
            elif mycommand == "blue_close\r\n":
                bia_mode = 40
                cmdOk = True
            elif mycommand == "red_close\r\n":
                bia_mode = 30
                cmdOk = True
            if mycommand == "init\r\n":
                bia_mode = 0
                cmdOk = True

        elif self.bia_mode == 30:  # SHUTTERS OPEN
            if mycommand == "shut_open\r\n":
                bia_mode = 20
                cmdOk = True
            elif mycommand == "blue_close\r\n":
                bia_mode = 0
                cmdOk = True
            elif mycommand == "red_close\r\n":
                bia_mode = 20
                cmdOk = True
            if mycommand == "init\r\n":
                bia_mode = 0
                cmdOk = True

        elif self.bia_mode == 40:  # SHUTTERS OPEN
            if mycommand == "shut_open\r\n":
                bia_mode = 20
                cmdOk = True
            elif mycommand == "blue_close\r\n":
                bia_mode = 20
                cmdOk = True
            elif mycommand == "red_close\r\n":
                bia_mode = 0
                cmdOk = True
            if mycommand == "init\r\n":
                bia_mode = 0
                cmdOk = True
        if bia_mode != self.bia_mode:
            self.bia_mode = bia_mode
            if bia_mode != 10:
                time.sleep(0.35)  # Shutters motion time

        if mycommand == "statword\r\n":
            self.buf.append(self.statword)
            cmdOk = True

        if mycommand == "status\r\n":
            self.buf.append(self.bia_mode)
            cmdOk = True

        if mycommand[:10] == "set_period":
            self.g_aperiod = int(mycommand[10:])
            cmdOk = True

        if mycommand[:8] == "set_duty":
            self.g_aduty = int(mycommand[8:])
            cmdOk = True

        if mycommand == "get_period\r\n":
            self.buf.append(self.g_aperiod)
            cmdOk = True

        if mycommand == "get_duty\r\n":
            self.buf.append(self.g_aduty)
            cmdOk = True
        if mycommand == "get_param\r\n":
            self.buf.append("%i,%i,%i" % (self.pulse_on, self.g_aperiod, self.g_aduty))
            cmdOk = True

        if mycommand == "pulse_on\r\n":
            self.pulse_on = 1
            self.cmdnok = 0

        if mycommand == "pulse_off\r\n":
            self.pulse_on = 0
            self.cmdnok = 0

        if cmdOk:
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
