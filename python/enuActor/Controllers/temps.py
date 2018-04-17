__author__ = 'alefur'

import logging
import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.simulator.temps_simu import TempsSim


class temps(FSMDev, QThread, bufferedSocket.EthComm):

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
        self.EOL = '\r\n'

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')

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

        ret = self.sendOneCommand("CRDG?A", doClose=False, cmd=cmd)
        for temp in ret.split(','):
            if not -10 <= float(temp) < 50:
                raise Exception("Temp reading is wrong : %.2f" % ret)

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
            self.fetchTemps(cmd)

        cmd.finish()

    def fetchTemps(self, cmd):
        """fetchTemps
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, 8*temperature
                 False, 8*nan if not initialised or an error had occured
        """

        try:
            temps1 = self.sendOneCommand("CRDG?A", doClose=False, cmd=cmd)
            temps2 = self.sendOneCommand("CRDG?B", cmd=cmd)

        except:
            cmd.warn('temps=%s' % ','.join(10 * ['nan']))
            raise

        cmd.inform('temps=%s,%s' % (temps1, temps2))

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
