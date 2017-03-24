import sys
import traceback as tb
from functools import partial

from enuActor.fysom import FysomError


def formatException(e, traceback):
    """ Format the caught exception as a string

    :param e: caught exception
    :param traceback: exception traceback
    """

    def clean(string):
        return str(string).replace("'", "").replace('"', "")

    return "%s %s %s" % (clean(type(e)), clean(type(e)(*e.args)), clean(tb.format_tb(traceback, limit=1)[0]))


def threaded(func):
    def wrapper(self, *args, **kwargs):
        self.actor.controllers[self.name].putMsg(partial(func, self, *args, **kwargs))

    wrapper.__doc__ = func.__doc__
    wrapper.__repr__ = func.__repr__

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
            cmd.warn("text='%s  %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))
            return
        self.getStatus(cmd, doFinish=False)

        ok = func(self, *args, **kwargs)
        self.fsm.goIdle() if ok else self.fsm.goFailed()
        return ok

    wrapper.__doc__ = func.__doc__
    wrapper.__repr__ = func.__repr__

    return wrapper
