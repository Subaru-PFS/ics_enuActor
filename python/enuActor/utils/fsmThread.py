import time

from actorcore.FSM import FSMDevice
from actorcore.QThread import QThread


class FSMThread(FSMDevice, QThread):
    def __init__(self, actor, name, events=False, substates=False, doInit=False):
        self.currCmd = False
        self.doInit = doInit
        self.last = 0
        self.monitor = 60

        QThread.__init__(self, actor, name, timeout=2)
        FSMDevice.__init__(self, actor, name, events=events, substates=substates)

    def loadCfg(self, cmd, mode=None):
        self._loadCfg(cmd, mode=mode)
        FSMDevice.loadCfg(self, cmd)

    def openComm(self, cmd):
        self._openComm(cmd)
        FSMDevice.openComm(self, cmd)

    def testComm(self, cmd):
        self._testComm(cmd)
        FSMDevice.testComm(self, cmd)

    def init(self, cmd, *args):
        self._init(cmd, *args)
        FSMDevice.init(self, cmd)

    def _loadCfg(self, cmd, mode=None):
        pass

    def _openComm(self, cmd):
        pass

    def _testComm(self, cmd):
        pass

    def _init(self, cmd, *args):
        pass

    def start(self, cmd=None, doInit=None, mode=None):
        doInit = self.doInit if doInit is None else doInit
        QThread.start(self)
        FSMDevice.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        FSMDevice.stop(self, cmd=cmd)
        self.exit()

    def generate(self, cmd):
        cmd.inform('%sFSM=%s,%s' % (self.name, self.states.current, self.substates.current))
        cmd.inform('%sMode=%s' % (self.name, self.mode))

        if self.states.current in ['LOADED', 'ONLINE']:
            try:
                self.getStatus(cmd)
            finally:
                self.closeSock()

        cmd.finish()

    def handleTimeout(self, cmd=None):
        if self.exitASAP:
            raise SystemExit()

        if self.monitor and (time.time() - self.last) > self.monitor:
            cmd = self.actor.bcast if cmd is None else cmd
            try:
                self.generate(cmd)
            except Exception as e:
                cmd.fail('text=%s' % self.actor.strTraceback(e))

            self.last = time.time()
