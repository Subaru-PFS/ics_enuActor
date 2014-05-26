#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr


class RexmCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('rexm', 'status', self.status),
            ('rexm', 'start', self.start),
            ('rexm', '@(simulated|operation)', self.set_mode),
            ('rexm', '@(off|load|busy|idle|SafeStop|fail|init)', self.set_state),
            ('rexm', 'stop',
             lambda x : self.actor.rexm.stop()),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("mcs_mcs", (1, 1),
                                        )

    def status(self, cmd):
        cmd.inform("text='{}'".format(self.actor.rexm.getStatus()))

    def start(self, cmd):
        self.actor.rexm.start_communication(cmd)

    def set_mode(self, cmd):
        mode = cmd.cmd.keywords[0].name
        self.actor.rexm.mode = mode

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        getattr(self.actor.rexm.fsm, state)()
        #self.status(cmd)

