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
        self.data = np.int32(data)

    @property
    def checksum(self):
        data = pack('>BBBBi', self.moduleAddress, self.cmd, self.ctype, self.motorAddress, self.data)
        checksum = sum(data)
        checksum %= 256
        return checksum

    @property
    def cmdBytes(self):
        return pack('>BBBBiB', self.moduleAddress, self.cmd, self.ctype, self.motorAddress, self.data, self.checksum)


class recvPacket(object):
    def __init__(self, bytes, fmtRet='>BBBBiB'):
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

    SPEED_MIN = 1.0  # mm/s
    SPEED_MAX = 10.0  # mm/s

    DISTANCE_MIN = 5.0
    DISTANCE_MAX = 420.0  # 410mm + 10mm margin

    g_speed = 3.2  # mm/s

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

    defaultConfig = {4: 268,  # max. positioning speed [int]
                     5: 1759,  # max. acceleration [int]
                     6: 255,  # max. current
                     7: 0,  # standby current
                     12: 0,  # right limit switch disable
                     13: 0,  # left limit switch disable
                     130: 1,  # minimum speed [int]
                     140: 2,  # microstep resolution
                     149: 0,  # soft stop flag
                     153: 11,  # ramp divisor
                     154: 5,  # pulse divisor
                     160: 0,  # step interpolation enable
                     161: 0,  # double step enable
                     162: 2,  # chopper blank time
                     163: 0,  # chopper mode
                     164: 0,  # chopper hysteresis decrement
                     165: 2,  # chopper hysteresis end
                     166: 3,  # chopper hysteresis start
                     167: 5,  # chopper off time
                     168: 0,  # smartEnergy current minimum
                     169: 0,  # smartEnergy current down step
                     170: 0,  # smartEnergy hysteresis
                     171: 0,  # smartEnergy current up step
                     172: 0,  # smartEnergy hysteresis start
                     173: 1,  # stallGuard filter enable
                     174: 5,  # stallGuard threshold
                     175: 3,  # slope control high side
                     176: 3,  # slope control low side
                     177: 1,  # short protection disable
                     178: 0,  # short detection timer
                     181: 0,  # stop on stall [int]
                     182: 0,  # smartEnergy threshold speed [int]
                     183: 0,  # smartEnergy slow run current
                     184: 0,  # random chopper off time
                     193: 1,  # reference search mode
                     194: 500,  # reference search speed [int]
                     195: 100,  # reference switch speed [int]
                     200: 0,  # boost current
                     204: 20,  # freewheeling delay
                     210: 6400,  # encoder prescaler
                     212: 0,  # max. encoder deviation
                     214: 20,  # power down delay
                     254: 0,  # step/direction mode
                     }

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
    def sgp(paramId, data, motorAddress):
        """set global parameter function
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_SGP,
                            ctype=paramId,
                            motorAddress=motorAddress,
                            data=data)
        return packet.cmdBytes

    @staticmethod
    def ggp(paramId, motorAddress):
        """get global parameter function
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_GGP,
                            ctype=paramId,
                            motorAddress=motorAddress)
        return packet.cmdBytes

    @staticmethod
    def gio(paramId, motorAddress):
        """get input/outputfunction
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_GIO,
                            ctype=paramId,
                            motorAddress=motorAddress)
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

        return np.float64((valueMm * reducer * nbStepByRev * step) / screwStep)

    @staticmethod
    def counts2mm(stepIdx, counts):
        """| Convert counts to mm

        :param counts: count value
        :type counts:float
        :rtype:float
        """
        return np.float64(counts / TMCM.mm2counts(stepIdx, 1.0))
