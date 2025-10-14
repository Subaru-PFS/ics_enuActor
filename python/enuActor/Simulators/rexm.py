#!/usr/bin/env python
import copy
import socket
import time
from struct import pack, unpack
from threading import Thread

import numpy as np
from enuActor.drivers.rexm_drivers import TMCM


class recvFake(object):
    def __init__(self, moduleAddress, cmd, ctype, motorAddress, data, checksum):
        object.__init__(self)
        self.moduleAddress = moduleAddress
        self.cmd = cmd
        self.ctype = ctype
        self.motorAddress = motorAddress
        self.data = data
        self.checksum = checksum


class sendFake(object):
    def __init__(self, cmd, data, fmtRet='>BBBBIB', status=100):
        data = np.int32(data) if data<0 else data
        data = np.uint32(data) if fmtRet == '>BBBBIB' else np.int32(data)
        self.replyAddress = 2
        self.moduleAddress = 1
        self.status = status
        self.cmd = cmd
        self.data = data
        self.fmtRet = fmtRet

    @property
    def checksum(self):
        data = pack(self.fmtRet[:-1], self.replyAddress, self.moduleAddress, self.status, self.cmd, self.data)
        checksum = sum(data)
        checksum %= 256
        return checksum

    @property
    def cmdBytes(self):
        return pack(self.fmtRet, self.replyAddress, self.moduleAddress, self.status, self.cmd, self.data, self.checksum)


class RexmSim(socket.socket):
    DISTANCE_MAX = 414.39

    def __init__(self):
        """Fake rexm through moxa ethernet server."""
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)

        self.currSpeed = 0.
        self.realPos = 100
        self.direction = 1
        self.motorConfig = copy.deepcopy(TMCM.defaultConfig)
        self.motorConfig[1] = 0

        self.emergencyFlag = 0
        self.emergencyButton = 0
        self.safeStop = False

        self.buf = []

    def connect(self, server):
        """Fake the connection to tcp server."""
        (ip, port) = server
        time.sleep(0.2)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    @property
    def speedStep(self):
        return self.currSpeed / (2 ** self.pulseDivisor * (65536 / 16e6))

    @property
    def stepIdx(self):
        return self.motorConfig[140]

    @property
    def pulseDivisor(self):
        return self.motorConfig[154]

    @property
    def currPos(self):
        return self.motorConfig[1]

    @property
    def maxSpeed(self):
        return self.motorConfig[4]

    def sendall(self, cmdBytes, flags=None):
        """Send fake packets, append fake response to buffer."""
        time.sleep(0.01)
        packet = recvFake(*unpack('>BBBBIB', cmdBytes))

        if packet.cmd == TMCM.TMCL_MST:
            self.safeStop = True
            self.currSpeed = 0
            self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=0))

        elif packet.cmd == TMCM.TMCL_SAP:
            self.motorConfig[packet.ctype] = packet.data
            self.buf.append(sendFake(cmd=TMCM.TMCL_SAP, data=packet.data))

        elif packet.cmd == TMCM.TMCL_GAP:
            dmin = 0
            dmax = TMCM.mm2ustep(stepIdx=self.stepIdx, valueMm=self.DISTANCE_MAX)

            if packet.ctype == 3:
                ret = self.currSpeed * self.direction
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret, fmtRet='>BBBBiB'))

            elif packet.ctype == 10:
                ret = 1 if self.realPos >= dmax else 0
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret))

            elif packet.ctype == 11:
                ret = 1 if self.realPos <= dmin else 0
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret))
            else:
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=self.motorConfig[packet.ctype]))

        elif packet.cmd == TMCM.TMCL_MVP:
            self.MVP(distance=np.int32(np.uint32(packet.data)))
            self.buf.append(sendFake(cmd=TMCM.TMCL_MVP, data=packet.data))

        elif packet.cmd == TMCM.TMCL_GGP:
            if packet.ctype == 11:
                self.buf.append(sendFake(cmd=TMCM.TMCL_GGP, data=int(self.emergencyFlag)))

        elif packet.cmd == TMCM.TMCL_SGP:
            if packet.ctype == 11:
                self.emergencyFlag = packet.data

            self.buf.append(sendFake(cmd=TMCM.TMCL_SGP, data=packet.data))

        elif packet.cmd == TMCM.TMCL_GIO:
            self.buf.append(sendFake(cmd=TMCM.TMCL_GIO, data=int(not self.emergencyButton)))

        else:
            self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=0, status=2))

    def fakeMove(self, distance, tempo=0.01):
        """Fake a motion."""
        if self.safeStop:
            self.safeStop = False

        self.direction = -1 if distance < 0 else 1
        dmin = 0
        dmax = TMCM.mm2ustep(stepIdx=self.stepIdx, valueMm=self.DISTANCE_MAX)

        goal = self.realPos + distance
        self.currSpeed = self.maxSpeed
        step = tempo * self.direction * self.speedStep

        if self.direction == -1:
            while self.realPos > goal:
                if self.safeStop:
                    break

                if self.realPos + step <= dmin:
                    step = dmin - self.realPos
                    self.moveRelative(tempo, step)
                    break

                self.moveRelative(tempo, step)

            self.currSpeed = 0

        elif self.direction == 1:
            while self.realPos < goal:
                if self.safeStop:
                    break
                if self.realPos + step >= dmax:
                    step = dmax - self.realPos
                    self.moveRelative(tempo, step)
                    break

                self.moveRelative(tempo, step)
            self.currSpeed = 0

    def MVP(self, distance):
        # set moving speed
        f1 = Thread(target=self.fakeMove, args=(distance,))
        f1.start()

        return 0

    def test(self):
        self.safeStop = True
        self.currSpeed = 0
        self.emergencyFlag = 1
        self.emergencyButton = 1

    def test2(self):
        self.emergencyButton = 0

    def moveRelative(self, tempo, step):
        time.sleep(tempo)

        self.realPos += step
        self.motorConfig[1] += step

    def recv(self, buffersize, flags=None):
        """Return and remove fake response from buffer."""
        time.sleep(0.01)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return ret.cmdBytes

    def close(self):
        pass
