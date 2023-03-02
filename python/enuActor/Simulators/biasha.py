# !/usr/bin/env python

import socket
import time

import numpy as np

STATUS_BCRC = 0x52  # Both shutters closed no error
STATUS_BCRO = 0x54  # Blue CLOSED Red OPEN no error
STATUS_BORC = 0x62  # Blue OPEN Red CLOSED no error
STATUS_BORO = 0x64  # Blue OPEN Red OPEN no error

ERROR_STR = {-1: "unrecognized command:",
             -2: "shutter switch timeout.",
             -3: "transition not allowed.",
             -4: "value out of range",
             -5: "exposure already declared.",
             -6: "exposure not yet completed.",
             -7: "no exposure declared.",
             }

STATE_CMD = ["bia_on", "bia_off",
             "shut_open", "shut_close",
             "blue_open", "blue_close",
             "red_open", "red_close",
             "init"]


class BiashaSim(socket.socket):
    statword = {0: STATUS_BCRC, 10: STATUS_BCRC, 20: STATUS_BORO, 30: STATUS_BORC, 40: STATUS_BCRO}
    version = "0.1.5"

    def __init__(self):
        """Fake biasha tcp server."""
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.noStrobeDuty = 100
        self.noStrobePeriod = 1000

        self.g_aduty = self.noStrobeDuty
        self.g_aperiod = self.noStrobePeriod
        self.g_sduty = self.g_aduty
        self.g_speriod = self.g_aperiod

        self.g_apower = 0
        self.bia_mode = 0
        self.statword = BiashaSim.statword[self.bia_mode]

        self.buf = []

    def connect(self, server):
        """Fake the connection to tcp server."""
        (ip, port) = server
        time.sleep(0.001)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def setBiaParameters(self, duty, period):
        self.g_aduty = duty
        self.g_aperiod = period

    def sendall(self, cmdStr, flags=None):
        """Send fake packets, append fake response to buffer."""
        time.sleep(0.005)

        # not recognized command
        errorCode = -1

        cmdStr = cmdStr.decode()
        cmdStripped, __ = cmdStr.split('\r\n')

        bia_mode = self.bia_mode
        self.statword = BiashaSim.statword[bia_mode]

        if bia_mode == 0:  # IDLE STATE
            if cmdStripped == 'bia_on':
                bia_mode = 10
                errorCode = 0
            elif cmdStripped == 'shut_open':
                bia_mode = 20
                errorCode = 0
            elif cmdStripped == 'blue_open':
                bia_mode = 30
                errorCode = 0
            elif cmdStripped == 'red_open':
                bia_mode = 40
                errorCode = 0
            elif cmdStripped == 'init':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped in STATE_CMD:
                # transition not allowed.
                errorCode = -3

        elif bia_mode == 10:  # BIA IS ON
            if cmdStripped == 'bia_off':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped == 'init':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped in STATE_CMD:
                # transition not allowed.
                errorCode = -3

        elif bia_mode == 20:  # SHUTTERS OPEN
            if cmdStripped == 'shut_close':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped == 'blue_close':
                bia_mode = 40
                errorCode = 0
            elif cmdStripped == 'red_close':
                bia_mode = 30
                errorCode = 0
            elif cmdStripped == 'init':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped in STATE_CMD:
                # transition not allowed.
                errorCode = -3

        elif bia_mode == 30:  # BLUE SHUTTER OPEN
            if cmdStripped == 'shut_open':
                bia_mode = 20
                errorCode = 0
            elif cmdStripped == 'shut_close':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped == 'red_open':
                bia_mode = 20
                errorCode = 0
            elif cmdStripped == 'blue_close':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped == 'init':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped in STATE_CMD:
                # transition not allowed.
                errorCode = -3

        elif bia_mode == 40:  # RED SHUTTER OPEN
            if cmdStripped == 'shut_open':
                bia_mode = 20
                errorCode = 0
            elif cmdStripped == 'shut_close':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped == 'blue_open':
                bia_mode = 20
                errorCode = 0
            elif cmdStripped == 'red_close':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped == 'init':
                bia_mode = 0
                errorCode = 0
            elif cmdStripped in STATE_CMD:
                # transition not allowed.
                errorCode = -3

        if bia_mode != self.bia_mode:
            self.waitForCompletion(BiashaSim.statword[bia_mode])
            self.bia_mode = bia_mode

        if cmdStripped == 'statword':
            self.buf.append(self.statword)
            errorCode = 0

        elif cmdStripped == 'status':
            self.buf.append(self.bia_mode)
            errorCode = 0

        elif cmdStr[:10] == 'set_period':
            g_aperiod = int(cmdStr[10:])
            if 0 < g_aperiod <= 65535:
                self.setBiaParameters(self.g_sduty, g_aperiod)
                self.g_speriod = g_aperiod
                errorCode = 0
            else:
                errorCode = -4

        elif cmdStr[:8] == 'set_duty':
            g_aduty = int(cmdStr[8:])
            if 0 < g_aduty <= 100:
                self.setBiaParameters(g_aduty, self.g_speriod)
                self.g_sduty = g_aduty
                errorCode = 0
            else:
                errorCode = - 4

        elif cmdStr[:9] == 'set_power':
            g_apower = int(cmdStr[9:])
            if 0 < g_apower <= 255:
                self.g_apower = g_apower
                errorCode = 0
            else:
                errorCode = -4

        elif cmdStripped == 'get_period':
            self.buf.append(self.g_aperiod)
            errorCode = 0

        elif cmdStripped == 'get_duty':
            self.buf.append(self.g_aduty)
            errorCode = 0

        elif cmdStripped == 'get_power':
            self.buf.append(self.g_apower)
            errorCode = 0

        elif cmdStripped == 'get_param':
            self.buf.append('%d,%d,%d' % (self.g_aduty, self.g_aperiod, self.g_apower))
            errorCode = 0

        elif cmdStripped == 'get_version':
            self.buf.append(BiashaSim.version)
            errorCode = 0

        elif cmdStripped == 'pulse_on':
            self.setBiaParameters(self.g_sduty, self.g_speriod)
            errorCode = 0

        elif cmdStripped == 'pulse_off':
            self.g_aduty = self.noStrobeDuty
            self.g_aperiod = self.noStrobePeriod
            errorCode = 0

        elif cmdStripped == 'read_phr':
            if self.bia_mode == 10:
                values = np.random.normal(845, 5), np.random.normal(845, 5)
            else:
                values = np.random.normal(10, 2), np.random.normal(10, 2)

            self.buf.append('%d,%d' % (values[0], values[1]))
            errorCode = 0

        else:
            pass

        if not errorCode:
            self.buf.append('ok\r\n')
        else:
            self.buf.append(f'{ERROR_STR[errorCode]}')
            self.buf.append('nok\r\n')

    def waitForCompletion(self, dst):
        # redTime = np.random.normal(0.397, 0.0006)
        # blueTime = np.random.normal(0.317, 0.0006)
        # closeOffset = 0.005
        redTime = 0.4
        blueTime = 0.3
        closeOffset = 0

        motionStart = nowMs = time.time()
        now = BiashaSim.statword[self.bia_mode]

        blueMotion = bin(now)[-6:][0] != bin(dst)[-6:][0]
        redMotion = bin(now)[-6:][3] != bin(dst)[-6:][3]

        if redMotion:
            time.sleep(redTime)

        elif blueMotion:
            time.sleep(blueTime)

    def recv(self, buffersize, flags=None):
        """Return and remove fake response from buffer."""
        time.sleep(0.005)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
