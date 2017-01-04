#!/usr/bin/env python


import opscore.protocols.keys as keys
from enuActor.utils.wrap import threaded


class IisCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.name = "iis"
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('iis', 'status', self.status),
            ('iis', 'mode [@(operation|simulation)]', self.changeMode),
            ('iis', 'init', self.initialise),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_iis", (1, 1),
                                        )

    @threaded
    def status(self, cmd, doFinish=True):
        """Report iis"""
        cmd.inform('state=%s' % self.actor.controllers['iis'].fsm.current)
        cmd.inform('mode=%s' % self.actor.controllers['iis'].currMode)
        ender = cmd.finish if doFinish else cmd.inform
        ok, status = self.actor.controllers['iis'].getStatus(cmd)
        if ok:
            ender('iis=%s' % status)

    @threaded
    def changeMode(self, cmd, doFinish=True):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        self.actor.controllers['iis'].fsm.changeMode()

        if self.actor.controllers['iis'].changeMode(cmd, mode):
            self.status(cmd, doFinish)

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        if self.actor.controllers['iis'].initialise(cmd):
            self.actor.controllers['iis'].fsm.initOk()
            self.status(cmd)
        else:
            self.actor.controllers['iis'].fsm.initFailed()
