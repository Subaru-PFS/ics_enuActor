#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils import waitForTcpServer
from enuActor.utils.wrap import threaded, singleShot


class PduCmd(object):
    def __init__(self, actor, name='pdu'):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.name = name
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            (self.name, 'status', self.status),
            ('power', 'status', self.status),
            ('power', '[<on>] [<off>]', self.switch),
            (self.name, 'stop', self.stop),
            (self.name, 'start [@(operation|simulation)]', self.start),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu__pdu", (1, 1),
                                        keys.Key("on", types.String() * (1, None),
                                                 help='which outlet to switch on.'),
                                        keys.Key("off", types.String() * (1, None),
                                                 help='which outlet to switch off.'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('pdu controller is not connected.')

    @threaded
    def status(self, cmd):
        """Report state, mode, status."""
        self.controller.generate(cmd)

    @threaded
    def switch(self, cmd):
        """Switch on/off outlets."""
        cmdKeys = cmd.cmd.keywords

        switchOn = cmdKeys['on'].values if 'on' in cmdKeys else []
        switchOff = cmdKeys['off'].values if 'off' in cmdKeys else []
        powerNames = dict([(name, 'on') for name in switchOn] + [(name, 'off') for name in switchOff])

        for name in powerNames.keys():
            if name not in self.controller.powerPorts.keys():
                raise ValueError('%s : unknown port' % name)

        powerPorts = dict([(self.controller.powerPorts[name], state) for name, state in powerNames.items()])

        self.controller.substates.switch(cmd, powerPorts=powerPorts)
        self.controller.generate(cmd)

    @singleShot
    def stop(self, cmd):
        """Disconnect controller."""
        self.actor.disconnect(self.name, cmd=cmd)
        cmd.finish()

    @singleShot
    def start(self, cmd):
        """Connect pdu controller."""
        cmdKeys = cmd.cmd.keywords
        mode = self.actor.config.get('pdu', 'mode')
        host = self.actor.config.get('pdu', 'host')
        port = self.actor.config.get('pdu', 'port')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        waitForTcpServer(host=host, port=port, cmd=cmd, mode=mode)

        self.actor.connect(self.name, cmd=cmd, mode=mode)
        cmd.finish()
