#!/usr/bin/env python

import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types

from fysom import FysomError
from enuActor.utils.wrap import threaded, formatException


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
            ('bsh', '<raw>', self.rawCommand),
            ('bia', '@(on|off)', self.biaSwitch),
            ('bia', '@(strobe) @(on|off)', self.biaStrobe),
            ('bia', 'config [<duty>] [<period>]', self.sendConfig),
            ('shutters', '@(open|close) [blue|red]', self.shutterSwitch),
            ('shutters', '@(expose) <exptime> [blue|red]', self.shutterExpose),
            ('shutters', 'abort', self.abort),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu__bsh", (1, 1),
                                        keys.Key("duty", types.Float(), help="bia duty cycle (0..255)"),
                                        keys.Key("period", types.Float(), help="bia period"),
                                        keys.Key("raw", types.String(), help="raw command"),
                                        keys.Key("exptime", types.Float(), help="exposure time"),

                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name))

    @threaded
    def ping(self, cmd):
        """Query the controller for liveness/happiness."""

        cmd.finish("text='%s controller Present and (probably) well'" % self.name)

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise BSH, call fsm startInit event """

        try:
            self.controller.fsm.startInit(cmd=cmd)
        # That transition may not be allowed, see state machine
        except FysomError as e:
            cmd.warn("text='%s  %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))

        self.controller.getStatus(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation call fsm changeMode event"""

        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"

        try:
            self.controller.fsm.changeMode(cmd=cmd, mode=mode)
        # That transition may not be allowed, see state machine
        except FysomError as e:
            cmd.warn("text='%s  %s'" % (self.name.upper(), formatException(e, sys.exc_info()[2])))

        self.controller.getStatus(cmd)

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

            self.controller.setBiaConfig(cmd, period, duty, doClose=True)
            cmd.finish()

        except Exception as e:
            cmd.fail("text='%s failed to send Bia Config %s'" % (self.name.upper(),
                                                                 formatException(e, sys.exc_info()[2])))

    @threaded
    def biaStrobe(self, cmd):
        """Activate|desactivate bia strobe mode  """
        cmdKeys = cmd.cmd.keywords
        state = "off" if "off" in cmdKeys else "on"

        try:
            self.controller.setBiaConfig(cmd, biaStrobe=state, doClose=True)
            cmd.finish()

        except Exception as e:
            cmd.fail("text='%s failed to change Bia Strobe %s'" % (self.name.upper(),
                                                                   formatException(e, sys.exc_info()[2])))

    @threaded
    def biaSwitch(self, cmd):
        """Switch bia on/off, optional keyword force to force transition (without breaking interlock)"""
        cmdKeys = cmd.cmd.keywords

        cmdStr = "bia_on" if "on" in cmdKeys else "bia_off"

        self.controller.switch(cmd, cmdStr)

        self.controller.getStatus(cmd)

    @threaded
    def shutterSwitch(self, cmd):
        """Open/close , optional keyword force to force transition (without breaking interlock)"""
        cmdKeys = cmd.cmd.keywords
        shutter = 'shut'
        shutter = 'red' if 'red' in cmdKeys else shutter
        shutter = 'blue' if 'blue' in cmdKeys else shutter
        move = "open" if "open" in cmdKeys else "close"

        cmdStr = "%s_%s" % (shutter, move)

        self.controller.switch(cmd, cmdStr)

        self.controller.getStatus(cmd)

    @threaded
    def shutterExpose(self, cmd):
        """Open/close shutters with temporization"""
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys["exptime"].values[0]
        shutter = 'shut'
        shutter = 'red' if 'red' in cmdKeys else shutter
        shutter = 'blue' if 'blue' in cmdKeys else shutter

        if exptime <= 0:
            cmd.fail("text='exptime must be positive'")
            return

        self.controller.stopExposure = False

        self.controller.expose(cmd, exptime, shutter)
        self.controller.getStatus(cmd)

    @threaded
    def rawCommand(self, cmd):
        """Send a raw command to the bsh board """
        cmdKeys = cmd.cmd.keywords

        cmdStr = cmdKeys["raw"].values[0]

        try:
            reply = self.controller.sendOneCommand(cmdStr, doClose=False, cmd=cmd)

        except Exception as e:
            cmd.warn("text='%s failed to send raw command %s'" % (self.name.upper(),
                                                                  formatException(e,
                                                                                  sys.exc_info()[2])))

        self.controller.getStatus(cmd)

    def abort(self, cmd):
        """Abort current exposure"""
        self.controller.stopExposure = True
        cmd.finish("text='stopping current exposure'")
