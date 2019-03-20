from functools import partial


def putMsg(func):
    def wrapper(self, cmd, *args, **kwargs):
        if self.actor.controllers[self.name].currCmd:
            raise RuntimeWarning('%s thread is busy' % self.name)

        self.actor.controllers[self.name].putMsg(partial(func, self, cmd, *args, **kwargs))

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
            self.actor.controllers[self.name].currCmd = cmd
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))
        finally:
            self.actor.controllers[self.name].currCmd = False

    return wrapper
