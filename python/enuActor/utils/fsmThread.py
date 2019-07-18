import time

from actorcore.FSM import FSMDevice
from actorcore.QThread import QThread


class FSMThread(FSMDevice, QThread):
    def __init__(self, actor, name, events=False, substates=False, doInit=False):
        self.currCmd = False
        self.doInit = doInit
        self.last = 0
        self.monitor = 60

        QThread.__init__(self, actor, name, timeout=15)
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

    def init(self, cmd, **kwargs):
        self._init(cmd, **kwargs)
        FSMDevice.init(self, cmd)

    def _loadCfg(self, cmd, mode=None):
        pass

    def _openComm(self, cmd):
        pass

    def _testComm(self, cmd):
        pass

    def _closeComm(self, cmd):
        pass

    def _init(self, cmd, **kwargs):
        pass

    def leaveCleanly(self, cmd):
        self.monitor = 0
        self._closeComm(cmd=cmd)

    def start(self, cmd=None, doInit=None, mode=None):
        doInit = self.doInit if doInit is None else doInit
        try:
            FSMDevice.start(self, cmd=cmd, doInit=doInit, mode=mode)
            self.generate(cmd=cmd, doFinish=False)
        finally:
            QThread.start(self)

    def stop(self, cmd):
        self.leaveCleanly(cmd=cmd)
        FSMDevice.stop(self, cmd=cmd)
        self.exit()

    def generate(self, cmd=None, doFinish=True):
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
        if self.exitASAP:
            raise SystemExit()

        if self.monitor and (time.time() - self.last) > self.monitor:
            cmd = self.actor.bcast if cmd is None else cmd
            try:
                self.generate(cmd)
            except Exception as e:
                cmd.fail('text=%s' % self.actor.strTraceback(e))
