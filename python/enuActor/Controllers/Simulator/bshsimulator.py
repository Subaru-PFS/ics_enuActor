#!/usr/bin/env python

import time


class BshSimulator(object):
    statword = {0: "01001000", 1: "10010000", 2: "01001000"}

    def __init__(self):
        super(BshSimulator, self).__init__()
        self.g_aduty = 0
        self.g_aperiod = 100
        self.bia_mode = 0
        self.safe_on = 0
        self.statword = BshSimulator.statword[self.bia_mode]

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

    def send(self, mycommand):
        time.sleep(0.1)
        self.cmdnok = 2
        self.statword = BshSimulator.statword[self.bia_mode]
        if self.bia_mode == 0:  # IDLE STATE
            if mycommand == "bia_on\r\n":
                if self.check_interlock(mycommand) == 1:
                    self.bia_mode = 2
                    self.cmdnok = 0
                else:
                    self.buf.append("intlk")
                    self.cmdnok = 1

            elif mycommand == "shut_open\r\n":
                if self.check_interlock(mycommand) == 1:
                    self.bia_mode = 1
                    self.cmdnok = 0
                else:
                    self.buf.append("intlk")
                    cmdnok = 1
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
            print "self.statword = ", self.statword
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

        if mycommand == "safe_on\r\n":
            self.safe_on = 1
            self.cmdnok = 1

        if mycommand == "safe_off\r\n":
            self.safe_on = 0
            self.cmdnok = 1

        if self.cmdnok < 2:
            self.buf.append("ok\r\n")

        else:
            self.buf.append("nok\r\n")

    def check_interlock(self, mycommand):
        if self.safe_on == 1:
            if mycommand == "bia_on\r\n" and self.statword != "01001000":
                return 0
                # if (mycommand =="shut_close\r\n" && statword !="01001000") {return 0;}     GET STATUS FROM PHOTODIODE
        return 1

    def recv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret)

    def close(self):
        pass
