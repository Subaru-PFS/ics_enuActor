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

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_iis", (1, 1),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name))


    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        self.controller.getStatus(cmd)
