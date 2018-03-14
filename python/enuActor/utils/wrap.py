import sys

from fysom import FysomError
from functools import partial


def threaded(func):
    @putMsg
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            cmd = args[0]
            cmd.fail('text=%s' % self.actor.strTraceback(e))

    return wrapper


def putMsg(func):
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

    wrapper.__doc__ = func.__doc__
    wrapper.__repr__ = func.__repr__

    return wrapper


def initialising(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0].cmd if hasattr(args[0], "cmd") else self.actor.bcast
        self.getStatus(cmd, doFinish=False)

        if func(self, *args, **kwargs):
            self.fsm.initialiseOk()
        else:
            self.fsm.initialiseFailed()

    wrapper.__doc__ = func.__doc__
    wrapper.__repr__ = func.__repr__

    return wrapper


def busy(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0]
        try:
            self.fsm.goBusy()
        except FysomError as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            return
        self.getStatus(cmd, doFinish=False)

        ok = func(self, *args, **kwargs)
        self.fsm.goIdle() if ok else self.fsm.goFailed()
        return ok

    wrapper.__doc__ = func.__doc__
    wrapper.__repr__ = func.__repr__

    return wrapper
