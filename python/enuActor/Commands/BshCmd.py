#!/usr/bin/env python

import subprocess

import opscore.protocols.keys as keys
import opscore.protocols.types as types

from enuActor.Controllers.wrap import threaded


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

        self.controller.fsm.startInit(cmd=cmd)

        self.status(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"

        self.controller.fsm.changeMode(cmd=cmd, mode=mode)

        self.status(cmd)

    @threaded
    def sendConfig(self, cmd):
        """Update bia parameters """
        cmdKeys = cmd.cmd.keywords
        period, duty = None, None

        if "period" in cmdKeys:
            if not 1e-1 <= cmdKeys["period"].values[0] < 1e6:
                cmd.warn("text='period not in range : %.1f => %.1f'" % (1e-1, 1e6))
            else:
                period = cmdKeys["period"].values[0]

        if "duty" in cmdKeys:
            if not 0 <= cmdKeys["duty"].values[0] < 512:
                cmd.warn("text='duty not in range : %.1f => %.1f'" % (0, 512))
            else:
                duty = cmdKeys["duty"].values[0]

        try:
            self.controller.biaConfig(cmd, period, duty, doClose=True)
            cmd.finish()
        except Exception as e:
             cmd.fail("text='%s biaConfig failed : %s'" % (self.name, e))

    @threaded
    def biaSwitch(self, cmd):
        """Switch bia on/off"""
        cmdKeys = cmd.cmd.keywords
        cmdStr = "bia_on" if "on" in cmdKeys else "bia_off"

        self.controller.switch(cmd, cmdStr)

        self.status(cmd)

    @threaded
    def shutterSwitch(self, cmd):
        """Open/close shutters"""
        cmdKeys = cmd.cmd.keywords
        cmdStr = "shut_open" if "open" in cmdKeys else "shut_close"

        self.controller.switch(cmd, cmdStr)

        self.status(cmd)
