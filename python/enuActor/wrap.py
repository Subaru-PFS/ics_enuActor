from functools import partial


def threaded(func):
    def wrapper(self, *args, **kwargs):
        self.actor.controllers[self.name].putMsg(partial(func, self, *args, **kwargs))

    return wrapper


def safeCheck(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0].cmd if hasattr(args[0], "cmd") else self.actor.bcast
        ok, ret = self.getStatus()
        ender = cmd.inform if ok else cmd.warn
        ender("%s=%s" % (self.name, ret))
        ok, ret = func(self, *args, **kwargs)
        ender = cmd.inform if ok else cmd.warn
        ender("text='%s'" % ret)

        nextState = getattr(args[0].fsm, "%sOk" % func.__name__) if ok else getattr(args[0].fsm,
                                                                                    "%sFailed" % func.__name__)
        nextState()

    return wrapper


def busy(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0]
        self.fsm.goBusy()
        ok, ret = self.getStatus()
        ender = cmd.inform if ok else cmd.warn
        ender("%s=%s" % (self.name, ret))
        ok, ret = func(self, *args, **kwargs)
        self.fsm.goIdle()
        return ok, ret

    return wrapper

def shutdown(func):
    def wrapper(self, *args, **kwargs):
        cmd = args[0]
        if self.fsm.current == "IDLE":
            self.fsm.goBusy()

        ok, ret = self.getStatus()
        ender = cmd.inform if ok else cmd.warn
        ender("%s=%s" % (self.name, ret))
        ok, ret = func(self, *args, **kwargs)
        self.fsm.goIdle()
        return ok, ret

    return wrapper