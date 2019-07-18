#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.drivers.rexm_drivers import TMCM
from enuActor.utils import waitForTcpServer
from enuActor.utils.wrap import threaded, blocking, singleShot


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
            ('rexm', 'stop', self.stop),
            ('rexm', 'start [@(operation|simulation)]', self.start),

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

        self.controller.substates.init(cmd, doHome=doHome)
        self.controller.generate(cmd)

    @blocking
    def moveTo(self, cmd):
        """ Move to low|med resolution position """
        cmdKeys = cmd.cmd.keywords
        position = 'low' if 'low' in cmdKeys else 'med'

        self.controller.substates.move(cmd, position=position)
        self.controller.generate(cmd)

    @blocking
    def moveRelative(self, cmd):
        """ Move to low|med resolution position """
        cmdKeys = cmd.cmd.keywords
        direction = int(cmdKeys['relative'].values[0] > 0)
        distance = abs(cmdKeys['relative'].values[0])

        if not 5 <= distance <= TMCM.DISTANCE_MAX:
            raise ValueError('requested distance out of range')

        self.controller.substates.move(cmd, direction=direction, distance=distance, speed=(TMCM.g_speed / 3))
        self.controller.generate(cmd)

    @threaded
    def resetFlag(self, cmd):
        """Report state, mode, position"""
        self.controller.resetEmergencyFlag(cmd)
        self.controller.substates.idle(cmd)
        self.controller.generate(cmd)

    @singleShot
    def shutdown(self, cmd):
        """ save hexapod position, turn power off and disconnect"""
        try:
            self.controller.abort(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.substates.shutdown(cmd)
        self.controller.getStatus(cmd)

        cmd.inform('text="powering down hxp controller ..."')
        self.actor.ownCall(cmd, cmdStr='power off=slit', failMsg='failed to power off hexapod controller')
        self.controller.disconnect()

        cmd.finish()

    def abort(self, cmd):
        """ Abort current motion """
        self.controller.doAbort()
        cmd.finish("text='motion aborted'")

    @singleShot
    def stop(self, cmd):
        """ abort current motion board, turn power off and disconnect"""
        self.actor.disconnect('rexm', cmd=cmd)

        if 'biasha' not in self.actor.controllers.keys():
            cmd.inform('text="powering down enu rack..."')
            self.actor.ownCall(cmd, cmdStr='power off=ctrl,pows', failMsg='failed to power off enu rack')

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """ power on enu rack, wait for rexm host, connect controller"""
        cmdKeys = cmd.cmd.keywords
        mode = self.actor.config.get('rexm', 'mode')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        cmd.inform('text="powering up enu rack ..."')
        self.actor.ownCall(cmd, cmdStr='power on=pows,ctrl', failMsg='failed to power on enu rack')

        if mode == 'operation':
            cmd.inform('text="waiting for tcp server ..."')
            waitForTcpServer(host=self.actor.config.get('rexm', 'host'), port=self.actor.config.get('rexm', 'port'))

        self.actor.connect('rexm', cmd=cmd, mode=mode)

        cmd.inform('text="rexm init"')
        self.actor.ownCall(cmd, cmdStr='rexm init', failMsg='failed to init rexm')

        self.controller.generate(cmd)
