from functools import partial


def threaded(func):
    @putMsg
    def wrapper(self, cmd, *args, **kwargs):
        try:
            self.actor.controllers[self.name].currCmd = cmd
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))
        finally:
            self.actor.controllers[self.name].currCmd = False

    return wrapper


def isStatus(cmd):
    return ' status' in cmd.rawCmd


def putMsg(func):
    def wrapper(self, cmd, *args, **kwargs):
        if self.actor.controllers[self.name].currCmd:
            if not isStatus(cmd) and not isStatus(self.actor.controllers[self.name].currCmd):
                raise RuntimeWarning('%s thread is busy' % self.name)

        self.actor.controllers[self.name].putMsg(partial(func, self, cmd, *args, **kwargs))

    return wrapper
