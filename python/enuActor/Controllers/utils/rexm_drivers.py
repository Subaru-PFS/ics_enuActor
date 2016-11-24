# XPS Python class

#

# for TMCM-1180 firmware v4.45.

#


# XPS Python class

#

# for TMCM-1180 firmware v4.45.

#
import time
from struct import pack, unpack

import numpy as np
import serial


class sendPacket(object):
    def __init__(self, moduleAddress=0, cmd=0, ctype=0, motorAddress=0, data=0):
        object.__init__(self)
        self.moduleAddress = np.uint8(moduleAddress)
        self.cmd = np.uint8(cmd)
        self.ctype = np.uint8(ctype)
        self.motorAddress = np.uint8(motorAddress)
        self.data = np.uint32(data)
        self.checksum()
        self.cmdStr = pack('>BBBBIB', self.moduleAddress, self.cmd, self.ctype, self.motorAddress, self.data,
                           self.checksum)

    def checksum(self):
        data = pack('>BBBBI', self.moduleAddress, self.cmd, self.ctype, self.motorAddress, self.data)
        self.checksum = sum(map(ord, data))
        self.checksum = self.checksum % 256

    def getCmd(self):
        return self.cmdStr


class recvPacket():
    def __init__(self, bytes, fmtRet):
        self.getRet(*(unpack(fmtRet, bytes)))

    def getRet(self, replyAddress, moduleAddress, status, cmd, data, checksum):
        self.replyAddress = replyAddress
        self.moduleAddress = moduleAddress
        self.status = status
        self.cmd = cmd
        self.data = data
        self.checksum = checksum


class TMCM():
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

    def __init__(self, port):
        self.ser = None
        self.port = port
        self.name = "rexm"

    def openSerial(self, cmd):
        """ Connect serial if self.ser is None

        :param cmd : current command,
        :return: ser in operation
                 bsh simulator in simulation
        """
        if self.ser is None:
            try:
                s = serial.Serial(port=self.port,
                                  baudrate=9600,
                                  bytesize=serial.EIGHTBITS,
                                  parity=serial.PARITY_NONE,
                                  stopbits=serial.STOPBITS_ONE,
                                  timeout=2.)
            except:
                cmd.warn("text='failed to create serial for %s'" % self.name)
                raise
            try:
                if not s.isOpen():
                    s.open()
                if s.readable() and s.writable():
                    self.ser = s
                else:
                    raise Exception('serial port is not readable')
            except:
                cmd.warn("text='failed to connect to %s'" % self.name)
                raise

        return self.ser

    def closeSerial(self, cmd):
        """ close serial

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """
        if self.ser is not None:
            try:
                self.ser.close()
            except:
                cmd.warn("text='failed to close serial for %s'" % self.name)
                raise
        self.ser = None

    def sendOneCommand(self, cmd, cmdStr, doClose=False, fmtRet='>BBBBIB'):
        """ Send one command and return one response.

        Args
        ----
        cmdStr : str
           The command to send.
        doClose : bool
           If True (the default), the device serial is closed before returning.

        Returns
        -------
        str : the single response string, with EOLs stripped.

        Raises
        ------
        IOError : from any communication errors.
        """

        s = self.openSerial(cmd)
        try:
            ret = s.write(cmdStr)
            if ret != 9:
                raise Exception('cmdStr is badly formatted')
        except:
            cmd.warn("text='failed to send cmd to %s'" % self.name)
            raise

        reply = self.getOneResponse(cmd, ser=s, fmtRet=fmtRet)
        if doClose:
            self.closeSerial(cmd)

        return reply

    def getOneResponse(self, cmd, ser=None, fmtRet='>BBBBIB'):
        time.sleep(0.05)
        try:
            if ser is None:
                ser = self.openSerial(cmd)

            ret = recvPacket(ser.read(9), fmtRet=fmtRet)
            if ret.status != 100:
                raise Exception(TMCM.controllerStatus[ret.status])
        except:
            cmd.warn("text='failed to get answer from %s'" % self.name)
            raise

        return ret.data

    def stop(self, cmd):
        """fonction stop  controleur
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_MST,
                            ctype=0,
                            motorAddress=TMCM.MOTOR_ADDRESS)

        ret = self.sendOneCommand(cmd, packet.getCmd(), doClose=False)

    def mm2counts(self, cmd, val):

        stepIdx = self.gap(cmd, 140)
        screwStep = 5.0  # mm
        step = 1 << stepIdx  # nombre de micro pas par pas moteur
        nbStepByRev = 200.0  # nombre de pas moteur dans un tour moteur
        reducer = 12.0  # nombre de tours moteur pour 1 tour en sortie du reducteur

        return np.float64(val / screwStep * reducer * nbStepByRev * step)

    def counts2mm(self, cmd, counts):

        return np.float64(counts / self.mm2counts(cmd, 1.0))

    def MVP(self, cmd, direction, distance, speed, type="relative", doClose=False):
        # set moving speed
        pulseDivisor = np.uint32(self.gap(cmd, 154))
        speed = self.minmax(speed, 0, TMCM.SPEED_MAX)
        freq = self.mm2counts(cmd, speed) * ((2 ** pulseDivisor) * 2048 * 32) / 16.0e6
        self.sap(cmd, 4, freq)

        cMax = np.int32(1 << 23)
        distance = self.minmax(distance, 0, TMCM.DISTANCE_MAX)

        counts = np.int32(self.mm2counts(cmd, distance))
        counts = self.minmax(counts, -cMax, cMax)

        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_MVP,
                            ctype=TMCM.MVP_ABS if type == "absolute" else TMCM.MVP_REL,
                            motorAddress=TMCM.MOTOR_ADDRESS,
                            data=- counts if direction == TMCM.DIRECTION_A else counts)

        ret = self.sendOneCommand(cmd, packet.getCmd(), doClose=doClose)

    def sap(self, cmd, paramId, data, doClose=False):
        """fonction set axis parameter du manuel du controleur
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_SAP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS,
                            data=data)

        return self.sendOneCommand(cmd, packet.getCmd(), doClose=doClose)

    def gap(self, cmd, paramId, doClose=False, fmtRet='>BBBBIB'):
        """fonction get axis parameter du manuel du controleur
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_GAP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS)

        return self.sendOneCommand(cmd, packet.getCmd(), doClose=doClose, fmtRet=fmtRet)

    def setOutput(self, cmd, paramId, boolean, doClose=False):
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_SIO,
                            ctype=self.minmax(paramId, 0, 1),
                            motorAddress=2,
                            data=boolean)

        return self.sendOneCommand(cmd, packet.getCmd(), doClose=doClose)

    def sgp(self, cmd, paramId, data, doClose=False):
        """fonction set global parameter du manuel du controleur
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_SGP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS,
                            data=data)

        return self.sendOneCommand(cmd, packet.getCmd(), doClose=doClose)

    def ggp(self, cmd, paramId, doClose=False):
        """fonction get global parameter du manuel du controleur
        """
        packet = sendPacket(moduleAddress=TMCM.MODULE_ADDRESS,
                            cmd=TMCM.TMCL_GGP,
                            ctype=paramId,
                            motorAddress=TMCM.MOTOR_ADDRESS)

        return self.sendOneCommand(cmd, packet.getCmd(), doClose=doClose)

    def minmax(self, x, a, b):
        if x < a:
            return a
        elif x > b:
            return b
        else:
            return x
