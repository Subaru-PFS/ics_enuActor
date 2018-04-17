#!/usr/bin/env python

import subprocess

import opscore.protocols.keys as keys
import opscore.protocols.types as types


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
            ('start', '', self.initControllers),
            ('set', '<controller> <mode>', self.changeMode)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_enu", (1, 1),
                                        keys.Key("controllers", types.String() * (1, None),
                                                 help='the names of 1 or more controllers to load'),
                                        keys.Key("controller", types.String(),
                                                 help='the names a controller.'),
                                        keys.Key("mode", types.String(),
                                                 help='controller mode'),
                                        keys.Key("period", types.Int(),
                                                 help='the period to sample at.'),
                                        )

    def monitor(self, cmd):
        """ Enable/disable/adjust period controller monitors. """

        period = cmd.cmd.keywords['period'].values[0]
        controllers = cmd.cmd.keywords['controllers'].values

        knownControllers = []
        for c in self.actor.config.get(self.actor.name, 'controllers').split(','):
            c = c.strip()
            knownControllers.append(c)

        foundOne = False
        for c in controllers:
            if c not in knownControllers:
                cmd.warn('text="not starting monitor for %s: unknown controller"' % (c))
                continue

            self.actor.monitor(c, period, cmd=cmd)
            foundOne = True

        if foundOne:
            cmd.finish()
        else:
            cmd.fail('text="no controllers found"')

    def controllerKey(self):
        """Return controllers keyword
        """
        controllerNames = list(self.actor.controllers.keys())
        key = 'controllers=%s' % (','.join([c for c in controllerNames]))

        return key

    def initControllers(self, cmd):
        """Init all enu controllers"""
        for c in self.actor.controllers:
            self.actor.callCommand("%s init" % c)
        cmd.finish()

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report enu status, actor version and each controller status """

        self.actor.sendVersionKey(cmd)

        cmd.inform('text=%s' % "Present!")
        cmd.inform('text="monitors: %s"' % self.actor.monitors)
        cmd.inform('text="config id=0x%08x %r"' % (id(self.actor.config),
                                                   self.actor.config.sections()))

        self.actor.updateStates(cmd=cmd)

        if 'all' in cmd.cmd.keywords:
            for c in self.actor.controllers:
                self.actor.callCommand("%s status" % c)

        cmd.finish(self.controllerKey())

    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords

        controller = cmd.cmd.keywords['controller'].values[0]
        mode = cmd.cmd.keywords['mode'].values[0]

        knownControllers = [c.strip() for c in self.actor.config.get(self.actor.name, 'controllers').split(',')]

        if controller not in knownControllers:
            raise ValueError('unknown controller')

        if mode not in ['operation', 'simulation']:
            raise ValueError('unknown mode')


        self.actor.attachController(name=controller,
                                    cmd=cmd,
                                    mode=mode)

        self.actor.callCommand("%s status" % controller)

        cmd.finish()