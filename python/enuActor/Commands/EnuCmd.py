#!/usr/bin/env python

import sys
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
from enuActor.MyFSM import FysomError

class EnuCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('status', '', self.status),
            ('start', '', self.start),
            ('@(off|load|busy|idle|SafeStop|fail)', '', self.set_state),
            ('init', '', self.init),
            ('ping', '', self.ping),
             ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_enu", (1, 1),
                                        )


    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Enu Actor: o/'")

    def init(self, cmd):
        """ Initialise Enu device

        """
        self.actor.enu.initialise()

    def start(self, cmd):
        """ Start and initialise Enu actor"""
        self.actor.enu.startUp()
        self.actor.enu.initialise()
        self.actor.enu.finish("start operation done successfully!")

    def set_state(self, cmd):
        """ Change current Enu state to BUSY, IDLE, LOADED, ...

        """
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.enu.fsm, state)()
        except AttributeError as e:
            cmd.error("text='Enu did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text='%s'" % e)

    def status(self, cmd):
        """Report camera status and actor version. """
        self.actor.sendVersionKey(cmd)
        try:
            self.actor.enu.inform("status:%s" % self.actor.enu.getStatus())
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))

