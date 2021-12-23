#!/usr/bin/env python
from importlib import reload

from ics.utils.sps.lamps.commands import LampsCmd

reload(LampsCmd)


class IisCmd(LampsCmd.LampsCmd):
    def __init__(self, actor):
        LampsCmd.LampsCmd.__init__(self, actor, name='iis')

        # since iis is a subsystem inside enu, commands needs to be rephrased.
        self.vocab = [
            ('iis', 'status', self.status),
            ('iis', '[<on>] [<warmingTime>] [force]', self.warmup),
            ('iis', '<off>', self.switchOff),
            ('iis', 'stop', self.stop),
            ('iis', 'start [@(operation|simulation)]', self.start),

            ('iis', 'abort', self.abort),
            ('iis', 'prepare [<halogen>] [<argon>] [<neon>] [<krypton>] [<xenon>] [<hgar>] [<hgcd>]', self.prepare),
            ('iis', 'waitForReadySignal', self.waitForReadySignal),
            ('iis', 'go [<delay>]', self.timedGoSequence),
            ('iis', 'go noWait [<delay>]', self.goNoWait),
        ]
