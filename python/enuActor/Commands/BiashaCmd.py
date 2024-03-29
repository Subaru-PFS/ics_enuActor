#!/usr/bin/env python

import time

import ics.utils.tcp.bufferedSocket as bufferedSocket
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.utils.threading import threaded, blocking, singleShot
from opscore.utility.qstr import qstr


class BiashaCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('biasha', 'status', self.status),
            ('biasha', '<raw>', self.rawCommand),
            ('biasha', 'init', self.init),
            ('bia', '@on [strobe] [<period>] [<duty>] [<power>]', self.biaOn),
            ('bia', '@off', self.biaOff),
            ('bia', '@strobe @on [<period>] [<duty>] [<power>]', self.biaOn),
            ('bia', '@strobe @off', self.strobeOff),
            ('bia', '[<period>] [<duty>] [<power>]', self.biaConfig),
            ('bia', 'status', self.biaStatus),
            ('shutters', '@(open|close) [blue|red]', self.shutterSwitch),
            ('shutters', 'status', self.shutterStatus),
            ('shutters', '@(expose) <exptime> [blue|red|none] [<shutterMask>] [<visit>]', self.expose),
            ('shutters', '@(blue|red) <raw>', self.shutterRaw),
            ('exposure', 'abort', self.abortExposure),
            ('exposure', 'finish', self.finishExposure),
            ('biasha', 'stop', self.stop),
            ('biasha', 'start [@(operation|simulation)]', self.start),
            ('biasha', 'reboot', self.reboot),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('enu__biasha', (1, 1),
                                        keys.Key('duty', types.Int(), help='bia duty cycle (0..255)'),
                                        keys.Key('period', types.Int(), help='bia period'),
                                        keys.Key("power", types.Float(),
                                                 help='power level to set (0..100)'),
                                        keys.Key('raw', types.String(), help='raw command'),
                                        keys.Key('exptime', types.Float(), help='exposure time'),
                                        keys.Key('shutterMask', types.Long(), help='shutterMask'),
                                        keys.Key('visit', types.Int(), help='pfsVisit'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['biasha']
        except KeyError:
            raise RuntimeError('biasha controller is not connected.')

    @threaded
    def status(self, cmd):
        """Report state, mode, statuses."""
        self.controller.generate(cmd)

    @threaded
    def shutterStatus(self, cmd):
        """Get shutters status."""
        self.controller.shutterStatus(cmd)
        cmd.finish()

    @threaded
    def biaStatus(self, cmd):
        """Get bia status."""
        self.controller.biaStatus(cmd)
        cmd.finish()

    @blocking
    def biaOn(self, cmd):
        """Switch bia on."""
        cmdKeys = cmd.cmd.keywords

        strobe = True if 'strobe' in cmdKeys else None
        period = cmdKeys['period'].values[0] if 'period' in cmdKeys else None
        duty = cmdKeys['duty'].values[0] if 'duty' in cmdKeys else None
        power = cmdKeys['power'].values[0] if 'power' in cmdKeys else None

        self.controller.setBiaConfig(cmd, strobe=strobe, period=period, duty=duty, power=power)

        if self.controller.substates.current == 'BIA':
            cmd.inform('text="bia already on, not forwarding to biasha board....')
        else:
            self.controller.gotoState(cmd, cmdStr='bia_on')

        self.controller.biaStatus(cmd)
        cmd.finish()

    @blocking
    def biaOff(self, cmd):
        """Switch bia off."""

        if self.controller.substates.current == 'IDLE':
            cmd.inform('text="bia already off, not forwarding to biasha board....')
        else:
            self.controller.gotoState(cmd, cmdStr='bia_off')

        self.controller.biaStatus(cmd)
        cmd.finish()

    @threaded
    def strobeOff(self, cmd):
        """Deactivate bia strobe mode. """
        self.controller.setBiaConfig(cmd, strobe=False)
        self.controller.biaStatus(cmd)
        cmd.finish()

    @threaded
    def biaConfig(self, cmd):
        """Set new bia config. """
        cmdKeys = cmd.cmd.keywords
        period = cmdKeys['period'].values[0] if 'period' in cmdKeys else None
        duty = cmdKeys['duty'].values[0] if 'duty' in cmdKeys else None
        power = cmdKeys['power'].values[0] if 'power' in cmdKeys else None

        self.controller.setBiaConfig(cmd, period=period, duty=duty, power=power)
        self.controller.biaStatus(cmd)
        cmd.finish()

    @blocking
    def shutterSwitch(self, cmd):
        """Open/close shutters (red/blue or both)."""
        cmdKeys = cmd.cmd.keywords
        shutter = 'shut'
        shutter = 'red' if 'red' in cmdKeys else shutter
        shutter = 'blue' if 'blue' in cmdKeys else shutter
        move = 'open' if 'open' in cmdKeys else 'close'

        self.controller.gotoState(cmd, cmdStr='%s_%s' % (shutter, move))
        self.controller.shutterStatus(cmd)
        cmd.finish()

    @blocking
    def expose(self, cmd):
        """Shutters expose routine."""
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys["exptime"].values[0]
        visit = cmdKeys["visit"].values[0] if 'visit' in cmdKeys else -1

        # open both shutters by default
        shutterMask = self.controller.shutterToMask['shut']

        # from cmdKeys if specified.
        shutterMask = cmdKeys['shutterMask'].values[0] if 'shutterMask' in cmdKeys else shutterMask

        # or if shutters specified as string.
        for key in ['blue', 'red', 'none']:
            shutterMask = self.controller.shutterToMask[key] if key in cmdKeys else shutterMask

        if exptime < 0.5 and shutterMask:
            raise ValueError('exptime>=0.5 (red shutter transientTime)')

        self.controller.expose(cmd=cmd,
                               exptime=exptime,
                               shutterMask=shutterMask,
                               visit=visit)

        self.controller.generate(cmd)

    @threaded
    def init(self, cmd):
        """Go to biasha init state."""
        if self.controller.substates.current == "FAILED":
            cmd.warn('text="acknowledging FAILED state..."')
            self.controller.substates.ack()

        self.controller.gotoState(cmd, 'init')
        self.controller.generate(cmd)

    @threaded
    def rawCommand(self, cmd):
        """Send a raw command to the biasha board."""
        cmdKeys = cmd.cmd.keywords
        cmdStr = cmdKeys['raw'].values[0]
        ret = self.controller.sendOneCommand(cmdStr, cmd=cmd)
        cmd.finish('text=%s' % (qstr('returned: %s' % (ret))))

    @singleShot
    def shutterRaw(self, cmd):
        """Send a raw command to the (blue|red) shutter controller via RS232 link."""
        cmdKeys = cmd.cmd.keywords

        shutter = 'blueshutter' if 'blue' in cmdKeys else 'redshutter'
        cmdStr = cmdKeys['raw'].values[0]

        sock = bufferedSocket.EthComm(host=self.actor.actorConfig[shutter]['host'],
                                      port=self.actor.actorConfig[shutter]['port'],
                                      EOL='\r')

        sock.ioBuffer = bufferedSocket.BufferedSocket(shutter + "IO", EOL='c>')
        sock.connectSock()
        ret = sock.sendOneCommand(cmdStr, doClose=True, cmd=cmd)
        cmd.finish('text=%s' % (qstr('returned: %s' % (ret))))

    def abortExposure(self, cmd):
        """Abort current exposure."""
        self.controller.doAbort()
        cmd.finish("text='exposure aborted'")

    def finishExposure(self, cmd):
        """Finish current exposure."""
        self.controller.doFinish()
        cmd.finish("text='exposure finished'")

    @singleShot
    def stop(self, cmd):
        """Finish current exposure, power off and disconnect."""
        self.actor.disconnect('biasha', cmd=cmd)

        if 'rexm' not in self.actor.controllers.keys():
            self.actor.powerSwitch('ctrl,pows', state='off', cmd=cmd)

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """Power on enu rack, wait for biasha host, connect controller."""
        cmdKeys = cmd.cmd.keywords

        mode = self.actor.actorConfig['biasha']['mode']
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode
        self.actor.startController('biasha', cmd=cmd, mode=mode)

        self.controller.generate(cmd)

    @singleShot
    def reboot(self, cmd):
        """Power on enu rack, wait for biasha host, connect controller."""
        cmd.inform('text="rebooting biasha board..."')
        self.actor.disconnect('biasha', cmd=cmd)

        # power off and wait
        self.actor.powerSwitch('ctrl', state='off', cmd=cmd)
        time.sleep(10)

        self.actor.startController('biasha', cmd=cmd)

        self.controller.generate(cmd)
