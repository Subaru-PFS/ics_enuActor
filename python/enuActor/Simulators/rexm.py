#!/usr/bin/env python
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
    DISTANCE_MAX = 420

    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)

        self.currSpeed = 0.
        self.maxSpeed = 0
        self.realPos = 50.
        self.currPos = 0.
        self.stepIdx = 0
        self.direction = 1
        self.pulseDivisor = 7
        self.safeStop = False

        self.buf = []

    def connect(self, server):
        (ip, port) = server
        time.sleep(0.2)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    @property
    def speedStep(self):
        return self.currSpeed / (2 ** self.pulseDivisor * (65536 / 16e6))

    def sendall(self, cmdBytes, flags=None):
        time.sleep(0.01)
        packet = recvFake(*unpack('>BBBBIB', cmdBytes))
        if packet.cmd == TMCM.TMCL_MST:
            self.safeStop = True
            self.currSpeed = 0
            self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=0))

        elif packet.cmd == TMCM.TMCL_SAP:
            if packet.ctype == 1:
                self.currPos = packet.data
            elif packet.ctype == 4:
                self.maxSpeed = packet.data
            elif packet.ctype == 140:
                self.stepIdx = packet.data
            elif packet.ctype == 154:
                self.pulseDivisor = packet.data

            self.buf.append(sendFake(cmd=TMCM.TMCL_SAP, data=packet.data))

        elif packet.cmd == TMCM.TMCL_GAP:
            if packet.ctype == 1:
                ret = self.currPos
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret, fmtRet='>BBBBiB'))

            elif packet.ctype == 3:
                ret = self.currSpeed * self.direction
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret, fmtRet='>BBBBiB'))

            elif packet.ctype == 10:
                ret = 1 if self.realPos >= self.mm2counts(self.DISTANCE_MAX - 10) else 0
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret))

            elif packet.ctype == 11:
                ret = 1 if self.realPos <= 0 else 0
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret))

            elif packet.ctype == 140:
                ret = self.stepIdx
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret))

            elif packet.ctype == 154:
                ret = self.pulseDivisor
                self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=ret))

        elif packet.cmd == TMCM.TMCL_MVP:
            self.MVP(distance=np.int32(packet.data))
            self.buf.append(sendFake(cmd=TMCM.TMCL_MVP, data=packet.data))

        else:
            self.buf.append(sendFake(cmd=TMCM.TMCL_GAP, data=0, status=2))

    def fakeMove(self, distance, tempo=0.01):
        if self.safeStop:
            self.safeStop = False

        self.direction = -1 if distance < 0 else 1
        dmin = 0
        dmax = self.mm2counts(self.DISTANCE_MAX - 10)

        goal = self.realPos + distance
        self.currSpeed = self.maxSpeed
        step = tempo * self.direction * self.speedStep

        if self.direction == -1:
            while self.realPos > goal:
                if self.safeStop:
                    break

                if self.realPos + step <= dmin:
                    self.currSpeed = 0
                    step = dmin - self.realPos
                    self.moveRelative(tempo, step)
                    break

                self.moveRelative(tempo, step)

        elif self.direction == 1:
            while self.realPos < goal:
                if self.safeStop:
                    break
                if self.realPos + step >= dmax:
                    self.currSpeed = 0
                    step = dmax - self.realPos
                    self.moveRelative(tempo, step)
                    break

                self.moveRelative(tempo, step)

    def MVP(self, distance):
        # set moving speed
        f1 = Thread(target=self.fakeMove, args=(distance,))
        f1.start()

        return 0

    def mm2counts(self, val):

        screwStep = 5.0  # mm
        step = 1 << self.stepIdx  # nombre de micro pas par pas moteur
        nbStepByRev = 200.0  # nombre de pas moteur dans un tour moteur
        reducer = 12.0  # nombre de tours moteur pour 1 tour en sortie du reducteur

        return np.float64(val / screwStep * reducer * nbStepByRev * step)

    def moveRelative(self, tempo, step):
        time.sleep(tempo)

        self.realPos += step
        self.currPos += step

    def recv(self, buffersize, flags=None):
        time.sleep(0.01)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return ret.cmdBytes

    def close(self):
        pass
