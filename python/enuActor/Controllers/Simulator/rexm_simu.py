#!/usr/bin/env python
import time
from threading import Thread

import numpy as np


class RexmSimulator(object):
    controllerStatus = {100: "Successfully executed, no error",
                        101: "Command loaded into TMCL program EEPROM",
                        1: "Wrong checksum",
                        2: "Invalid command",
                        3: "Wrong type",
                        4: "Invalid value",
                        5: "Configuration EEPROM locked",
                        6: "Command not available"}
    MODULE_ADDRESS = 1
    MOTOR_ADDRESS = 0

    DIRECTION_A = 0
    DIRECTION_B = 1

    # unit : mm/s
    SPEED_MAX = 1000

    g_speed = 3.2;  # mm/s
    g_pauseDelay = 60.0  # secondes

    # 410mm + 10mm de marge
    DISTANCE_MAX = 420.0

    TMCL_ROR = 1
    TMCL_ROL = 2
    TMCL_MST = 3
    TMCL_MVP = 4
    TMCL_SAP = 5
    TMCL_GAP = 6
    TMCL_STAP = 7
    TMCL_RSAP = 8
    TMCL_SGP = 9
    TMCL_GGP = 10
    TMCL_STGP = 11
    TMCL_RSGP = 12
    TMCL_RFS = 13
    TMCL_SIO = 14
    TMCL_GIO = 15
    TMCL_SCO = 30
    TMCL_GCO = 31
    TMCL_CCO = 32

    TMCL_APPL_STOP = 128
    TMCL_APPL_RUN = 129
    TMCL_APPL_RESET = 131

    # Options for MVP commandds
    MVP_ABS = 0
    MVP_REL = 1
    MVP_COORD = 2

    def __init__(self, port="/dev/ttyACM0"):
        self.name = "rexm"
        self.ser = None
        self.port = port
        self.currSpeed = 0.
        self.currPos = 210.
        self.safeStop = False

    def stop(self):
        """fonction stop  controleur
        """
        time.sleep(0.2)
        self.safeStop = True

    def mm2counts(self, val):

        stepIdx = 1
        screwStep = 5.0  # mm
        step = 1 << stepIdx  # nombre de micro pas par pas moteur
        nbStepByRev = 200.0  # nombre de pas moteur dans un tour moteur
        reducer = 12.0  # nombre de tours moteur pour 1 tour en sortie du reducteur

        return np.float64(val / screwStep * reducer * nbStepByRev * step)

    def counts2mm(self, counts):

        return np.float64(counts / self.mm2counts(1.0))

    def fakeMove(self, direction, distance, speed):

        self.currSpeed = speed
        tempo = 0.1
        if self.safeStop:
            self.safeStop = False

        if direction == RexmSimulator.DIRECTION_A:
            goal = self.currPos - distance
            while (self.currPos > goal) and not self.safeStop:
                if self.currPos < 0: break
                time.sleep(tempo)
                self.currPos -= tempo * speed
        elif direction == RexmSimulator.DIRECTION_B:
            goal = self.currPos + distance
            while (self.currPos < goal) and not self.safeStop:
                if self.currPos > self.DISTANCE_MAX - 10: break
                time.sleep(tempo)
                self.currPos += tempo * speed

        self.currSpeed = 0

    def MVP(self, direction, distance, speed, type="relative", doClose=False):
        # set moving speed
        f1 = Thread(target=self.fakeMove, args=(direction, distance, speed))
        f1.start()

        return 0

    def sap(self, paramId, data, doClose=False):
        """fonction set axis parameter du manuel du controleur

        """
        if paramId == 1:
            self.currPos = data
        return 0

    def gap(self, paramId, doClose=False, fmtRet='>BBBBIB'):
        """fonction get axis parameter du manuel du controleur
        """
        if paramId == 1:
            return self.mm2counts(self.currPos)
        elif paramId == 3:
            return self.mm2counts(self.currSpeed)
        elif paramId == 11:
            ret = 1 if self.currPos <= 0 else 0
        elif paramId == 10:
            ret = 1 if self.currPos >= self.DISTANCE_MAX - 10 else 0

        return ret

    def minmax(self, x, a, b):
        if x < a:
            return a
        elif x > b:
            return b
        else:
            return x
