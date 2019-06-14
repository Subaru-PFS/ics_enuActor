#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.drivers.rexm_drivers import TMCM
from enuActor.utils.wrap import threaded, blocking


class RexmCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('rexm', 'status', self.status),
            ('rexm', 'init [@(skipHoming)]', self.initialise),
            ('rexm', '@(low|med)', self.moveTo),
            ('rexm', '@moveTo @(low|med)', self.moveTo),
            ('rexm', '@(move) <relative>', self.moveRelative),
            ('rexm', 'resetFlag', self.resetFlag),
            ('rexm', 'abort', self.abort),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('enu_rexm', (1, 1),
                                        keys.Key('relative', types.Float(), help='relative move in mm'))

    @property
    def controller(self):
        try:
            return self.actor.controllers['rexm']
        except KeyError:
            raise RuntimeError('rexm controller is not connected.')

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""
        self.controller.generate(cmd)

    @blocking
    def initialise(self, cmd):
        """Initialise Slit, call fsm startInit event """

        doHome = 'skipHoming' not in cmd.cmd.keywords

        self.controller.substates.init(cmd, doHome)
        self.controller.generate(cmd)

    @blocking
    def moveTo(self, cmd):
        """ Move to low|med resolution position """
        cmdKeys = cmd.cmd.keywords
        position = 'low' if 'low' in cmdKeys else 'med'

        self.controller.substates.move(cmd, dict(position=position))
        self.controller.generate(cmd)

    @blocking
    def moveRelative(self, cmd):
        """ Move to low|med resolution position """
        cmdKeys = cmd.cmd.keywords
        direction = int(cmdKeys['relative'].values[0] > 0)
        distance = abs(cmdKeys['relative'].values[0])

        if not 5 <= distance <= TMCM.DISTANCE_MAX:
            raise ValueError('requested distance out of range')

        self.controller.substates.move(cmd, dict(direction=direction,
                                                 distance=distance,
                                                 speed=(TMCM.g_speed / 3)))
        self.controller.generate(cmd)

    @threaded
    def resetFlag(self, cmd):
        """Report state, mode, position"""
        self.controller.resetEmergencyFlag(cmd)
        self.controller.substates.idle(cmd)
        self.controller.generate(cmd)

    def abort(self, cmd):
        """ Abort current motion """

        self.controller.abortMotion = True
        cmd.finish()
