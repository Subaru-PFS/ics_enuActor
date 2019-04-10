__author__ = 'alefur'

import logging

import enuActor.utils.bufferedSocket as bufferedSocket
import numpy as np
from enuActor.Simulators.temps import TempsSim
from enuActor.utils.fsmThread import FSMThread


class temps(FSMThread, bufferedSocket.EthComm):
    channels = {1: '101:110',
                2: '201:210'}
    tempMin, tempMax = -20, 60
    resMin, resMax = 90, 120

    @staticmethod
    def polyval(resistances, calib):
        """|  convert resistance to temperature using lab calibration

        :param resistances: resistance value
        :param calib: polynomial coeffient
        :type resistances: np.array
        :type calib: np.array
        :return: temperature
        :rtype: np.array
        """
        return np.array([np.polyval(calib[i], resistances[i]) for i in range(len(resistances))])

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        FSMThread.__init__(self, actor, name, doInit=True)

        self.sim = TempsSim()

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    def getProbeCoeff(self, probe):
        return np.array([float(c) for c in self.actor.config.get('temps', str(probe)).split(',')])

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice().

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('temps', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('temps', 'host'),
                                        port=int(self.actor.config.get('temps', 'port')),
                                        EOL='\n')

        self.doCalib = self.actor.config.getboolean('temps', 'doCalib')
        self.calib = {1: np.array([self.getProbeCoeff(probe) for probe in range(101, 111)]),
                      2: np.array([self.getProbeCoeff(probe) for probe in range(201, 211)])}

    def _openComm(self, cmd):
        """| Open socket with keysight controller or simulate it.
        | Called by FSMDev.loadDevice()

        :param cmd: on going command
        :raise: socket.error if the communication has failed with the controller
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\n')
        s = self.connectSock()

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.getInfo(cmd=cmd)

    def _init(self, cmd):
        """| Initialise temperature controller, called by self.initDevice().
        - get error

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """
        self.getError(cmd=cmd)

    def getStatus(self, cmd):
        """| Get status and generate temps keywords.

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        self.getTemps(cmd=cmd)

    def getTemps(self, cmd):
        """| generate temps keyword

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        self.genKeys(cmd, self.calibTemps, keys='temps1', slot=1)
        self.genKeys(cmd, self.calibTemps, keys='temps2', slot=2)

    def getResistance(self, cmd):
        """|  generate resistance keywords

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        self.genKeys(cmd, self._fetchResistance, keys='res1', slot=1)
        self.genKeys(cmd, self._fetchResistance, keys='res2', slot=2)

    def getInfo(self, cmd):
        """|  fetch controller info.

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        cmd.inform('tempsSlot1=%s' % self._fetchSlotInfo(cmd, slot=1))
        cmd.inform('tempsSlot2=%s' % self._fetchSlotInfo(cmd, slot=2))
        cmd.inform('tempsVersion=%s' % self.sendOneCommand('SYST:VERS?', cmd=cmd))

    def getError(self, cmd):
        """|  fetch controller error

        :param cmd: on going command
        :raise: RuntimeError if the controller returns an error
        """
        errorCode, errorMsg = self._fetchError(cmd)
        cmd.inform('tempsStatus=%d,%s' % (errorCode, errorMsg))

    def calibTemps(self, cmd, slot):
        """|  fetch resistance and use lab calibration if doCalib else fetch temps

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: RuntimeError if the controller returns an error
        """
        if not self.doCalib:
            return self._fetchTemps(slot=slot, cmd=cmd)

        resistances = self._fetchResistance(slot=slot, cmd=cmd)
        return temps.polyval(resistances, calib=self.calib[slot])

    def genKeys(self, cmd, retrieveData, keys, **kwargs):
        """|  generate keys using retrieveData func

        :param cmd: on going command
        :raise: RuntimeError if the controller returns an error
        """
        values = np.ones(10) * np.nan
        try:
            values = retrieveData(cmd, **kwargs)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        cmd.inform('%s=%s' % (keys, ','.join(['%.3f' % float(val) for val in values])))

    def _fetchTemps(self, cmd, slot):
        """|  fetch temperature values for a specified slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:TEMP? FRTD, (@%s)' % channels, cmd=cmd)
        return np.array([float(t) if temps.tempMin < float(t) < temps.tempMax else np.nan for t in ret.split(',')])

    def _fetchResistance(self, cmd, slot):
        """|  fetch resistance values for a specified slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:FRES? 100,0.0003,(@%s)' % channels, cmd=cmd)
        return np.array([float(res) if temps.resMin < float(res) < temps.resMax else np.nan for res in ret.split(',')])

    def _fetchSlotInfo(self, cmd, slot):
        """|  fetch slot info

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: RuntimeError if the controller returns an error
        """
        ret = self.sendOneCommand('SYST:CTYP? %d00' % slot, cmd=cmd)
        company, modelNumber, serialNumber, firmware = ret.split(',')
        return '"%s", "%s", %s, %s' % (company, modelNumber, serialNumber, firmware)

    def _fetchError(self, cmd):
        """|  fetch controller error

        :param cmd: on going command
        :raise: RuntimeError if the controller returns an error
        """
        errorCode, errorMsg = self.sendOneCommand('SYST:ERR?', cmd=cmd).split(',')

        if int(errorCode) != 0:
            cmd.warn('error=%d,%s' % (int(errorCode), errorMsg))
            raise RuntimeError(errorMsg)

        return int(errorCode), errorMsg

    def createSock(self):
        """| create socket or fake it returning a simulator.

        :raise: Exception if a command fail
        """
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
