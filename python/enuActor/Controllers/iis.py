__author__ = 'alefur'
import logging

import enuActor.utils.bufferedSocket as bufferedSocket
from enuActor.Simulators.iis import IisSim
from enuActor.utils.fsmThread import FSMThread


class iis(FSMThread, bufferedSocket.EthComm):

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
        self.EOL = '\r\n'

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

    def loadCfg(self, cmd, mode=None):
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """

        self.mode = self.actor.config.get('bsh', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('iis', 'host'),
                                        port=int(self.actor.config.get('iis', 'port')),
                                        EOL='\r\n')

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        self.sim = IisSim()  # Create new simulator
        s = self.connectSock()

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='ok\r\n')

    def init(self, cmd):
        """ Initialise the temperature controller

        wrapper @safeCheck handles the state machine
        :param e : fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """

        ret = self.sendOneCommand("init", doClose=False, cmd=cmd)

    def getStatus(self, cmd):
        """getStatus
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, state, mode, 8*temperature
                 False, state, mode, 8*nan if not initialised or an error had occured
        """

        cmd.inform('iisFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('iisMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            self.checkStatus(cmd)

        cmd.finish()

    def checkStatus(self, cmd):
        """fetchTemps
        temperature is nan if the controller is unreachable
        :param cmd,
        :return True, 8*temperature
                 False, 8*nan if not initialised or an error had occured
        """

        try:
            ret = self.sendOneCommand("status", cmd=cmd)

        except:
            cmd.warn('iis=unknown')
            raise

        cmd.inform('iis=%s' % ret)

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
