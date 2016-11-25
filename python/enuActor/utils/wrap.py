from functools import partial
from enuActor.fysom import FysomError
import sys

def threaded(func):
    def wrapper(self, *args, **kwargs):
        self.actor.controllers[self.name].putMsg(partial(func, self, *args, **kwargs))

    return wrapper


def loading(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0].cmd if hasattr(args[0], "cmd") else self.actor.bcast
        self.getStatus(cmd, doFinish=False)

        if func(self, *args, **kwargs):
            self.fsm.loadDeviceOk()
        else:
            self.fsm.loadDeviceFailed()
        self.getStatus(cmd, doFinish=False)

    return wrapper


def initialising(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0].cmd if hasattr(args[0], "cmd") else self.actor.bcast
        self.getStatus(cmd, doFinish=False)

        if func(self, *args, **kwargs):
            self.fsm.initialiseOk()
        else:
            self.fsm.initialiseFailed()

    return wrapper


def busy(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0]
        try:
            self.fsm.goBusy()
        except FysomError as e:
            cmd.warn("text='%s  %s'" % (self.name.upper(),
                                        self.formatException(e, sys.exc_info()[2])))
            return
        self.getStatus(cmd, doFinish=False)

        ok = func(self, *args, **kwargs)
        self.fsm.goIdle() if ok else self.fsm.goFailed()
        return ok

    return wrapper
