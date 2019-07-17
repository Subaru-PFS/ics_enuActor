import time
from functools import partial

from actorcore.QThread import QThread


def putMsg(func):
    def wrapper(self, cmd, *args, **kwargs):
        if self.controller.currCmd:
            raise RuntimeWarning('%s thread is busy' % self.controller.name)

        self.controller.putMsg(partial(func, self, cmd, *args, **kwargs))

    return wrapper


def threaded(func):
    @putMsg
    def wrapper(self, cmd, *args, **kwargs):
        try:
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))

    return wrapper


def blocking(func):
    @putMsg
    def wrapper(self, cmd, *args, **kwargs):
        try:
            self.controller.currCmd = cmd
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))
        finally:
            self.controller.currCmd = False

    return wrapper


def putMsg2(func):
    def wrapper(self, cmd, *args, **kwargs):
        thr = QThread(self.actor, str(time.time()))
        thr.start()
        thr.putMsg(partial(func, self, cmd, *args, **kwargs))
        thr.exitASAP = True

    return wrapper


def singleShot(func):
    @putMsg2
    def wrapper(self, cmd, *args, **kwargs):
        try:
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))

    return wrapper
