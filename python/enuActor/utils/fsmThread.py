import time

from actorcore.FSM import FSMDevice
from actorcore.QThread import QThread


class FSMThread(FSMDevice, QThread):
    def __init__(self, actor, name, events=False, substates=False, doInit=False):
        """This combine QThread and FSMDevice.

        :param actor: enuActor.
        :param name: controller name.
        :param events: event list for FSM device.
        :param substates: substates list for FSM device.
        :param doInit: perform init automatically at startup.
        """
        self.currCmd = False
        self.doInit = doInit
        self.last = 0
        self.monitor = 60

        QThread.__init__(self, actor, name, timeout=15)
        FSMDevice.__init__(self, actor, name, events=events, substates=substates)

    def loadCfg(self, cmd, mode=None):
        """Called by FSM loading state callback, loadCfg=>openComm=>testComm.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        self._loadCfg(cmd, mode=mode)
        FSMDevice.loadCfg(self, cmd)

    def openComm(self, cmd):
        """Called by FSM loading state callback, loadCfg=>openComm=>testComm.

        :param cmd: current command.
        :raise: socket.error if the communication has failed.
        """
        self._openComm(cmd)
        FSMDevice.openComm(self, cmd)

    def testComm(self, cmd):
        """Called by FSM loading state callback, loadCfg=>openComm=>testComm.

        :param cmd: current command.
        :raise: Exception if the communication has failed with the controller.
        """
        self._testComm(cmd)
        FSMDevice.testComm(self, cmd)

    def init(self, cmd, **kwargs):
        """Called by FSM initialising state callback.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self._init(cmd, **kwargs)
        FSMDevice.init(self, cmd)

    def _loadCfg(self, cmd, mode=None):
        """Intended to be overridden."""
        pass

    def _openComm(self, cmd):
        """Intended to be overridden."""
        pass

    def _testComm(self, cmd):
        """Intended to be overridden."""
        pass

    def _closeComm(self, cmd):
        """Intended to be overridden."""
        pass

    def _init(self, cmd, **kwargs):
        """Intended to be overridden."""
        pass

    def leaveCleanly(self, cmd):
        """stop monitoring and close communication.

        :param cmd: current command.
        """
        self.monitor = 0
        self._closeComm(cmd=cmd)

    def start(self, cmd=None, doInit=None, mode=None):
        """Start state machine and start QThread.

        :param cmd: current command.
        """
        doInit = self.doInit if doInit is None else doInit
        try:
            FSMDevice.start(self, cmd=cmd, doInit=doInit, mode=mode)
            self.generate(cmd=cmd, doFinish=False)
        finally:
            QThread.start(self)

    def stop(self, cmd):
        """Free up any hardware ressources, stop state machine and stop QThread.

        :param cmd: current command.
        """
        self.leaveCleanly(cmd=cmd)
        FSMDevice.stop(self, cmd=cmd)
        self.exit()

    def generate(self, cmd=None, doFinish=True):
        """Generate FSM state and substate, current operating mode and get statuses.

        :param cmd: current command.
        :param doFinish: if True finish current command.
        """
        cmd = self.actor.bcast if cmd is None else cmd

        cmd.inform('%sFSM=%s,%s' % (self.name, self.states.current, self.substates.current))
        cmd.inform('%sMode=%s' % (self.name, self.mode))

        if self.states.current in ['LOADED', 'ONLINE']:
            try:
                self.getStatus(cmd)
                self.last = time.time()
            finally:
                self._closeComm(cmd)

        if doFinish:
            cmd.finish()

    def handleTimeout(self, cmd=None):
        """Called when thread is idle, generate keywords if monitor>0.

        :param cmd: current command.
        """
        if self.exitASAP:
            raise SystemExit()

        if self.monitor and (time.time() - self.last) > self.monitor:
            cmd = self.actor.bcast if cmd is None else cmd
            try:
                self.generate(cmd)
            except Exception as e:
                cmd.fail('text=%s' % self.actor.strTraceback(e))
