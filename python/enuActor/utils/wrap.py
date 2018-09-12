import time
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


def busy(func):
    def wrapper(self, *args, **kwargs):
        while self.isBusy:
            time.sleep(0.01)
        self.isBusy = True
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            raise
        finally:
            self.isBusy = False

    return wrapper
