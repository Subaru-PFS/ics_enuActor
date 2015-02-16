#!/usr/bin/env python

import sys
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr


class EnuCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('status', '', self.status),
            ('start', '[@(operation|simulation)]', self.start),
            ('@(off|load|busy|idle|SafeStop|fail)', '', self.set_state),
            ('init', '', self.init),
            ('ping', '', self.ping),
             ]

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Enu Actor: o/'")

    def init(self, cmd):
        self.actor.enu.initialise()

    def start(self, cmd):
        self.actor.enu.startUp()

    def set_state(self, cmd):
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
            status = self.actor.enu.getStatus()
            cmd.inform("text='{}'".format(status))
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))

