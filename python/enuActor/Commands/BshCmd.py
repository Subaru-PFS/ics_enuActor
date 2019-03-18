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
            ('bsh', '<raw>', self.rawCommand),
            ('bsh', 'init', self.initBsh),
            ('bia', '@(on|off)', self.biaSwitch),
            ('bia', '@(strobe) @(on|off)', self.setStrobe),
            ('bia', 'config [<duty>] [<period>]', self.setBiaConfig),
            ('bia', 'status', self.biaStatus),
            ('shutters', '@(open|close) [blue|red]', self.shutterSwitch),
            ('shutters', 'status', self.shutterStatus),
            ('shutters', '@(expose) <exptime> [blue|red]', self.expose),
            ('exposure', 'abort', self.abortExposure),
            ('exposure', 'finish', self.finishExposure)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('enu__bsh', (1, 1),
                                        keys.Key('duty', types.Int(), help='bia duty cycle (0..255)'),
                                        keys.Key('period', types.Int(), help='bia period'),
                                        keys.Key('raw', types.String(), help='raw command'),
                                        keys.Key('exptime', types.Float(), help='exposure time'),
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
        cmd.finish('text="%s controller Present and (probably) well"' % self.name)

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""
        self.controller.generate(cmd)

    @threaded
    def shutterStatus(self, cmd):
        """get shutters status"""
        self.controller.shutterStatus(cmd)
        cmd.finish()

    @threaded
    def biaStatus(self, cmd):
        """get bia status"""
        self.controller.biaStatus(cmd)
        cmd.finish()

    @threaded
    def initBsh(self, cmd):
        """Report state, mode, position"""
        self.controller.gotoState(cmd, 'init')
        self.controller.generate(cmd)

    @threaded
    def rawCommand(self, cmd):
        """send a raw command to the bsh board"""
        cmdKeys = cmd.cmd.keywords
        cmdStr = cmdKeys['raw'].values[0]
        cmd.finish('text=%s' % self.controller.sendOneCommand(cmdStr, cmd=cmd))

    @threaded
    def setBiaConfig(self, cmd):
        """Update bia parameters """
        cmdKeys = cmd.cmd.keywords
        period = cmdKeys['period'].values[0] if 'period' in cmdKeys else None
        duty = cmdKeys['duty'].values[0] if 'duty' in cmdKeys else None

        self.controller.setBiaConfig(cmd, period, duty)
        cmd.finish()

    @threaded
    def setStrobe(self, cmd):
        """Activate|desactivate bia strobe mode  """
        cmdKeys = cmd.cmd.keywords
        state = 'off' if 'off' in cmdKeys else 'on'

        self.controller.setBiaConfig(cmd, strobe=state)
        cmd.finish()

    @threaded
    def biaSwitch(self, cmd):
        """Switch bia on/off)"""
        cmdKeys = cmd.cmd.keywords
        state = 'on' if 'on' in cmdKeys else 'off'

        self.controller.gotoState(cmd, cmdStr='bia_%s' % state)
        self.controller.biaStatus(cmd)
        cmd.finish()

    @threaded
    def shutterSwitch(self, cmd):
        """Open/close shutters (red/blue or both)"""
        cmdKeys = cmd.cmd.keywords
        shutter = 'shut'
        shutter = 'red' if 'red' in cmdKeys else shutter
        shutter = 'blue' if 'blue' in cmdKeys else shutter
        move = 'open' if 'open' in cmdKeys else 'close'

        self.controller.gotoState(cmd, cmdStr='%s_%s' % (shutter, move))
        self.controller.shutterStatus(cmd)
        cmd.finish()

    @threaded
    def expose(self, cmd):
        """send a raw command to the bsh board"""
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys["exptime"].values[0]
        shutter = 'shut'
        shutter = 'red' if 'red' in cmdKeys else shutter
        shutter = 'blue' if 'blue' in cmdKeys else shutter

        if exptime < 0.5:
            raise ValueError('exptime>=0.5 (red shutter transientTime)')

        self.controller.expose(cmd=cmd,
                               exptime=exptime,
                               shutter=shutter)

        self.controller.generate(cmd)

    def abortExposure(self, cmd):
        """send a raw command to the bsh board"""
        self.controller.abortExposure = True
        cmd.finish("text='aborting current exposure'")

    def finishExposure(self, cmd):
        """send a raw command to the bsh board"""
        self.controller.finishExposure = True
        cmd.finish("text='finishing current exposure'")
