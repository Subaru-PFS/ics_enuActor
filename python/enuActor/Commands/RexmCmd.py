#!/usr/bin/env python


import sys

import opscore.protocols.keys as keys
from fysom import FysomError
from enuActor.utils.wrap import threaded


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
            ('rexm', '@(operation|simulation)', self.changeMode),
            ('rexm', 'init', self.initialise),
            ('rexm', '@(move) @(low|mid)', self.moveTo),
            ('rexm', 'abort', self.abort),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_rexm", (1, 1),
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
        cmd.finish("text='%s controller Present and (probably) well'" % self.name)

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise REXM, call fsm startInit event """

        try:
            self.controller.fsm.startInit(cmd=cmd)
        # That transition may not be allowed, see state machine
        except FysomError as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation call fsm changeMode event"""

        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"

        try:
            self.controller.fsm.changeMode(cmd=cmd, mode=mode)
        # That transition may not be allowed, see state machine
        except FysomError as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

    @threaded
    def moveTo(self, cmd):
        """ Move to low|mid resolution position """
        cmdKeys = cmd.cmd.keywords
        position = "low" if "low" in cmdKeys else "mid"

        self.controller.moveTo(cmd, position)

        self.controller.getStatus(cmd)

    def abort(self, cmd):
        """ Abort current motion """

        self.controller.abort(cmd)
        self.controller.getStatus(cmd)