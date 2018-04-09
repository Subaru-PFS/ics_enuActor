__author__ = 'alefur'
import logging
import socket

from actorcore.QThread import QThread
from fysom import Fysom
from enuActor.utils.wrap import loading, initialising


class Device(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)
        self.mode = "undef"
        self.fsm = Fysom({'initial': 'OFF',
                          'events': [
                              {'name': 'startLoading', 'src': 'OFF', 'dst': 'LOADING'},
                              {'name': 'loadDeviceOk', 'src': 'LOADING', 'dst': 'LOADED'},
                              {'name': 'loadDeviceFailed', 'src': 'LOADING', 'dst': 'FAILED'},
                              {'name': 'startInit', 'src': 'LOADED', 'dst': 'INITIALISING'},
                              {'name': 'initialiseOk', 'src': 'INITIALISING', 'dst': 'IDLE'},
                              {'name': 'initialiseFailed', 'src': 'INITIALISING', 'dst': 'FAILED'},
                              {'name': 'changeMode', 'src': ['LOADED', 'IDLE'], 'dst': 'LOADING'},
                              {'name': 'goBusy', 'src': 'IDLE', 'dst': 'BUSY'},
                              {'name': 'goIdle', 'src': 'BUSY', 'dst': 'IDLE'},
                              {'name': 'goFailed', 'src': 'BUSY', 'dst': 'FAILED'},
                              {'name': 'shutdown', 'src': ['LOADED', 'IDLE'], 'dst': 'OFF'},
                          ],
                          'callbacks': {
                              'onLOADING': self.loadDevice,
                              'onINITIALISING': self.initDevice,
                          }})

    @loading
    def loadDevice(self, e):
        """| *Wrapper @loading* handles the state machine.
        | Load the device and catch any raised exception

        :param e: fsm event
        :return: - True : fsm (LOADING => LOADED)
                 - False : fsm (LOADING => FAILED)
        """
        cmd = e.cmd if hasattr(e, "cmd") else self.actor.bcast
        mode = e.mode if hasattr(e, "mode") else None

        try:
            try:
                self.loadCfg(cmd, mode)
                cmd.inform("text='%s config File successfully loaded" % self.name)
            except:
                cmd.warn("text='%s Config file badly formatted'" % self.name)
                raise
            try:
                cmd.inform("text='Connecting to %s in ...%s'" % (self.name.upper(), self.mode))
                self.startCommunication(cmd)
                cmd.inform("text=' %s Connected'" % self.name)
            except:
                cmd.warn("text='%s Connection has failed'" % self.name)
                raise

        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            return False

        return True

    @initialising
    def initDevice(self, e):
        """| *wrapper @initialising* handles the state machine.
        | Call initialise and catch any raised Exception,

        :param e: fsm event
        :return: - True : fsm (INITIALISING => IDLE)
                 - False : fsm (INITIALISING => FAILED)
        """
        cmd = e.cmd if hasattr(e, "cmd") else self.actor.bcast
        try:
            self.initialise(cmd)
            cmd.inform("text='%s successfully initialised" % self.name)

        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            return False

        return True

    def loadCfg(self, cmd, mode=None):
        """| Load configuration file. (prototype)

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.mode = self.actor.config.get(self.name, 'mode') if mode is None else mode

    def startCommunication(self, cmd):
        """| Start communication with the controller. (prototype)

        :param cmd: on going command
        :raise: Exception if the communication has failed with the controller
        """
        pass

    def initialise(self, cmd):
        """ | Initialise device. (prototype)

        :param cmd: on going command
        :raise: Exception if a command fail
        """
        pass

    def getStatus(self, cmd, doFinish=True):
        """| Get controller status and published its keywords. (prototype)
         - controller=fsm, mode

        :param cmd: on going command
        :param doFinish: if True finish command

        """
        ender = cmd.finish if doFinish else cmd.inform
        ender("%s=%s,%s" % (self.name.upper(), self.fsm.current, self.mode))

    def connectSock(self):
        """| Connect socket if self.sock is None.

        :return: - sock in operation
                 - simulator in simulation
        """
        if self.sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) if self.mode == "operation" else self.simulator
            s.settimeout(1.0)
            s.connect((self.host, self.port))

            self.sock = s

        return self.sock

    def closeSock(self):
        """| Close the socket.

        :raise: Exception if closing socket has failed
        """

        if self.sock is not None:
            try:
                self.sock.close()

            except Exception as e:
                self.sock = None
                raise

        self.sock = None

    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
        """| Send one command and return one response.

        :param cmdStr: (str) The command to send.
        :param doClose: If True (the default), the device socket is closed before returning.
        :param cmd: on going command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)

        s = self.connectSock()

        try:
            s.sendall(fullCmd.encode())

        except Exception as e:
            self.closeSock()
            raise

        reply = self.getOneResponse(sock=s, cmd=cmd)

        if doClose:
            self.closeSock()

        return reply

    def getOneResponse(self, sock=None, cmd=None):
        """| Attempt to receive data from the socket.

        :param sock: socket
        :param cmd: command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        if sock is None:
            sock = self.connectSock()

        ret = self.ioBuffer.getOneResponse(sock=sock, cmd=cmd)
        reply = ret.strip()

        self.logger.debug('received %r', reply)

        return reply

    def printstatechange(self, e):
        """| Print state when fsm change.

        :param e: fsm event
        """
        self.logger.debug('%s state=%r' % self.name.upper(), self.fsm.current)

    def stop(self):
        """| Stop thread
        """
        self.exit()

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
