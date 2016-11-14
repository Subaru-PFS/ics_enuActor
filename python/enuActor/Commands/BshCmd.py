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
            ('bsh', 'mode [@(operation|simulation)]', self.changeMode),
            ('bsh', 'config [<duty>] [<period>]', self.sendConfig),
            ('bia', '[@(on|off)]', self.biaSwitch),
            ('shutters', '[@(open|close)]', self.shutterSwitch),

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
        ok, ret = self.controller.getStatus(cmd)
        ender = cmd.inform if ok else cmd.warn
        for keyword, status in ret:
            ender("%s=%s" % (keyword, status))
        cmd.finish()

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        try:
            self.controller.fsm.startInit(cmd=cmd)
        except Exception as e:
            cmd.warn('text="failed to initialise for %s: %s"' % (self.name, e))

        self.status(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        try:
            self.controller.fsm.changeMode(cmd=cmd, mode=mode)
        except Exception as e:
            cmd.warn('text="failed to change mode for %s: %s"' % (self.name, e))

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

        self.controller.biaConfig(cmd, period, duty, doClose=True)

    @threaded
    def biaSwitch(self, cmd):
        """Switch bia on/off"""
        cmdKeys = cmd.cmd.keywords
        cmdStr = "bia_on" if "on" in cmdKeys else "bia_off"

        ok, ret = self.controller.switch(cmd, cmdStr)
        if not ok:
            cmd.warn("text='%s'" % ret)
        self.status(cmd)

    @threaded
    def shutterSwitch(self, cmd):
        """Open/close shutters"""
        cmdKeys = cmd.cmd.keywords
        cmdStr = "shut_open" if "open" in cmdKeys else "shut_close"

        ok, ret = self.controller.switch(cmd, cmdStr)
        if not ok:
            cmd.warn("text='%s'" % ret)
        self.status(cmd)
