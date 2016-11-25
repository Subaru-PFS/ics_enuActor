__author__ = 'alefur'
import logging
import sys
import socket

from actorcore.QThread import QThread

from enuActor.fysom import Fysom
from enuActor.utils.wrap import loading, initialising



class Device(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        QThread.__init__(self, actor, name, timeout=2)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)
        self.currMode = "undef"
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
        """load device

        load Configuration file and startcommunication
        wrapper @safeCheck handles the state machine

        :param e,fsm event
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception
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
                cmd.inform("text='Connecting to %s in ...%s'" % (self.name.upper(), self.currMode))
                self.startCommunication(cmd)
                cmd.inform("text=' %s Connected'" % self.name)
            except:
                cmd.warn("text='%s Connection has failed'" % self.name)
                raise

        except Exception as e:
            cmd.warn("text='%s load device failed %s'" % (self.name.upper(), self.formatException(e, sys.exc_info()[2])))

            return False

        return True

    @initialising
    def initDevice(self, e):
        """load device

        load Configuration file and startcommunication
        wrapper @safeCheck handles the state machine

        :param e,fsm event
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception
        """
        cmd = e.cmd if hasattr(e, "cmd") else self.actor.bcast
        try:
            self.initialise(cmd)
            cmd.inform("text='%s successfully initialised" % self.name)

        except Exception as e:
            cmd.warn("text='%s init device failed %s'" % (self.name.upper(), self.formatException(e, sys.exc_info()[2])))

            return False

        return True

    def loadCfg(self, cmd, mode=None):
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """

        self.currMode = self.actor.config.get(self.name, 'mode') if mode is None else mode

    def startCommunication(self, cmd):
        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the board, fsm (LOADING => LOADED)
                 False, ret: if the communication failed with the board, ret is the error, fsm (LOADING => FAILED)
        """
        pass

    def initialise(self, cmd):
        """ Initialise device


        wrapper @safeCheck handles the state machine
        :param e, fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """
        pass

    def getStatus(self, cmd, doFinish=True):
        """getStatus
        position is nan if the controller is unreachable
        :param cmd,
        :return True, status

        """
        ender = cmd.finish if doFinish else cmd.inform
        ender("%s=%s,%s" % (self.name.upper(), self.fsm.current, self.currMode))

    def printstatechange(self, e):
        print ('%s state=%s' % (self.name.upper(), self.fsm.current))

    def stop(self):
        self.exit()

    def handleTimeout(self):
        pass

    def formatException(self, e, traceback=""):

        return "%s %s %s" % (str(type(e)).replace("'", ""), str(type(e)(*e.args)).replace("'", ""), traceback)

    def connectSock(self):
        """ Connect socket if self.sock is None

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """

        if self.sock is None:
            try:
                s = socket.socket(socket.AF_INET,
                                  socket.SOCK_STREAM) if self.currMode == "operation" else self.simulator
                s.settimeout(1.0)
            except Exception as e:
                raise Exception("%s failed to create socket : %s" % (self.name, self.formatException(e)))

            try:
                s.connect((self.host, self.port))
            except Exception as e:
                raise Exception("%s failed to connect socket : %s" % (self.name, self.formatException(e)))

            self.sock = s

        return self.sock

    def closeSock(self):
        """ close socket

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """

        if self.sock is not None:
            try:
                self.sock.close()

            except Exception as e:
                raise Exception("%s failed to close socket : %s" % (self.name, self.formatException(e)))

        self.sock = None

    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
        """ Send one command and return one response.

        Args
        ----
        cmdStr : str
           The command to send.
        doClose : bool
           If True (the default), the device socket is closed before returning.

        Returns
        -------
        str : the single response string, with EOLs stripped.

        Raises
        ------
        IOError : from any communication errors.
        """

        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)

        s = self.connectSock()
        try:
            s.sendall(fullCmd)

        except Exception as e:
            raise Exception("%s failed to send %s : %s" % (self.name.upper(), fullCmd, self.formatException(e)))

        reply = self.getOneResponse(sock=s, cmd=cmd)
        if doClose:
            self.closeSock()

        return reply

    def getOneResponse(self, sock=None, cmd=None):
        if sock is None:
            sock = self.connectSock()

        ret = self.ioBuffer.getOneResponse(sock=sock, cmd=cmd)
        reply = ret.strip()

        self.logger.debug('received %r', reply)

        return reply
