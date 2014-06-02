#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr


class ShutterCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('shutter', 'status', self.status),
            ('shutter', 'start', self.start),
            ('shutter', '<cmd>', self.command),
            ('shutter', '@(simulated|operation)', self.set_mode),
            ('shutter', '@(open|close|reset) @(red|blue)', self.shutter),
            ('shutter', '@(open|close|reset)', self.shutter),
            ('shutter', '@(off|load|busy|idle|SafeStop|fail|init)', self.set_state),
            ('shutter', 'stop',
             lambda x : self.actor.shutter.stop()),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("shutter_shutter", (1, 1),
                keys.Key("cmd", types.String(), help="Command ascii"),
                                        )

    def status(self, cmd):
        cmd.inform("text='{}'".format(self.actor.shutter.getStatus()))

    def start(self, cmd):
        self.actor.shutter.start_communication(cmd)

    def command(self, cmd):
        """Opens a terminal to communicate directly with device"""
        self.actor.shutter.send("%s\r\n" %
        cmd.cmd.keywords["cmd"].values[0])

    def set_mode(self, cmd):
        mode = cmd.cmd.keywords[0].name
        self.actor.shutter.mode = mode

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        getattr(self.actor.shutter.fsm, state)()
        #self.status(cmd)

    def shutter(self, cmd):
        """Parse shutter command and arguments
        :cmd: open or close shutter red or blue or both if no args
        """
        transition = cmd.cmd.keywords[0].name
        if(len(cmd.cmd.keywords)==2):
            shutter_id = cmd.cmd.keywords[1].name
        elif( len(cmd.cmd.keywords)==1):
            shutter_id = 'all'
        else:
            raise ValueError("Number of args exceed")
        self.actor.shutter.putMsg(self.actor.shutter.shutter, transition)
        #self.actor.shutter.queue.put({
        #'function': self.actor.shutter.shutter,
        #'args': transition,
        #'cmd': cmd})


