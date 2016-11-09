__author__ = 'alefur'
import copy
from actorcore.QThread import QThread
from fysom import Fysom
from wrap import safeCheck


class Device(QThread):
    def __init__(self, actor, name):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        super(Device, self).__init__(actor, name, timeout=2)

        self.currMode = "undef"
        self.fsm = Fysom({'initial': 'OFF',
                          'events': [
                              {'name': 'startLoading', 'src': 'OFF', 'dst': 'LOADING'},
                              {'name': 'loadCfgOk', 'src': 'LOADING', 'dst': 'LOADED'},
                              {'name': 'loadCfgFailed', 'src': 'LOADING', 'dst': 'FAILED'},
                              {'name': 'startCommunicationOk', 'src': 'LOADED', 'dst': 'CONNECTED'},
                              {'name': 'startCommunicationFailed', 'src': 'LOADED', 'dst': 'FAILED'},
                              {'name': 'startInit', 'src': 'CONNECTED', 'dst': 'INITIALISING'},
                              {'name': 'initialiseOk', 'src': 'INITIALISING', 'dst': 'IDLE'},
                              {'name': 'initialiseFailed', 'src': 'INITIALISING', 'dst': 'FAILED'},
                              {'name': 'changeMode', 'src': ['CONNECTED', 'IDLE'], 'dst': 'LOADING'},
                              {'name': 'goBusy', 'src': 'IDLE', 'dst': 'BUSY'},
                              {'name': 'goIdle', 'src': 'BUSY', 'dst': 'IDLE'},
                              {'name': 'shutdown', 'src': ['CONNECTED', 'IDLE'], 'dst': 'OFF'},
                          ],
                          'callbacks': {
                              'onLOADING': self.loadCfg,
                              'onLOADED': self.startCommunication,
                              'onINITIALISING': self.initialise,
                          }})

        # self.fsm.onchangestate = self.printstatechange

    @safeCheck
    def loadCfg(self, e):
        """prototype """

        self.currMode = self.actor.config.get(self.name, 'mode')
        return True, "load Configuration file Ok"

    @safeCheck
    def startCommunication(self, e):
        """prototype """
        return True, "startCommunication Ok"

    @safeCheck
    def initialise(self, e):
        """prototype """
        return True, "Initialisation Ok"

    def getStatus(self):
        return True, "status"

    def printstatechange(self, e):
        print ('%s state=%s' % (self.name, self.fsm.current))

    def stop(self):
        self.exit()

    def handleTimeout(self):
        pass
