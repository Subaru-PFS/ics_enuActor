import time
from functools import partial, wraps

from actorcore.QThread import QThread
from enuActor.utils import wait


def putMsg(func):
    @wraps(func)
    def wrapper(self, cmd, *args, **kwargs):
        self.putMsg(partial(func, self, cmd, *args, **kwargs))

    return wrapper


def threaded(func):
    @wraps(func)
    @putMsg
    def wrapper(self, cmd, *args, **kwargs):
        try:
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))

    return wrapper


class SyncCmd(object):
    def __init__(self, actor, cmdList):
        """This combine QThread and FSMDevice.

        :param actor: enuActor.
        :param cmdList: command list to be processed in parallel.
        """
        self.cmdThd = [CmdThread(actor, cmdStr=cmdStr) for cmdStr in cmdList]

    def process(self, cmd):
        """Call commands and synchronise, exit threads.

        :param cmd: current command.
        """
        self.call(cmd)
        self.sync()
        self.exit()

    def call(self, cmd):
        """Each thread call its command string.

        :param cmd: current command.
        """
        for th in self.cmdThd:
            th.call(cmd)

    def sync(self):
        """Wait for each command to be finished."""
        while None in [th.cmdVar for th in self.cmdThd]:
            wait(secs=1)

    def exit(self):
        """Exit all threads."""
        for ti in self.cmdThd:
            ti.exit()


class CmdThread(QThread):
    def __init__(self, actor, cmdStr):
        """Dedicated command thread.

        :param actor: enuActor.
        :param cmdStr: Command string to be sent
        """
        self.cmdVar = None
        self.cmdStr = cmdStr
        QThread.__init__(self, actor, str(time.time()))
        QThread.start(self)

    @threaded
    def call(self, cmd):
        """Call self.cmdStr.

        :param cmd: current command.
        """
        cmd.inform(f'text="calling {self.cmdStr}"')
        cmdVar = self.actor.cmdr.call(actor=self.actor.name, cmdStr=self.cmdStr, forUserCmd=cmd, timeLim=150)

        if cmdVar.didFail:
            cmd.warn(cmdVar.replyList[-1].keywords.canonical(delimiter=';'))
        else:
            cmd.inform(f'text="{self.cmdStr} OK"')

        self.cmdVar = cmdVar
