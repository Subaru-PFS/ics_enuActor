from functools import partial


def threaded(func):
    def wrapper(self, *args, **kwargs):
        self.actor.controllers[self.name].putMsg(partial(func, self, *args, **kwargs))

    return wrapper


def loading(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0].cmd if hasattr(args[0], "cmd") else self.actor.bcast
        self.getStatus(cmd, doFinish=False)
        ok = func(self, *args, **kwargs)
        nextState = getattr(self.fsm, "%sOk" % func.__name__) if ok else getattr(self.fsm, "%sFailed" % func.__name__)
        nextState()

    return wrapper


def loading(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0].cmd if hasattr(args[0], "cmd") else self.actor.bcast
        self.getStatus(cmd, doFinish=False)

        if func(self, *args, **kwargs):
            self.fsm.loadDeviceOk()
        else:
            self.fsm.loadDeviceFailed()

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
        self.fsm.goBusy()
        self.getStatus(cmd, doFinish=False)

        ok = func(self, *args, **kwargs)
        self.fsm.goIdle() if ok else self.fsm.goFailed()
        return ok

    return wrapper
