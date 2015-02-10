#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
import sys
from enuActor.Devices.Error import CommErr, DeviceErr
from enuActor.MyFSM import FysomError


class ShutterCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('shutter', 'status', self.status),
            ('shutter', '<cmd>', self.command),
            ('shutter', '@(simulated|operation)', self.set_mode),
            ('shutter', '@(open|close|reset) @(red|blue)', self.shutter),
            ('shutter', '@(open|close|reset)', self.shutter),
            ('shutter', '@(off|load|busy|idle|SafeStop|fail)', self.set_state),
            ('shutter', 'init', self.init),
            ('shutter', 'stop',
             lambda x : self.actor.shutter.stop()),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("shutter_shutter", (1, 1),
                keys.Key("cmd", types.String(), help="Command ascii"),
                                        )

    def init(self, cmd):
        cmd.inform("text='test'")
        self.actor.shutter.initialise()

    def status(self, cmd):
        try:
            cmd.inform("text='{}'".format(self.actor.shutter.getStatus()))
        except AttributeError as e:
            cmd.error("text='Shutter did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: %s'" % sys.exc_info()[0])
    def command(self, cmd):
        """Opens a terminal to communicate directly with device"""
        self.actor.shutter.send("%s\r\n" %
        cmd.cmd.keywords["cmd"].values[0])

    def set_mode(self, cmd):
        mode = cmd.cmd.keywords[0].name
        try:
            self.actor.shutter.change_mode(mode)
        except CommErr as e:
            cmd.error("text='%s'" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))
        else:
            cmd.inform("text='Shutter mode %s enabled'" % mode)

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.shutter.fsm, state)()
        except AttributeError as e:
            cmd.error("text='Shutter did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text= Can't go to this state: %s -x-> %s'" %
            (self.actor.shutter.fsm.current, state.upper()))

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
        try:
            self.actor.shutter.putMsg(self.actor.shutter.shutter, transition)
        except AttributeError as e:
            cmd.error("text='Shutter did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))


