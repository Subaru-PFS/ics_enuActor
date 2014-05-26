#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr


class EnuCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
             ]

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """
        self.actor.sendVersionKey(cmd)
        cmd.inform("'text='Present!")
        #cmd.inform('text="thread isAlive: %s"' % self.actor.shutter.isAlive())
        #cmd.inform('text="%s"'%self.actor.shutter.status())
        cmd.finish()

