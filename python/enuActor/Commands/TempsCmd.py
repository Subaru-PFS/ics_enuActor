#!/usr/bin/env python


import subprocess

import opscore.protocols.keys as keys

from enuActor.utils.wrap import threaded


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
            ('temps', '@(operation|simulation)', self.changeMode),
            ('temps', 'init', self.initialise),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_temps", (1, 1),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name))

    @threaded
    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.inform('version=%s' % subprocess.check_output(["git", "describe"]))
        cmd.finish("text='Present and (probably) well'")

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        self.controller.fsm.startInit(cmd=cmd)

        self.status(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"

        self.controller.fsm.changeMode(cmd=cmd, mode=mode)

        self.status(cmd)
