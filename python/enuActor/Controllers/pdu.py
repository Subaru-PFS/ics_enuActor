__author__ = 'alefur'
import logging
import time

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.Simulators.pdu import PduSim


class pdu(FSMDev, QThread, bufferedSocket.EthComm):
    powerPorts = ('slit', 'xenon', 'hgar', 'krypton')

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

        bufferedSocket.EthComm.__init__(self)
        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('SWITCHING', self.switch)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n>')
        self.EOL = '\r\n'

        self.mode = ''
        self.sim = None

        self.state = {}

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    def getOutlet(self, channel):
        return self.actor.config.get('outlets', channel).strip().zfill(2)

    def start(self, cmd=None, doInit=True, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.host = self.actor.config.get('pdu', 'host')
        self.port = int(self.actor.config.get('pdu', 'port'))
        self.mode = self.actor.config.get('pdu', 'mode') if mode is None else mode

        for channel in self.powerPorts:
            self.getOutlet(channel=channel)

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        cmd.inform('pduMode=%s' % self.mode)

        self.sim = PduSim()
        s = self.connectSock()

    def switch(self, e):
        toSwitch = dict([(channel, 'on') for channel in e.switchOn] + [(channel, 'off') for channel in e.switchOff])

        try:
            for channel, state in toSwitch.items():
                cmdStr = "sw o%s %s imme" % (self.getOutlet(channel=channel), state)
                ret = self.sendOneCommand(cmdStr=cmdStr, cmd=e.cmd, doRaise=False)
                self.checkChannel(cmd=e.cmd, channel=channel)
                time.sleep(2)

            self.substates.idle(cmd=e.cmd)

        except:
            self.substates.fail(cmd=e.cmd)
            raise

        finally:
            self.closeSock()

    def checkChannel(self, cmd, channel):

        outlet = self.getOutlet(channel=channel)

        ret = self.sendOneCommand('read status o%s format' % outlet, cmd=cmd)
        __, outlet, state = ret.rsplit(' ', 2)

        self.setState(cmd=cmd, outlet=outlet, channel=channel, state=state)

    def getStatus(self, cmd):
        cmd.inform('pduMode=%s' % self.mode)
        cmd.inform('pduFSM=%s,%s' % (self.states.current, self.substates.current))

        channels = [channel for channel in self.actor.config.options('outlets')]

        if self.states.current == 'ONLINE':
            try:
                for channel in channels:
                    self.checkChannel(cmd=cmd, channel=channel)

                cmd.finish('pduVAW=%s,%s,%s' % self.checkVaw(cmd))

            except:
                raise

            finally:
                self.closeSock()

    def checkVaw(self, cmd):

        voltage = self.sendOneCommand('read meter dev volt simple', cmd=cmd)
        current = self.sendOneCommand('read meter dev curr simple', cmd=cmd)
        power = self.sendOneCommand('read meter dev pow simple', cmd=cmd)

        return voltage, current, power

    def setState(self, cmd, outlet, channel, state):

        self.state[channel] = state
        cmd.inform('pduport%s=%s,%s' % (outlet, channel, state))

    def connectSock(self):
        """ Connect socket if self.sock is None

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """
        if self.sock is None:
            s = self.createSock()
            s.settimeout(2.0)
            s.connect((self.host, self.port))

            try:
                self.sock = self.authenticate(sock=s)
            except ValueError:
                self.closeSock()
                return self.connectSock()

        return self.sock

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None, doRaise=True):
        fullCmd = '%s%s' % (cmdStr, self.EOL)
        reply = bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)

        return self.parseResponse(cmd=cmd, fullCmd=fullCmd, reply=reply, doRaise=doRaise)

    def parseResponse(self, cmd, fullCmd, reply, doRaise, retry=True):
        if fullCmd in reply:
            return reply.split(fullCmd)[1].strip()

        if retry:
            time.sleep(1)
            reply = self.getOneResponse(cmd=cmd)
            return self.parseResponse(cmd=cmd, fullCmd=fullCmd, reply=reply, doRaise=doRaise, retry=False)

        if doRaise:
            raise ValueError('Command was not echoed properly')

        return

    def authenticate(self, sock):
        time.sleep(0.1)

        ret = sock.recv(1024).decode('utf-8', 'ignore')

        if 'Login: ' not in ret:
            raise ValueError('Could not login')

        sock.sendall('teladmin\r\n'.encode('utf-8'))

        time.sleep(0.1)
        ret = sock.recv(1024).decode('utf-8', 'ignore')

        if 'Password:' not in ret:
            raise ValueError('Bad login')

        sock.sendall('toto\r\n'.encode('utf-8'))

        time.sleep(0.1)
        ret = sock.recv(1024).decode('utf-8', 'ignore')

        if 'Logged in successfully' not in ret:
            raise ValueError('Bad password')

        return sock

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
