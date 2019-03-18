import time

from actorcore.FSM import FSMDev
from actorcore.QThread import QThread


class FSMThread(FSMDev, QThread):
    def __init__(self, actor, name, events=False, substates=False, doInit=False):
        self.currCmd = False
        self.doInit = doInit
        self.last = 0
        self.monitor = 60

        QThread.__init__(self, actor, name, timeout=2)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

    def start(self, cmd=None, doInit=None, mode=None):
        doInit = self.doInit if doInit is None else doInit
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()

        if self.monitor and (time.time() - self.last) > self.monitor:
            self.getStatus(cmd=self.actor.bcast)
            self.last = time.time()
