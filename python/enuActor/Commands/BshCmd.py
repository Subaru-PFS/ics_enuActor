#!/usr/bin/env python

import subprocess

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from wrap import threaded


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

    @threaded
    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.inform('version=%s' % subprocess.check_output(["git", "describe"]))
        cmd.finish("text='Present and (probably) well'")

    @threaded
    def status(self, cmd, doFinish=True):
        """Report state, mode, position"""
        cmd.inform('state=%s' % self.actor.controllers['bsh'].fsm.current)
        cmd.inform('mode=%s' % self.actor.controllers['bsh'].currMode)
        if self.actor.controllers['bsh'].getStatus(cmd):
            ender = cmd.finish if doFinish else cmd.inform
            cmd.inform('shutters=%s' % self.actor.controllers['bsh'].shState)
            cmd.inform('biaConfig=%.1f,%.1f' % (
                self.actor.controllers['bsh'].biaPeriod, self.actor.controllers['bsh'].biaDuty))
            ender('bia=%s' % self.actor.controllers['bsh'].biaState)
        else:
            self.actor.controllers['bsh'].fsm.cmdFailed()

    @threaded
    def initialise(self, cmd):
        if self.actor.controllers['bsh'].initialise(cmd):
            self.actor.controllers['bsh'].fsm.initOk()
            self.status(cmd)
        else:
            self.actor.controllers['bsh'].fsm.initFailed()

    @threaded
    def changeMode(self, cmd, doFinish=True):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        self.actor.controllers['bsh'].fsm.changeMode()

        if self.actor.controllers['bsh'].changeMode(cmd, mode):
            self.status(cmd, doFinish)

    @threaded
    def sendConfig(self, cmd):
        cmdKeys = cmd.cmd.keywords

        duty = 1024 * cmdKeys["duty"].values[0] if "duty" in cmdKeys else None
        period = cmdKeys["period"].values[0] if "period" in cmdKeys else None
        list_param = [("duty", duty, (0., 1.)), ("period", period, (1, 1e6))]
        for param, val, (min, max) in list_param:
            if val is not None:
                if min <= val <= max:
                    if not self.actor.controllers['bsh'].errorChecker(cmd, "set_%s%i" % (param, val)):
                        self.actor.controllers['bsh'].fsm.cmdFailed()
                        return
                else:
                    cmd.warn("text='%s : %.1f is not in range (%i, %i) '" % (param, val, min, max))
        self.status(cmd)

    @threaded
    def biaSwitch(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "on" if "on" in cmdKeys else "off"
        self.actor.controllers['bsh'].fsm.getBusy()
        if self.actor.controllers['bsh'].switch(cmd, "bia", mode):
            self.actor.controllers['bsh'].fsm.getIdle()
            self.status(cmd)
        else:
            self.actor.controllers['bsh'].fsm.cmdFailed()

    @threaded
    def shutterSwitch(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "open" if "open" in cmdKeys else "close"
        self.actor.controllers['bsh'].fsm.getBusy()
        if self.actor.controllers['bsh'].switch(cmd, "shut", mode):
            self.actor.controllers['bsh'].fsm.getIdle()
            self.status(cmd)
        else:
            self.actor.controllers['bsh'].fsm.cmdFailed()
