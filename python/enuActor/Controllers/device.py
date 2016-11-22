__author__ = 'alefur'
import logging
import sys

from actorcore.QThread import QThread

from enuActor.fysom import Fysom
from enuActor.Controllers.wrap import safeCheck


class Device(QThread):
    def __init__(self, actor, name,
                 loglevel=logging.DEBUG):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        super(Device, self).__init__(actor, name, timeout=2)
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
                              'onINITIALISING': self.initialise,
                          }})

    @safeCheck
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
            self.loadCfg(cmd, mode)
            self.startCommunication(cmd)

        except Exception as e:
            cmd.warn("text='%s load device failed : %s'" % (self.name, e))
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
        try:
            self.currMode = self.actor.config.get(self.name, 'mode') if mode is None else mode
        except Exception as e:
            raise type(e), type(e)("%s Config file badly formatted, Exception :  %s" % (self.name, e)), sys.exc_info()[
                2]

    def startCommunication(self, cmd):
        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the board, fsm (LOADING => LOADED)
                 False, ret: if the communication failed with the board, ret is the error, fsm (LOADING => FAILED)
        """
        cmd.inform("text='startCommunication Ok'")

    @safeCheck
    def initialise(self, e):
        """ Initialise device


        wrapper @safeCheck handles the state machine
        :param e, fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """
        return True

    def getStatus(self, cmd=None):
        """getStatus
        position is nan if the controller is unreachable
        :param cmd,
        :return True, status

        """
        return True, "status"

    def printstatechange(self, e):
        print ('%s state=%s' % (self.name, self.fsm.current))

    def stop(self):
        self.exit()

    def handleTimeout(self):
        pass
