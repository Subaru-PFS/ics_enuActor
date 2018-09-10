#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


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
            ('bsh', '<raw>', self.rawCommand),
            ('bia', '@(on|off)', self.biaSwitch),
            ('bia', '@(strobe) @(on|off)', self.biaStrobe),
            ('bia', 'config [<duty>] [<period>]', self.sendConfig),
            ('shutters', '@(open|close) [blue|red] [force]', self.shutterSwitch),
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

    def status(self, cmd):
        """Report state, mode, position"""
        self.controller.getBiaConfig(cmd)
        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise Bsh, call fsm startInit event """

        self.controller.substates.init(cmd=cmd)
        self.controller.getStatus(cmd)

    def sendConfig(self, cmd):
        """Update bia parameters """

        cmdKeys = cmd.cmd.keywords
        period, duty = None, None

        if "period" in cmdKeys:
            if 0 < cmdKeys["period"].values[0] < 65536:
                period = int(cmdKeys["period"].values[0])
            else:
                raise ValueError("period not in range : %i=> %i" % (0, 65535))

        if "duty" in cmdKeys:
            if 0 < cmdKeys["duty"].values[0] < 256:
                duty = int(cmdKeys["duty"].values[0])
            else:
                raise ValueError("duty not in range : %i => %i" % (0, 255))

        self.controller.setBiaConfig(cmd, period, duty, doClose=True)
        cmd.finish()

    def biaStrobe(self, cmd):
        """Activate|desactivate bia strobe mode  """
        cmdKeys = cmd.cmd.keywords
        state = "off" if "off" in cmdKeys else "on"

        self.controller.setBiaConfig(cmd, biaStrobe=state, doClose=True)
        cmd.finish()

    def biaSwitch(self, cmd):
        """Switch bia on/off, optional keyword force to force transition (without breaking interlock)"""
        cmdKeys = cmd.cmd.keywords

        cmdStr = "bia_on" if "on" in cmdKeys else "bia_off"

        self.controller.switch(cmd, cmdStr)

        self.controller.getStatus(cmd)

    def shutterSwitch(self, cmd):
        """Open/close , optional keyword force to force transition (without breaking interlock)"""
        cmdKeys = cmd.cmd.keywords
        shutter = 'shut'
        shutter = 'red' if 'red' in cmdKeys else shutter
        shutter = 'blue' if 'blue' in cmdKeys else shutter
        move = "open" if "open" in cmdKeys else "close"
        force = True if 'force' in cmdKeys else False

        if self.controller.substates.current == 'EXPOSING' and not force:
            raise UserWarning('shutter cant be operated during an exposure unless keyword force is added')

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

        self.controller.substates.expose(cmd=cmd,
                                         exptime=exptime,
                                         shutter=shutter)
        self.controller.getStatus(cmd)

    def rawCommand(self, cmd):
        """Send a raw command to the bsh board """
        cmdKeys = cmd.cmd.keywords

        cmdStr = cmdKeys["raw"].values[0]

        try:
            reply = self.controller.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            cmd.inform('text=%s' % reply)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

    def abort(self, cmd):
        """Abort current exposure"""
        self.controller.stopExposure = True
        cmd.finish("text='stopping current exposure'")
