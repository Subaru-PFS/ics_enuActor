__author__ = 'alefur'
import copy

from fysom import Fysom

from actorcore.QThread import QThread


class Device(QThread):
    map = {'events': [
        {'name': 'loadOk', 'src': 'none', 'dst': 'LOADED'},
        {'name': 'loadFailed', 'src': 'none', 'dst': 'FAILED'},
        {'name': 'commOk', 'src': 'LOADED', 'dst': 'INIT'},
        {'name': 'commFailed', 'src': 'LOADED', 'dst': 'FAILED'},
        {'name': 'changeMode', 'src': ['LOADED', 'INIT', 'IDLE', 'FAILED', 'OFF', 'none'], 'dst': 'none'},
        {'name': 'initOk', 'src': ['INIT', 'IDLE'], 'dst': 'IDLE'},
        {'name': 'initFailed', 'src': ['INIT', 'IDLE'], 'dst': 'FAILED'},
        {'name': 'cmdFailed', 'src': ['IDLE', 'INIT', 'BUSY'], 'dst': 'FAILED'},
        {'name': 'getBusy', 'src': 'IDLE', 'dst': 'BUSY'},
        {'name': 'getIdle', 'src': 'BUSY', 'dst': 'IDLE'},
        {'name': 'shutdown', 'src': ['IDLE', 'INIT'], 'dst': 'OFF'},
        {'name': 'ack', 'src': ['FAILED'], 'dst': 'IDLE'},

    ]}

    def __init__(self, actor, name):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        super(Device, self).__init__(actor, name, timeout=2)

        self.currMode = "undef"
        self.fsm = Fysom(copy.deepcopy(Device.map))
        self.fsm.onchangestate = self.printstatechange

    def changeMode(self, cmd=None, mode=None):
        """change mode from config file or from argument """
        cmd = self.actor.bcast if not cmd else cmd

        if self.loadCfg(cmd):
            cmd.inform("text='Loading %s parameters from config file...'"%self.name)
            self.currMode = mode if mode else self.currMode
            self.fsm.loadOk()
            if self.startCommunication(cmd):
                self.fsm.commOk()
                return True
            else:
                self.fsm.commFailed()
                return False
        else:
            self.fsm.loadFailed()
            return False

    def loadCfg(self, cmd):
        """prototype """
        self.currMode = self.actor.config.get(self.name, 'mode')
        return True

    def startCommunication(self, cmd):
        """prototype """
        return True

    def initialise(self, cmd):
        """prototype """
        return True

    def printstatechange(self, e):
        self.actor.bcast.inform('state=%s' % self.fsm.current)

    def stop(self):
        self.exit()

    def handleTimeout(self):
        pass
