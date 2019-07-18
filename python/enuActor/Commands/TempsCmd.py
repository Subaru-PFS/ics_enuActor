#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils import waitForTcpServer
from enuActor.utils.wrap import threaded, singleShot


class TempsCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('temps', 'status', self.status),
            ('temps', 'resistance', self.getResistance),
            ('temps', 'error', self.getError),
            ('temps', 'info', self.getInfo),
            ('temps', '<raw>', self.rawCommand),
            ('temps', 'stop', self.stop),
            ('temps', 'start [@(operation|simulation)]', self.start),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_temps", (1, 1),
                                        keys.Key("raw", types.String(), help="raw command"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['temps']
        except KeyError:
            raise RuntimeError('temps controller is not connected.')

    @threaded
    def status(self, cmd):
        """Report state, substate, mode, temperatures"""
        self.controller.generate(cmd)

    @threaded
    def getResistance(self, cmd):
        """Report resistance value for all sensors"""
        self.controller.getResistance(cmd)
        cmd.finish()

    @threaded
    def getError(self, cmd):
        """Report controller error"""
        self.controller.getError(cmd)
        cmd.finish()

    @threaded
    def getInfo(self, cmd):
        """Report controller info"""
        self.controller.getInfo(cmd)
        cmd.finish()

    @threaded
    def rawCommand(self, cmd):
        """send a raw command to the controller"""
        cmdKeys = cmd.cmd.keywords
        cmdStr = cmdKeys["raw"].values[0]

        cmd.finish('text=%s' % self.controller.sendOneCommand(cmdStr, cmd=cmd))

    @singleShot
    def stop(self, cmd):
        """ finish current exposure, power off and disconnect"""
        self.actor.disconnect('temps', cmd=cmd)

        cmd.inform('text="powering down temps controller..."')
        self.actor.ownCall(cmd, cmdStr='power off=temps', failMsg='failed to power off temps')

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """ power on temps controller, wait for temps host, connect controller"""
        cmdKeys = cmd.cmd.keywords
        mode = self.actor.config.get('temps', 'mode')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        cmd.inform('text="powering up temps controller ..."')
        self.actor.ownCall(cmd, cmdStr='power on=temps', failMsg='failed to power on temps')

        if mode == 'operation':
            cmd.inform('text="waiting for tcp server ..."')
            waitForTcpServer(host=self.actor.config.get('temps', 'host'), port=self.actor.config.get('temps', 'port'))

        self.actor.connect('temps', cmd=cmd, mode=mode)

        cmd.finish()
