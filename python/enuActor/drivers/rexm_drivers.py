# XPS Python class
#
# for TMCM-1180 firmware v4.45.

from struct import pack, unpack

import numpy as np


class sendPacket(object):
    def __init__(self, moduleAddress=0, cmd=0, ctype=0, motorAddress=0, data=0):
        object.__init__(self)
        self.moduleAddress = np.uint8(moduleAddress)
        self.cmd = np.uint8(cmd)
        self.ctype = np.uint8(ctype)
        self.motorAddress = np.uint8(motorAddress)
        self.data = np.uint32(data)

    @property
    def checksum(self):
        data = pack('>BBBBI', self.moduleAddress, self.cmd, self.ctype, self.motorAddress, self.data)
        checksum = sum(data)
        checksum %= 256
        return checksum

    @property
    def cmdBytes(self):
        return pack('>BBBBIB', self.moduleAddress, self.cmd, self.ctype, self.motorAddress, self.data, self.checksum)


class recvPacket(object):
    def __init__(self, bytes, fmtRet):
        self.getRet(*(unpack(fmtRet, bytes)))

    def getRet(self, replyAddress, moduleAddress, status, cmd, data, checksum):
        self.replyAddress = replyAddress
        self.moduleAddress = moduleAddress
        self.status = status
        self.cmd = cmd
        self.data = data
        self.checksum = checksum


class TMCM(object):
    controllerStatus = {100: "Successfully executed, no error",
                        101: "Command loaded into TMCL program EEPROM",
                        0: "Unkown Error",
                        1: "Wrong checksum",
                        2: "Invalid command",
                        3: "Wrong type",
                        4: "Invalid value",
                        5: "Configuration EEPROM locked",
                        6: "Command not available"}

    SPEED_MAX = 10.0 # mm/s
    DISTANCE_MAX = 420.0  # 410mm + 10mm margin

    g_speed = 3.2 # mm/s

    MODULE_ADDRESS = 1
    MOTOR_ADDRESS = 0

    DIRECTION_A = 0
    DIRECTION_B = 1

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

    @staticmethod
    def stop():
        """stop function
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_MST,
                            ctype=0,
                            motorAddress=TMCM.MOTOR_ADDRESS)
        return packet.cmdBytes

    @staticmethod
    def MVP(direction, counts):
        # mvp function
        data = -counts if direction == TMCM.DIRECTION_A else counts

        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_MVP,
                            ctype=TMCM.MVP_REL,
                            motorAddress=TMCM.MOTOR_ADDRESS,
                            data=data)
        return packet.cmdBytes

    @staticmethod
    def sap(paramId, data):
        """set axis function
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_SAP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS,
                            data=data)
        return packet.cmdBytes

    @staticmethod
    def gap(paramId):
        """get axis parameter function
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_GAP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS)
        return packet.cmdBytes

    @staticmethod
    def sgp(paramId, data):
        """set global parameter function
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_SGP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS,
                            data=data)
        return packet.cmdBytes

    @staticmethod
    def ggp(paramId):
        """get global parameter function
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_GGP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS)
        return packet.cmdBytes

    @staticmethod
    def mm2counts(stepIdx, valueMm):
        """| Convert mm to counts

        :param valueMm: value in mm
        :type valueMm:float
        :rtype:float
        """
        screwStep = 5.0  # mm #
        step = 1 << stepIdx  # ustep per motorstep
        nbStepByRev = 200.0  # motorstep per motor revolution
        reducer = 12.0  # motor revolution for 1 reducer revolution

        return np.float64(valueMm / screwStep * reducer * nbStepByRev * step)

    @staticmethod
    def counts2mm(stepIdx, counts):
        """| Convert counts to mm

        :param counts: count value
        :type counts:float
        :rtype:float
        """
        return np.float64(counts / TMCM.mm2counts(stepIdx, 1.0))
