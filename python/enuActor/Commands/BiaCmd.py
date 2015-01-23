#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
import sys
from enuActor.Devices.Error import CommErr, DeviceErr
from enuActor.MyFSM import FysomError

class BiaCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('bia', 'status', self.status),
            ('bia', '@(simulated|operation)', self.set_mode),
            ('bia', '@(on|off)', self.bia),
            ('bia', 'on <int>', self.bia),
            ('bia', 'on strobe <int>', self.strobe_int),
            ('bia', 'on strobe <freq> <dur>', self.strobe_freq_dur),
            ('bia', 'on strobe <freq> <dur> <int>', self.strobe_freq_dur_int),
            ('bia', 'on strobe', self.strobeByDefault),
            ('bia', '@(off|load|busy|idle|SafeStop|fail)', self.set_state),
            ('bia', 'init', self.init),
            ('bia', 'SetConfig <freq> <dur> <int>', self.setconfig),
            ('bia', 'stop',
             lambda x : self.actor.bia.stop()),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary(
                "bia_bia", (1, 1),
                keys.Key("freq", types.Int(), help="Frequency for strobe mode"),
                keys.Key("dur", types.Int(), help="Duration for strobe mode"),
                keys.Key("int", types.Int(), help="Intensity of light"),
                                        )

    def init(self, cmd):
        self.actor.bia.initialise()

    def status(self, cmd):
        try:
            status = self.actor.bia.getStatus()
            cmd.inform("text='{}'".format(status))
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: %s'" % sys.exc_info()[0])

    def set_mode(self, cmd):
        mode = cmd.cmd.keywords[0].name
        try:
            self.actor.bia.change_mode(mode)
        except CommErr as e:
            cmd.error("text='%s'" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))
        else:
            cmd.inform("text='Bia mode %s enabled'" % mode)


        cmd.inform("text='Bia mode %s enabled'" % mode)

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.bia.fsm, state)()
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text='%s'" % e)

    def bia(self, cmd):
        transition = cmd.cmd.keywords[0].name
        try:
            self.actor.bia.putMsg(self.actor.bia.bia, transition)
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))

    def strobe_int(self, cmd):
        strobe = [
                cmd.cmd.keywords["freq"].values[0],
                cmd.cmd.keywords["dur"].values[0]
                ]
        try:
            self.actor.bia.putMsg(self.actor.bia.bia, "strobe", strobe)
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                sys.exc_info()[0],
                sys.exc_info()[1]))

    def strobe_freq_dur(self, cmd):
        strobe = [
                cmd.cmd.keywords["freq"].values[0],
                cmd.cmd.keywords["dur"].values[0]
                ]
        try:
            self.actor.bia.putMsg(self.actor.bia.bia, "strobe", strobe)
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                sys.exc_info()[0],
                sys.exc_info()[1]))

    def strobe_freq_dur_int(self, cmd):
        strobe = [
                cmd.cmd.keywords["freq"].values[0],
                cmd.cmd.keywords["dur"].values[0],
                cmd.cmd.keywords["int"].values[0]
                ]
        try:
            self.actor.bia.putMsg(self.actor.bia.bia, "strobe", strobe)
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                sys.exc_info()[0],
                sys.exc_info()[1]))

    def strobeByDefault(self, cmd):
        try:
            self.actor.bia.putMsg(self.actor.bia.bia, "strobe")
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                sys.exc_info()[0],
                sys.exc_info()[1]))

    def setconfig(self, cmd):
        freq = cmd.cmd.keywords["freq"].values[0]
        dur = cmd.cmd.keywords["dur"].values[0]
        try:
            self.actor.bia.putMsg(self.actor.bia.setConfig, freq=freq, dur=dur)
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                sys.exc_info()[0],
                sys.exc_info()[1]))

