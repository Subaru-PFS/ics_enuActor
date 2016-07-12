#!/usr/bin/env python


import opscore.protocols.keys as keys
from wrap import threaded


class TempsCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.name = "temps"
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('temps', 'status', self.status),
            ('temps', 'mode [@(operation|simulation)]', self.changeMode),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_temps", (1, 1),
                                        )

    @threaded
    def status(self, cmd, doFinish=True):
        """Report temps"""
        cmd.inform('state=%s' % self.actor.controllers['temps'].fsm.current)
        cmd.inform('mode=%s' % self.actor.controllers['temps'].currMode)
        ender = cmd.finish if doFinish else cmd.inform
        ok, temps = self.actor.controllers['temps'].fetchTemps(cmd)
        if ok:
            ender('temps=%s' % temps)


    @threaded
    def changeMode(self, cmd, doFinish=True):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        self.actor.controllers['temps'].fsm.changeMode()

        if self.actor.controllers['temps'].changeMode(cmd, mode):
            self.status(cmd, doFinish)
