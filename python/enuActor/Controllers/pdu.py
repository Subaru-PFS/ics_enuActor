__author__ = 'alefur'
import logging

import enuActor.utils.bufferedSocket as bufferedSocket
from enuActor.Simulators.pdu import PduSim
from enuActor.utils.fsmThread import FSMThread


class pdu(FSMThread, bufferedSocket.EthComm):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        substates = ['IDLE', 'SWITCHING', 'FAILED']
        events = [{'name': 'switch', 'src': 'IDLE', 'dst': 'SWITCHING'},
                  {'name': 'idle', 'src': ['SWITCHING', ], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['SWITCHING', ], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('SWITCHING', self.switching)
        self.state = {}
        self.sim = PduSim()

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

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file.

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('pdu', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('pdu', 'host'),
                                        port=int(self.actor.config.get('pdu', 'port')),
                                        EOL='\r\n')
        self.powerNames = dict([(key, val) for (key, val) in self.actor.config.items('outlets')])
        self.powerPorts = dict([(val, key) for (key, val) in self.actor.config.items('outlets')])

    def _openComm(self, cmd):
        """| Open socket with pdu controller or simulate it.

        :param cmd: on going command
        :raise: socket.error if the communication has failed with the controller
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n\r\n> ')
        s = self.connectSock()

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        v = float(self.sendOneCommand('read meter olt o01 volt simple', cmd=cmd))

    def getStatus(self, cmd):
        """| get all port status

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        for outlet in self.powerNames.keys():
            self.portStatus(cmd, outlet=outlet)

    def portStatus(self, cmd, outlet):
        """| get state, voltage, current, power

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        state = self.sendOneCommand('read status o%s simple' % outlet, cmd=cmd)
        v = float(self.sendOneCommand('read meter olt o%s volt simple' % outlet, cmd=cmd))
        a = float(self.sendOneCommand('read meter olt o%s curr simple' % outlet, cmd=cmd))
        w = float(self.sendOneCommand('read meter olt o%s pow simple' % outlet, cmd=cmd))

        cmd.inform('pduPort%s=%s,%s,%.2f,%.2f,%.2f' % (outlet, self.powerNames[outlet], state, v, a, w))
        self.state[self.powerNames[outlet]] = state

    def switching(self, cmd, powerPorts):
        """ switch on/off powerPorts dict

        :param cmd : current command,
        :raise: Exception if the communication has failed with the controller
        """
        for outlet, state in powerPorts.items():
            self.sendOneCommand('sw o%s %s imme' % (outlet, state), cmd=cmd)
            self.portStatus(cmd, outlet=outlet)

    def loginCommand(self, cmdStr, cmd=None, ioEOL=None):
        """ used to login

        :param cmd : current command,
        :param cmdStr: (str) The command to send.
        :raise: Exception if the communication has failed with the controller
        """
        self.ioBuffer.EOL = ioEOL if ioEOL is not None else self.ioBuffer.EOL

        return bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, cmd=cmd)

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        """| Send one command and return one response.

        :param cmdStr: (str) The command to send.
        :param doClose: If True (the default), the device socket is closed before returning.
        :param cmd: on going command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        fullCmd = '%s%s' % (cmdStr, self.EOL)
        reply = bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)

        if fullCmd not in reply:
            raise ValueError('Command was not echoed properly')

        return reply.split(fullCmd)[1].strip()

    def connectSock(self):
        """| Connect socket if self.sock is None

        :param cmd : current command,
        """
        if self.sock is None:
            s = self.createSock()
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            self.sock = s
            self.authenticate()

        return self.sock

    def authenticate(self):
        """| log to the telnet server

        :param cmd : current command,
        """
        try:
            self.loginCommand('teladmin', ioEOL='Password: ')
            self.loginCommand('pdu.%s' % self.actor.name, ioEOL='Telnet server 1.1\r\n\r\n> ')

            self.ioBuffer.EOL = '\r\n\r\n> '
        except:
            self.sock = None
            raise

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
