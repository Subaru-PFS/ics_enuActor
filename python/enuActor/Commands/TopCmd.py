#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.sync import SyncCmd
from ics.utils.threading import singleShot


class TopCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '[@all]', self.status),
            ('monitor', '<controllers> <period>', self.monitor),
            ('start', '', self.start),
            ('stop', '', self.stop),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_enu", (1, 1),
                                        keys.Key("controllers", types.String() * (1, None),
                                                 help='the names of 1 or more controllers to load'),
                                        keys.Key("controller", types.String(),
                                                 help='the names a controller.'),
                                        keys.Key("period", types.Int(),
                                                 help='the period to sample at.'),
                                        )

    def monitor(self, cmd):
        """Enable/disable/adjust period controller monitors."""

        period = cmd.cmd.keywords['period'].values[0]
        controllers = cmd.cmd.keywords['controllers'].values

        foundOne = False
        for c in controllers:
            if c not in self.actor.knownControllers:
                cmd.warn('text="not starting monitor for %s: unknown controller"' % (c))
                continue

            self.actor.monitor(c, period, cmd=cmd)
            foundOne = True

        if foundOne:
            cmd.finish()
        else:
            cmd.fail('text="no controllers found"')

    def controllerKey(self):
        """Return controllers keyword."""
        controllerNames = list(self.actor.controllers.keys())
        key = 'controllers=%s' % (','.join([c for c in controllerNames]) if controllerNames else None)

        return key

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""
        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report enu status, actor version and each controller status."""

        self.actor.sendVersionKey(cmd)

        cmd.inform('text="monitors: %s"' % self.actor.monitors)
        cmd.inform('text="config id=0x%08x %r"' % (id(self.actor.config),
                                                   self.actor.config.sections()))

        self.genPersistedKeys(cmd)
        self.actor.genInstConfigKeys(cmd)
        self.actor.metaStates.update(cmd)

        if 'all' in cmd.cmd.keywords:
            for c in self.actor.controllers:
                self.actor.callCommand("%s status" % c)

        cmd.finish(self.controllerKey())

    def genPersistedKeys(self, cmd):
        """Make sure that hexapodMoved and gratingMoved are generated as soon as enuActor start."""
        try:
            hexapodMoved, = self.actor.instData.loadKey('hexapodMoved')
        except:
            hexapodMoved = float('nan')

        try:
            gratingMoved, = self.actor.instData.loadKey('gratingMoved')
        except:
            gratingMoved = float('nan')

        cmd.inform(f'hexapodMoved={hexapodMoved:0.6f}')
        cmd.inform(f'gratingMoved={gratingMoved:0.6f}')

    @singleShot
    def start(self, cmd):
        """Start all enu controllers."""
        cmdList = [f'{c} start' for c in ['rexm', 'slit', 'biasha', 'temps', 'iis']]
        syncCmd = SyncCmd(self.actor, cmdList)
        syncCmd.call(cmd)
        syncCmd.sync()
        syncCmd.exit()

        cmd.finish()

    @singleShot
    def stop(self, cmd):
        """Stop all enu controllers."""
        cmdList = [f'{c} stop' for c in ['rexm', 'slit', 'biasha', 'temps', 'iis']]
        syncCmd = SyncCmd(self.actor, cmdList)
        syncCmd.call(cmd)
        syncCmd.sync()
        syncCmd.exit()

        cmd.finish()
