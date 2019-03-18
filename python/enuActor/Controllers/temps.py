__author__ = 'alefur'

import logging

import enuActor.utils.bufferedSocket as bufferedSocket
import numpy as np
from enuActor.Simulators.temps import TempsSim
from enuActor.utils.fsmThread import FSMThread


class temps(FSMThread, bufferedSocket.EthComm):
    channels = {1: '101:110',
                2: '201:210'}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """

        FSMThread.__init__(self, actor, name, doInit=True)

        self.sock = None
        self.sim = None

        self.monitor = 15

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
        return np.array([float(c) for c in self.actor.config.get('temps', probe).split(',')])

    def loadCfg(self, cmd, mode=None):
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
        self.calib = {1: np.array([self.getProbeCoeff(str(probe)) for probe in range(101, 111)]),
                      2: np.array([self.getProbeCoeff(str(probe)) for probe in range(201, 211)])}

    def startComm(self, cmd):
        """| Start socket with the controller or simulate it.
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.sim = TempsSim()  # Create new simulator

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\n')
        s = self.connectSock()

    def init(self, cmd):
        """| Initialise temperature controller, called by self.initDevice().
        - get error
        - get info
        - get slot 1 temperature
        - get slot 2 temperature

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """
        self.getError(cmd=cmd)
        self.getInfo(cmd=cmd)

    def getStatus(self, cmd):
        """| Get status and generate temps keywords.

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        cmd.inform('tempsFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('tempsMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            try:
                self.getTemps(slot=1, cmd=cmd)
            except:
                raise
            finally:
                self.getTemps(slot=2, cmd=cmd)
                self.closeSock()

        cmd.finish()

    def getTemps(self, cmd, slot):
        """| generate temps keyword for a dedicated slot controller.
          if doCalib : get resistance and compute temperature according to the lab calibration
          else : get directly temperature from the controller

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        try:
            if self.doCalib:
                resistances = self.fetchResistance(slot=slot, cmd=cmd)
                temps = self.convert(resistances=resistances, calib=self.calib[slot])
            else:
                temps = self.fetchTemps(slot=slot, cmd=cmd)

            cmd.inform('temps%d=%s' % (slot, ','.join(['%.3f' % float(temp) for temp in temps])))

        except:
            cmd.warn('temps%d=%s' % (slot, ','.join(['%.3f' % float(temp) for temp in np.ones(10) * np.nan])))
            raise

    def getResistance(self, cmd, slot):
        """|  generate res keyword for a dedicated slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        try:
            resistances = self.fetchResistance(slot=slot, cmd=cmd)
            cmd.inform('res%d=%s' % (slot, ','.join(['%.5f' % float(res) for res in resistances])))

        except:
            cmd.warn('res%d=%s' % (slot, ','.join(['%.5f' % float(res) for res in np.ones(10) * np.nan])))
            raise

    def fetchResistance(self, cmd, slot):
        """|  fetch resistance values for a specified slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:FRES? 100,0.0003,(@%s)' % channels, cmd=cmd)
        return np.array([float(res) for res in ret.split(',')])

    def fetchTemps(self, cmd, slot):
        """|  fetch temperature values for a specified slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:TEMP? FRTD, (@%s)' % channels, cmd=cmd)
        return np.array([float(temp) for temp in ret.split(',')])

    def getInfo(self, cmd):
        """|  fetch controller info.

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        cmd.inform('slot1="%s"' % self.sendOneCommand('SYST:CTYP? 100', cmd=cmd))
        cmd.inform('slot2="%s"' % self.sendOneCommand('SYST:CTYP? 200', cmd=cmd))
        cmd.inform('firmware=%s' % self.sendOneCommand('SYST:VERS?', cmd=cmd))

    def getError(self, cmd):
        """|  fetch controller error

        :param cmd: on going command
        :raise: RuntimeError if the controller returns an error
        """
        errorCode, errorMsg = self.sendOneCommand('SYST:ERR?', cmd=cmd).split(',')

        if int(errorCode) != 0:
            cmd.warn('error=%d,%s' % (int(errorCode), errorMsg))
            raise RuntimeError(errorMsg)

        cmd.inform('error=%d,%s' % (int(errorCode), errorMsg))

    def convert(self, resistances, calib):
        """|  convert resistance to temperature using lab calibration

        :param resistances: resistance value
        :param calib: polynomial coeffient
        :type resistances: np.array
        :type calib: np.array
        :return: temperature
        :rtype: np.array
        """
        return np.array([np.polyval(calib[i], resistances[i]) for i in range(len(resistances))])

    def createSock(self):
        """| create socket or fake it returning a simulator.

        :raise: Exception if a command fail
        """
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
