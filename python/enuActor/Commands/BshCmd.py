#!/usr/bin/env python

import subprocess
import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types

from enuActor.utils.wrap import threaded
from enuActor.fysom import FysomError

class BshCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.name = "bsh"

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('bsh', 'ping', self.ping),
            ('bsh', 'status', self.status),
            ('bsh', 'init', self.initialise),
            ('bsh', '@(operation|simulation)', self.changeMode),
            ('bsh', 'config [<duty>] [<period>]', self.sendConfig),
            ('bia', '@(on|off) [@(force)]', self.biaSwitch),
            ('shutters', '@(open|close) [@(force)]', self.shutterSwitch),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu__bsh", (1, 1),
                                        keys.Key("duty", types.Float(), help="bia duty cycle (0..1"),
                                        keys.Key("period", types.Float(), help="bia period"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name))

    @threaded
    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.inform('version=%s' % subprocess.check_output(["git", "describe"]))
        cmd.finish("text='Present and (probably) well'")

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """

        try:
            self.controller.fsm.startInit(cmd=cmd)
        except FysomError as e:
            cmd.warn("text='%s  %s'" % (self.name.upper(),
                                        self.controller.formatException(e, sys.exc_info()[2])))

        self.status(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"

        try:
            self.controller.fsm.changeMode(cmd=cmd, mode=mode)

        except FysomError as e:
            cmd.warn("text='%s  %s'" % (self.name.upper(),
                                        self.controller.formatException(e, sys.exc_info()[2])))

        self.status(cmd)

    @threaded
    def sendConfig(self, cmd):
        """Update bia parameters """
        cmdKeys = cmd.cmd.keywords
        period, duty = None, None

        try:
            if "period" in cmdKeys:
                if 0 < cmdKeys["period"].values[0] < 65536:
                    period = int(cmdKeys["period"].values[0])
                else:
                    raise Exception("period not in range : %i=> %i" % (0, 65535))

            if "duty" in cmdKeys:
                if 0 < cmdKeys["duty"].values[0] < 256:
                    duty = int(cmdKeys["duty"].values[0])
                else:
                    raise Exception("duty not in range : %i => %i" % (0, 255))

            self.controller.sendBiaConfig(cmd, period, duty, doClose=True)
            cmd.finish()

        except Exception as e:
            cmd.fail("text='%s failed to send Bia Config %s'" % (self.name.upper(),
                                                                 self.controller.formatException(e, sys.exc_info()[2])))

    @threaded
    def biaSwitch(self, cmd):
        """Switch bia on/off"""
        cmdKeys = cmd.cmd.keywords

        cmdStr = "bia_on" if "on" in cmdKeys else "bia_off"
        doForce = True if "force" in cmdKeys else False

        self.controller.switch(cmd, cmdStr, doForce=doForce)

        self.status(cmd)

    @threaded
    def shutterSwitch(self, cmd):
        """Open/close shutters"""
        cmdKeys = cmd.cmd.keywords

        cmdStr = "shut_open" if "open" in cmdKeys else "shut_close"
        doForce = True if "force" in cmdKeys else False

        self.controller.switch(cmd, cmdStr, doForce)

        self.status(cmd)
