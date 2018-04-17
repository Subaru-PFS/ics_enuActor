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