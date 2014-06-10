#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
import sys
from enuActor.Devices.Error import CommErr, DeviceErr
from enuActor.MyFSM import FysomError


class SlitCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('slit', 'status', self.status), # TODO
            ('slit', 'start', self.start), # TODO
            ('slit', '<cmd>', self.command), # TODO
            ('slit', '@(simulated|operation)', self.set_mode),# TODO
            ('slit', 'GetHome', self.slit),# TODO
            ('slit', 'GoHome', self.slit),# TODO
            #('slit', 'SetHome <X> <Y> <Z> <U> <V> <W>', self.slit),# TODO
            #('slit', 'SetHome CURRENT', self.slit),# TODO
            #('slit', 'MoveTo <X> <Y> <Z> <U> <V> <W> @(absolute|relative)',
                #self.slit),# TODO
            #('slit', 'dither axis <X> <Y> <Z>', self.slit),# TODO
            #('slit', 'dither axis', self.slit),# TODO
            #('slit', 'focus axis <X> <Y> <Z>', self.slit),# TODO
            #('slit', 'focus axis', self.slit),# TODO
            #('slit', 'dither', self.slit),# TODO
            #('slit', '<dither>', self.slit),# TODO
            #('slit', '<magnification>', self.slit),# TODO
            #('slit', 'focus', self.slit),# TODO
            #('slit', '<focus>', self.slit),# TODO
            ('slit', '@(off|load|busy|idle|SafeStop|fail|init)',
                self.set_state),# TODO
            ('slit', 'stop',
             lambda x : self.actor.slit.stop()),# TODO
                ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("slit_slit", (1, 1),
                #keys.Key("cmd", types.Float(), help="Command ascii"),
                #keys.Key("X", types.Float(), help="X coordinate"),
                #keys.Key("Y", types.Float(), help="Y coordinate"),
                #keys.Key("Z", types.Float(), help="Z coordinate"),
                #keys.Key("U", types.Float(), help="U coordinate"),
                #keys.Key("V", types.Float(), help="V coordinate"),
                #keys.Key("W", types.Float(), help="W coordinate"),
                #keys.Key("dither", types.Float(),
                    #help="Number of pixel along dither axis"),
                #keys.Key("focus", types.Float(),
                    #help="Number of pixel along focus axis"),
                keys.Key("magnification", types.Float(),
                    help="magnification value"),
                                        )

    def status(self, cmd):
        try:
            cmd.inform("text='{}'".format(self.actor.slit.getStatus()))
        except AttributeError as e:
            cmd.error("text='slit did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: %s'" % sys.exc_info()[0])

    def start(self, cmd):
        try:
            self.actor.slit.start_communication(cmd)
        except CommErr as e: # ISSUE : I cannot catch timeout error
            cmd.error("text='%s'" % e)
        except FysomError as e:
            cmd.error("text='Can't start when device is in %s state'" %
            self.actor.slit.fsm.current)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))
        else:
            cmd.inform("text='slit started successfully!'")

    def command(self, cmd):
        """Opens a terminal to communicate directly with device"""
        self.actor.slit.send("%s\r\n" %
        cmd.cmd.keywords["cmd"].values[0])

    def set_mode(self, cmd):
        mode = cmd.cmd.keywords[0].name
        self.actor.slit.mode = mode

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.slit.fsm, state)()
        except AttributeError as e:
            cmd.error("text='slit did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text= Can't go to this state: %s -x-> %s'" %
            (self.actor.slit.fsm.current, state.upper()))

    def slit(self, cmd):
        """Not Implemented Yet"""
        pass
