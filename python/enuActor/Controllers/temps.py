__author__ = 'alefur'

import logging

import enuActor.Controllers.bufferedSocket as bufferedSocket
import numpy as np
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.simulator.temps_simu import TempsSim


class temps(FSMDev, QThread, bufferedSocket.EthComm):
    channels = {1: '101:110',
                2: '201:210'}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """

        bufferedSocket.EthComm.__init__(self)
        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name)

        self.sock = None
        self.sim = None
        self.EOL = '\n'

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\n')

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.defaultSamptime = 15

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

    def start(self, cmd=None, doInit=True, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice().

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('temps', 'mode') if mode is None else mode
        self.host = self.actor.config.get('temps', 'host')
        self.port = int(self.actor.config.get('temps', 'port'))
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
        self.getError(cmd=cmd, doClose=False)
        self.getInfo(cmd=cmd, doClose=False)

        self.getTemps(cmd, slot=1, doClose=False)
        self.getTemps(cmd, slot=2)

    def getStatus(self, cmd):
        """| Get status and generate temps keywords.

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        cmd.inform('tempsFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('tempsMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            try:
                self.getTemps(cmd, slot=1, doClose=False)
            except:
                raise
            finally:
                self.getTemps(cmd, slot=2)

        cmd.finish()

    def getTemps(self, cmd, slot, doClose=True):
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
                resistances = self.fetchResistance(slot=slot, doClose=doClose)
                temps = self.convert(resistances=resistances, calib=self.calib[slot])
            else:
                temps = self.fetchTemps(slot=slot, doClose=doClose)

            cmd.inform('temps%d=%s' % (slot, ','.join(['%.3f' % float(temp) for temp in temps])))

        except:
            cmd.warn('temps%d=%s' % (slot, ','.join(['%.3f' % float(temp) for temp in np.ones(10) * np.nan])))
            raise

    def getResistance(self, cmd, slot, doClose=True):
        """|  generate res keyword for a dedicated slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        try:
            resistances = self.fetchResistance(slot=slot, doClose=doClose)
            cmd.inform('res%d=%s' % (slot, ','.join(['%.5f' % float(res) for res in resistances])))

        except:
            cmd.warn('res%d=%s' % (slot, ','.join(['%.5f' % float(res) for res in np.ones(10) * np.nan])))
            raise

    def fetchResistance(self, slot, doClose=True):
        """|  fetch resistance values for a specified slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:FRES? 100,0.0003,(@%s)' % channels, doClose=doClose)
        return np.array([float(res) for res in ret.split(',')])

    def fetchTemps(self, slot, doClose=True):
        """|  fetch temperature values for a specified slot.

        :param cmd: on going command
        :param slot: temperature slot
        :type slot:int
        :raise: Exception if a command fail
        """
        channels = self.channels[slot]

        ret = self.sendOneCommand('MEAS:TEMP? FRTD, (@%s)' % channels, doClose=doClose)
        return np.array([float(temp) for temp in ret.split(',')])

    def getInfo(self, cmd, doClose=True):
        """|  fetch controller info.

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        cmd.inform('slot1="%s"' % self.sendOneCommand('SYST:CTYP? 100', doClose=False))
        cmd.inform('slot2="%s"' % self.sendOneCommand('SYST:CTYP? 200', doClose=False))
        cmd.inform('firmware=%s' % self.sendOneCommand('SYST:VERS?', doClose=doClose))

    def getError(self, cmd, doClose=True):
        """|  fetch controller error

        :param cmd: on going command
        :raise: RuntimeError if the controller returns an error
        """
        errorCode, errorMsg = self.sendOneCommand('SYST:ERR?', doClose=doClose).split(',')

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

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
