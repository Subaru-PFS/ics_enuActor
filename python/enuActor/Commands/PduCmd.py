#!/usr/bin/env python


import opscore.protocols.keys as keys
from enuActor.utils.wrap import threaded

class PduCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.name = "pdu"
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('pdu', 'status', self.status),
            ('pdu', 'mode [@(operation|simulation)]', self.changeMode),
            ('pdu', 'init', self.initialise),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_pdu", (1, 1),
                                        )

    @threaded
    def status(self, cmd, doFinish=True):
        """Report pdu"""
        cmd.inform('state=%s' % self.actor.controllers['pdu'].fsm.current)
        cmd.inform('mode=%s' % self.actor.controllers['pdu'].currMode)
        ender = cmd.finish if doFinish else cmd.inform
        ok, status = self.actor.controllers['pdu'].getStatus(cmd)
        if ok:
            ender('pdu=%s' % status)

    @threaded
    def changeMode(self, cmd, doFinish=True):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        self.actor.controllers['pdu'].fsm.changeMode()

        if self.actor.controllers['pdu'].changeMode(cmd, mode):
            self.status(cmd, doFinish)

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        if self.actor.controllers['pdu'].initialise(cmd):
            self.actor.controllers['pdu'].fsm.initOk()
            self.status(cmd)
        else:
            self.actor.controllers['pdu'].fsm.initFailed()
