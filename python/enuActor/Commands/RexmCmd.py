#!/usr/bin/env python


import opscore.protocols.keys as keys
from wrap import threaded


class RexmCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.name = "rexm"
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('rexm', 'status', self.status),
            ('rexm', 'mode [@(operation|simulation)]', self.changeMode),
            ('rexm', 'init', self.initialise),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_rexm", (1, 1),
                                        )

    @threaded
    def status(self, cmd, doFinish=True):
        """Report rexm"""
        cmd.inform('state=%s' % self.actor.controllers['rexm'].fsm.current)
        cmd.inform('mode=%s' % self.actor.controllers['rexm'].currMode)
        ender = cmd.finish if doFinish else cmd.inform
        if self.actor.controllers['rexm'].getPosition(cmd):
            ender('position=%s' % self.actor.controllers['rexm'].currPos)
        else:
            self.actor.controllers['rexm'].fsm.cmdFailed()

    @threaded
    def changeMode(self, cmd, doFinish=True):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        self.actor.controllers['rexm'].fsm.changeMode()

        if self.actor.controllers['rexm'].changeMode(cmd, mode):
            self.status(cmd, doFinish)

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        if self.actor.controllers['rexm'].initialise(cmd):
            self.actor.controllers['rexm'].fsm.initOk()
            self.status(cmd)
        else:
            self.actor.controllers['rexm'].fsm.initFailed()
