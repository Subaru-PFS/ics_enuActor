__author__ = 'alefur'

import logging
from importlib import reload

import enuActor.Simulators.temps as simulator
import ics.utils.tcp.bufferedSocket as bufferedSocket
import numpy as np
import opscore.protocols.types as types
from ics.utils.fsm.fsmThread import FSMThread

reload(simulator)


class temps(FSMThread, bufferedSocket.EthComm):
    # for state machine, not need to temporize before init
    forceInit = True

    channels = {1: '101:110',
                2: '201:210'}
    tempMin, tempMax = -20, 60
    resMin, resMax = 90, 120

    @staticmethod
    def polyval(resistances, calib):
        """Convert resistance to temperature using lab calibration.

        :param resistances: resistance value
        :param calib: polynomial coeffient
        :type resistances: np.array
        :type calib: np.array
        :return: temperature
        :rtype: np.array
        """
        return np.array([np.polyval(calib[i], resistances[i]) for i in range(len(resistances))])

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
        :type name: str
        """
        FSMThread.__init__(self, actor, name)

        self.sim = simulator.TempsSim()
        self.biaOverHeat = False

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    @property
    def simulated(self):
        """Return True if self.mode=='simulation', return False if self.mode='operation'."""
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    @property
    def biaTemp(self):
        """Return current bia temperature, np.nan if Invalid."""
        bia = self.actor.models[self.actor.name].keyVarDict['temps1'].getValue(doRaise=False)[3]
        bia = np.nan if bia is None else bia
        return np.nan if isinstance(bia, types.Invalid) else bia

    def getProbeCoeff(self, probe):
        """Load probe calibration 4-tuple coefficients.

        :param probe: channel number(101).
        :type probe: str.
        :raise: Exception if config file is badly formatted.
        """
        return np.array([float(c) for c in self.actor.config.get('temps', str(probe)).split(',')])

    def _loadCfg(self, cmd, mode=None):
        """Load temps configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str.
        :raise: Exception if config file is badly formatted.
        """
        self.mode = self.actor.config.get('temps', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('temps', 'host'),
                                        port=int(self.actor.config.get('temps', 'port')),
                                        EOL='\n')

        self.biaTempLimit = float(self.actor.config.get('temps', 'biaTempLimit'))
        self.doCalib = self.actor.config.getboolean('temps', 'doCalib')
        self.calib = {1: np.array([self.getProbeCoeff(probe) for probe in range(101, 111)]),
                      2: np.array([self.getProbeCoeff(probe) for probe in range(201, 211)])}

    def _openComm(self, cmd):
        """Open socket with keysight temperature controller or simulate it.
        
        :param cmd: current command.
        :raise: socket.error if the communication has failed.
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\n')
        s = self.connectSock()

    def _closeComm(self, cmd):
        """Close socket.

        :param cmd: current command.
        """
        self.closeSock()

    def _testComm(self, cmd):
        """Test communication.

        :param cmd: current command.
        :raise: Exception if the communication has failed with the controller.
        """
        self.getInfo(cmd=cmd)

    def _init(self, cmd):
        """Initialise temperature controller, get error string.

        :param cmd: current command.
        :raise: Exception with warning message., user if warned with error.
        """
        self.getError(cmd=cmd)

    def getStatus(self, cmd):
        """Get status and generate temps keywords.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self.getTemps(cmd=cmd)

    def getTemps(self, cmd):
        """Generate temps1 and temps2 keywords.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self.genKey(cmd, self.calibTemps, key='temps1', slot=1)
        self.genKey(cmd, self.calibTemps, key='temps2', slot=2)

    def getResistance(self, cmd):
        """Generate resistance keywords.

        :param cmd: current command.
        :param slot: temperature slot.
        :type slot: int
        :raise: Exception with warning message.
        """
        self.genKey(cmd, self._fetchResistance, key='res1', slot=1)
        self.genKey(cmd, self._fetchResistance, key='res2', slot=2)

    def getInfo(self, cmd):
        """Fetch controller info.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        cmd.inform('tempsSlot1=%s' % self._fetchSlotInfo(cmd, slot=1))
        cmd.inform('tempsSlot2=%s' % self._fetchSlotInfo(cmd, slot=2))
        cmd.inform('tempsVersion=%s' % self.sendOneCommand('SYST:VERS?', cmd=cmd))

    def getError(self, cmd):
        """Fetch controller error string.

        :param cmd: current command.
        :raise: RuntimeError if the controller returns an error.
        """
        errorCode, errorMsg = self._fetchError(cmd)
        cmd.inform('tempsStatus=%d,%s' % (errorCode, errorMsg))

    def calibTemps(self, cmd, slot):
        """Fetch resistance and use lab calibration if doCalib else fetch temps.

        :param cmd: current command.
        :param slot: temperature slot number.
        :type slot: int
        :raise: Exception with warning message.
        """
        if not self.doCalib:
            return self._fetchTemps(slot=slot, cmd=cmd)

        resistances = self._fetchResistance(slot=slot, cmd=cmd)
        return temps.polyval(resistances, calib=self.calib[slot])

    def genKey(self, cmd, retrieveData, key, **kwargs):
        """Generate key using retrieveData func.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        values = np.ones(10) * np.nan
        try:
            values = retrieveData(cmd, **kwargs)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        cmd.inform('%s=%s' % (key, ','.join(['%.3f' % float(val) for val in values])))

    def _fetchTemps(self, cmd, slot):
        """Fetch temperature values for a specified slot.

        :param cmd: current command.
        :param slot: temperature slot.
        :type slot: int
        :raise: Exception with warning message.
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:TEMP? FRTD, (@%s)' % channels, cmd=cmd)
        return np.array([float(t) if temps.tempMin < float(t) < temps.tempMax else np.nan for t in ret.split(',')])

    def _fetchResistance(self, cmd, slot):
        """Fetch resistance values for a specified slot.

        :param cmd: current command.
        :param slot: temperature slot.
        :type slot: int
        :raise: Exception with warning message.
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:FRES? 100,0.0003,(@%s)' % channels, cmd=cmd)
        return np.array([float(res) if temps.resMin < float(res) < temps.resMax else np.nan for res in ret.split(',')])

    def _fetchSlotInfo(self, cmd, slot):
        """Fetch slot info.

        :param cmd: current command.
        :param slot: temperature slot.
        :type slot: int
        :raise: Exception with warning message.
        """
        ret = self.sendOneCommand('SYST:CTYP? %d00' % slot, cmd=cmd)
        company, modelNumber, serialNumber, firmware = ret.split(',')
        return '"%s", "%s", %s, %s' % (company, modelNumber, serialNumber, firmware)

    def _fetchError(self, cmd):
        """Fetch controller error.

        :param cmd: current command.
        :raise: RuntimeError if the controller returns an error.
        """
        errorCode, errorMsg = self.sendOneCommand('SYST:ERR?', cmd=cmd).split(',')

        if int(errorCode) != 0:
            cmd.warn('error=%d,%s' % (int(errorCode), errorMsg))
            raise RuntimeError(errorMsg)

        return int(errorCode), errorMsg

    def createSock(self):
        """Create socket in operation, simulator otherwise.
        """
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def handleTimeout(self, cmd=None):
        """Call FSMThread.handleTimeout, if bia is on check for biaOverHeat.
        """
        FSMThread.handleTimeout(self, cmd=cmd)
        self.biaOverHeat = self.biaTemp > self.biaTempLimit
