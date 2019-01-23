__author__ = 'alefur'

import logging

import enuActor.Controllers.bufferedSocket as bufferedSocket
import numpy as np
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.Simulators.temps import TempsSim


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
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """

        self.mode = self.actor.config.get('temps', 'mode') if mode is None else mode
        self.host = self.actor.config.get('temps', 'host')
        self.port = int(self.actor.config.get('temps', 'port'))

        self.calib = {1: np.array([self.getProbeCoeff(str(probe)) for probe in range(101, 111)]),
                      2: np.array([self.getProbeCoeff(str(probe)) for probe in range(201, 211)])}

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        self.sim = TempsSim()  # Create new simulator
        s = self.connectSock()

    def init(self, cmd):
        """ Initialise the temperature controller

        wrapper @safeCheck handles the state machine
        :param e : fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """
        self.getError(cmd=cmd, doClose=False)
        self.getInfo(cmd=cmd, doClose=False)

        self.fetchTemps(cmd, slot=1, doClose=False)
        self.fetchTemps(cmd, slot=2)

    def getStatus(self, cmd):
        """getStatus
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, state, mode, 8*temperature
                 False, state, mode, 8*nan if not initialised or an error had occured
        """

        cmd.inform('tempsFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('tempsMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            try:
                self.fetchTemps(cmd, slot=1, doClose=False)
            except:
                raise
            finally:
                self.fetchTemps(cmd, slot=2)

        cmd.finish()

    def fetchTemps(self, cmd, slot, doClose=True):
        """fetchTemps
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, 8*temperature
                 False, 8*nan if not initialised or an error had occured
        """
        calib = self.calib[slot]
        channels = self.channels[slot]

        try:
            ret = self.sendOneCommand('MEAS:TEMP? FRTD, (@%s)' % channels, doClose=doClose)
            temps = np.array([float(temp) for temp in ret.split(',')])
            offsets = np.array([np.polyval(calib[i], temps[i]) for i in range(10)])
            temps += offsets
            cmd.inform('temps%d=%s' % (slot, ','.join(['%.3f' % float(temp) for temp in temps])))

        except:
            cmd.warn('temps%d=%s' % (slot, ','.join(['%.3f' % float(temp) for temp in np.ones(10) * np.nan])))
            raise

    def fetchResistance(self, cmd, slot, doClose=True):
        """fetchTemps
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, 8*temperature
                 False, 8*nan if not initialised or an error had occured
        """
        channels = self.channels[slot]

        try:
            ret = self.sendOneCommand('MEAS:FRES? (@%s)' % channels, doClose=doClose)
            resistances = np.array([float(res) for res in ret.split(',')])
            cmd.inform('res%d=%s' % (slot, ','.join(['%.3f' % float(res) for res in resistances])))

        except:
            cmd.warn('res%d=%s' % (slot, ','.join(['%.3f' % float(res) for res in np.ones(10) * np.nan])))
            raise

    def getInfo(self, cmd, doClose=True):
        cmd.inform('slot1="%s"' % self.sendOneCommand('SYST:CTYP? 100', doClose=False))
        cmd.inform('slot2="%s"' % self.sendOneCommand('SYST:CTYP? 200', doClose=False))
        cmd.inform('firmware=%s' % self.sendOneCommand('SYST:VERS?', doClose=doClose))

    def getError(self, cmd, doClose=True):
        errorCode, errorMsg = self.sendOneCommand('SYST:ERR?', doClose=doClose).split(',')

        if int(errorCode) != 0:
            cmd.warn('error=%d,%s' % (int(errorCode), errorMsg))
            raise UserWarning(errorMsg)

        cmd.inform('error=%d,%s' % (int(errorCode), errorMsg))

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
