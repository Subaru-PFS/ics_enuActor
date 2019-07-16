#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils import waitForTcpServer
from enuActor.utils.wrap import threaded, blocking, singleShot


class IisCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('iis', 'status', self.status),
            ('iis', '[<on>] [<off>]', self.switch),
            ('iis', 'abort', self.abort),
            ('iis', 'stop', self.stop),
            ('iis', 'start', self.start),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu__iis", (1, 1),
                                        keys.Key("on", types.String() * (1, None),
                                                 help='which outlet to switch on.'),
                                        keys.Key("off", types.String() * (1, None),
                                                 help='which outlet to switch off.'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['iis']
        except KeyError:
            raise RuntimeError('iis controller is not connected.')

    @threaded
    def status(self, cmd):
        """Report status and version; obtain and send current data"""
        self.controller.generate(cmd)

    @blocking
    def switch(self, cmd):
        cmdKeys = cmd.cmd.keywords
        arcOn = cmdKeys['on'].values if 'on' in cmdKeys else []
        arcOff = cmdKeys['off'].values if 'off' in cmdKeys else []

        for name in arcOn + arcOff:
            if name not in self.controller.arcs:
                raise ValueError(f'{name} : unknown arc')

        powerOff = dict([(self.controller.powerPorts[name], 'off') for name in arcOff])
        powerOn = [self.controller.powerPorts[name] for name in arcOn if self.controller.isOff(name)]

        self.controller.switching(cmd, powerPorts=powerOff)
        self.controller.substates.warming(cmd, arcOn=powerOn)

        self.controller.generate(cmd)

    def abort(self, cmd, doFinish=True):
        self.controller.doStop = True
        while self.controller.currCmd:
            pass

        genKey = cmd.finish if doFinish else cmd.inform
        genKey("text='warmup aborted'")

    @singleShot
    def stop(self, cmd):
        """ abort iis warmup, turn iis lamp off and disconnect"""
        self.abort(cmd, doFinish=False)

        powerOff = dict([(self.controller.powerPorts[name], 'off') for name in self.controller.arcs])

        try:
            self.controller.switching(cmd, powerPorts=powerOff)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)
        self.controller.disconnect()

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """ connect iis controller"""
        operation = self.actor.config.get('iis', 'mode') == 'operation'

        if operation:
            cmd.inform('text="waiting for tcp server ..."')
            waitForTcpServer(host=self.actor.config.get('iis', 'host'), port=self.actor.config.get('iis', 'port'))

        cmd.inform('text="connecting iis..."')
        self.actor.ownCall(cmd, cmdStr='connect controller=iis', failMsg='failed to connect iis controller')

        self.controller.generate(cmd)
