#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr


class BiaCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('bia', 'status', self.status),
            ('bia', 'start', self.start),
            ('bia', '@(simulated|operation)', self.set_mode),
            ('bia', '@(on|off)', self.bia),
            ('bia', 'on <freq> <dur>', self.strobe),
            ('bia', '@(off|load|busy|idle|SafeStop|fail|init)', self.set_state),
            ('bia', 'stop',
             lambda x : self.actor.bia.stop()),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary(
                "bia_bia", (1, 1),
                keys.Key("freq", types.Float(), help="Frequency for strobe mode"),
                keys.Key("dur", types.Float(), help="Duration for strobe mode"),
                                        )

    def status(self, cmd):
        cmd.inform("text='{}'".format(self.actor.bia.getStatus()))

    def start(self, cmd):
        self.actor.bia.start_communication(cmd)

    def set_mode(self, cmd):
        mode = cmd.cmd.keywords[0].name
        self.actor.bia.mode = mode

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        getattr(self.actor.bia.fsm, state)()
        #self.status(cmd)

    def bia(self, cmd):
        transition = cmd.cmd.keywords[0].name
        self.actor.bia.putMsg(self.actor.bia.bia, transition)

    def strobe(self, cmd):
        strobe = [cmd.cmd.keywords["freq"].values[0], cmd.cmd.keywords["dur"].values[0]]
        self.actor.bia.putMsg(self.actor.bia.bia, "strobe", strobe)
