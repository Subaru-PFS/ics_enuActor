# !/usr/bin/env python

import socket
import time

import numpy as np


class BshSim(socket.socket):
    statword = {0: 82, 10: 82, 20: 100, 30: 98, 40: 84}

    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.g_aduty = 0
        self.g_aperiod = 100
        self.bia_mode = 0
        self.pulse_on = 0
        self.statword = BshSim.statword[self.bia_mode]

        self.buf = []

    def connect(self, server):
        (ip, port) = server
        time.sleep(0.2)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def sendall(self, cmdStr, flags=None):
        time.sleep(0.02)
        transient = 0
        redTime = np.random.normal(0.397, 0.0006)
        blueTime = np.random.normal(0.317, 0.0006)
        closeOffset = 0.005
        cmdOk = False
        cmdStr = cmdStr.decode()

        bia_mode = self.bia_mode
        self.statword = BshSim.statword[bia_mode]

        if bia_mode == 0:  # IDLE STATE
            if cmdStr == 'bia_on\r\n':
                bia_mode = 10
                cmdOk = True
            elif cmdStr == 'shut_open\r\n':
                bia_mode = 20
                transient = redTime
                cmdOk = True
            elif cmdStr == 'blue_open\r\n':
                bia_mode = 30
                transient = blueTime
                cmdOk = True
            elif cmdStr == 'red_open\r\n':
                bia_mode = 40
                transient = redTime
                cmdOk = True
            elif cmdStr == 'init\r\n':
                bia_mode = 0
                cmdOk = True

        elif bia_mode == 10:  # BIA IS ON
            if cmdStr == 'bia_off\r\n':
                bia_mode = 0
                cmdOk = True
            elif cmdStr == 'init\r\n':
                bia_mode = 0
                cmdOk = True

        elif bia_mode == 20:  # SHUTTERS OPEN
            if cmdStr == 'shut_close\r\n':
                bia_mode = 0
                transient = redTime - closeOffset
                cmdOk = True
            elif cmdStr == 'blue_close\r\n':
                bia_mode = 40
                transient = blueTime - closeOffset
                cmdOk = True
            elif cmdStr == 'red_close\r\n':
                bia_mode = 30
                transient = redTime - closeOffset
                cmdOk = True
            elif cmdStr == 'init\r\n':
                bia_mode = 0
                transient = redTime - closeOffset
                cmdOk = True

        elif bia_mode == 30:  # BLUE SHUTTER OPEN
            if cmdStr == 'shut_open\r\n':
                bia_mode = 20
                transient = redTime
                cmdOk = True
            elif cmdStr == 'shut_close\r\n':
                bia_mode = 0
                transient = blueTime - closeOffset
                cmdOk = True
            elif cmdStr == 'red_open\r\n':
                bia_mode = 20
                transient = redTime
                cmdOk = True
            elif cmdStr == 'blue_close\r\n':
                bia_mode = 0
                transient = blueTime - closeOffset
                cmdOk = True
            elif cmdStr == 'init\r\n':
                bia_mode = 0
                transient = blueTime - closeOffset
                cmdOk = True

        elif bia_mode == 40:  # RED SHUTTER OPEN
            if cmdStr == 'shut_open\r\n':
                bia_mode = 20
                transient = blueTime
                cmdOk = True
            elif cmdStr == 'shut_close\r\n':
                bia_mode = 0
                transient = redTime - closeOffset
                cmdOk = True
            elif cmdStr == 'blue_open\r\n':
                bia_mode = 20
                transient = blueTime
                cmdOk = True
            elif cmdStr == 'red_close\r\n':
                bia_mode = 0
                transient = redTime - closeOffset
                cmdOk = True
            elif cmdStr == 'init\r\n':
                bia_mode = 0
                transient = redTime - closeOffset
                cmdOk = True

        if bia_mode != self.bia_mode:
            if self.bia_mode != 10:
                time.sleep(transient)
            self.bia_mode = bia_mode

        if cmdStr == 'statword\r\n':
            self.buf.append(self.statword)
            cmdOk = True

        elif cmdStr == 'status\r\n':
            self.buf.append(self.bia_mode)
            cmdOk = True

        elif cmdStr[:10] == 'set_period':
            self.g_aperiod = int(cmdStr[10:])
            cmdOk = True

        elif cmdStr[:8] == 'set_duty':
            self.g_aduty = int(cmdStr[8:])
            cmdOk = True

        elif cmdStr == 'get_period\r\n':
            self.buf.append(self.g_aperiod)
            cmdOk = True

        elif cmdStr == 'get_duty\r\n':
            self.buf.append(self.g_aduty)
            cmdOk = True
        elif cmdStr == 'get_param\r\n':
            self.buf.append('%d,%d,%d' % (self.pulse_on, self.g_aperiod, self.g_aduty))
            cmdOk = True

        elif cmdStr == 'pulse_on\r\n':
            self.pulse_on = 1
            cmdOk = True

        elif cmdStr == 'pulse_off\r\n':
            self.pulse_on = 0
            cmdOk = True

        elif cmdStr == 'read_phr\r\n':
            if self.bia_mode == 10:
                values = np.random.normal(845, 5), np.random.normal(845, 5)
            else:
                values = np.random.normal(10, 2), np.random.normal(10, 2)

            self.buf.append('%d,%d' % (values[0], values[1]))
            cmdOk = True

        else:
            pass

        if cmdOk:
            self.buf.append('ok\r\n')

        else:
            self.buf.append('nok\r\n')

    def recv(self, buffersize, flags=None):
        time.sleep(0.02)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
