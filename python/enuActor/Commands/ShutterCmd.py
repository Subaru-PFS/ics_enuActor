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
            ('shutter', 'start [@(operation|simulation)]', self.set_mode),
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
        """ Initialise SHUTTER device

        """
        self.actor.shutter.initialise()

    def status(self, cmd):
        """ Get status and position of SHUTTER device

        """
        try:
            status = self.actor.shutter.getStatus()
            self.actor.shutter.finish('status = %s' % status)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))

    def command(self, cmd):
        """ Opens a terminal to communicate directly with device"""
        self.actor.shutter.send("%s\r\n" %
        cmd.cmd.keywords["cmd"].values[0])

    def set_mode(self, cmd):
        """ Start/Restart SHUTTER device in operation/simulation mode (default operation)

        """
        name = cmd.cmd.keywords[-1].name
        if name.lower() in ['start','operation']:
            mode = 'operation'
        elif name.lower() == 'simulation':
            mode = 'simulated'
        else:
            cmd.error("text='unknow operation %s'" % name)

        try:
            self.actor.shutter.change_mode(mode)
        except CommErr as e:
            self.actor.shutter.error("text='%s'" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))
        else:
            self.actor.shutter.finish('started/restarted well!')

    def set_state(self, cmd):
        """ Change current SHUTTER state to BUSY, IDLE, LOADED, ...

        """
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.shutter.fsm, state)()
        except AttributeError as e:
            cmd.error("text='Shutter did not start well. details: %s" % e)
        except FysomError as e:
            self.actor.shutter.error("text='%s'" % e)

    def shutter(self, cmd):
        """ Open/Close/Reset shutter blue/red/all

        """
        transition = cmd.cmd.keywords[0].name
        if(len(cmd.cmd.keywords)==2):
            shutter_id = cmd.cmd.keywords[1].name
        elif( len(cmd.cmd.keywords)==1):
            shutter_id = 'all'
        try:
            self.actor.shutter.putMsg(self.actor.shutter.shutter, transition)
        except AttributeError as e:
            cmd.error("text='Shutter did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))


