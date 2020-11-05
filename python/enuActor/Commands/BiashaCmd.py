#!/usr/bin/env python

import enuActor.utils.bufferedSocket as bufferedSocket
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils import waitForTcpServer, serverIsUp
from enuActor.utils.wrap import threaded, blocking, singleShot
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
            ('bia', '@strobe @on [<period>] [<duty>] [<power>]', self.strobeOn),
            ('bia', '@strobe @off', self.strobeOff),
            ('bia', '[<period>] [<duty>] [<power>]', self.biaConfig),
            ('bia', 'status', self.biaStatus),
            ('shutters', '@(open|close) [blue|red]', self.shutterSwitch),
            ('shutters', 'status', self.shutterStatus),
            ('shutters', '@(expose) <exptime> [blue|red]', self.expose),
            ('shutters', '@(blue|red) <raw>', self.shutterRaw),
            ('exposure', 'abort', self.abortExposure),
            ('exposure', 'finish', self.finishExposure),
            ('biasha', 'stop', self.stop),
            ('biasha', 'start [@(operation|simulation)]', self.start),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('enu__biasha', (1, 1),
                                        keys.Key('duty', types.Int(), help='bia duty cycle (0..255)'),
                                        keys.Key('period', types.Int(), help='bia period'),
                                        keys.Key("power", types.Float(),
                                                 help='power level to set (0..100)'),
                                        keys.Key('raw', types.String(), help='raw command'),
                                        keys.Key('exptime', types.Float(), help='exposure time'),
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

        strobe = 'on' if 'strobe' in cmdKeys else None
        period = cmdKeys['period'].values[0] if 'period' in cmdKeys else None
        duty = cmdKeys['duty'].values[0] if 'duty' in cmdKeys else None
        duty = round(cmdKeys['power'].values[0] * 255 / 100) if 'power' in cmdKeys else duty

        self.controller.setBiaConfig(cmd, strobe=strobe, period=period, duty=duty)

        self.controller.gotoState(cmd, cmdStr='bia_on')
        self.controller.biaStatus(cmd)
        cmd.finish()

    @blocking
    def biaOff(self, cmd):
        """Switch bia off."""
        self.controller.gotoState(cmd, cmdStr='bia_off')
        self.controller.biaStatus(cmd)
        cmd.finish()

    @threaded
    def strobeOn(self, cmd):
        """Activate bia strobe mode. """
        cmdKeys = cmd.cmd.keywords
        period = cmdKeys['period'].values[0] if 'period' in cmdKeys else None
        duty = cmdKeys['duty'].values[0] if 'duty' in cmdKeys else None
        duty = round(cmdKeys['power'].values[0] * 255 / 100) if 'power' in cmdKeys else duty

        self.controller.setBiaConfig(cmd, strobe='on', period=period, duty=duty)
        self.controller.biaStatus(cmd)
        cmd.finish()

    @threaded
    def strobeOff(self, cmd):
        """Deactivate bia strobe mode. """
        self.controller.setBiaConfig(cmd, strobe='off')
        self.controller.biaStatus(cmd)
        cmd.finish()

    @threaded
    def biaConfig(self, cmd):
        """Set new bia config. """
        cmdKeys = cmd.cmd.keywords
        period = cmdKeys['period'].values[0] if 'period' in cmdKeys else None
        duty = cmdKeys['duty'].values[0] if 'duty' in cmdKeys else None
        duty = round(cmdKeys['power'].values[0] * 255 / 100) if 'power' in cmdKeys else duty

        self.controller.setBiaConfig(cmd, period=period, duty=duty)
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
        shutter = 'shut'
        shutter = 'red' if 'red' in cmdKeys else shutter
        shutter = 'blue' if 'blue' in cmdKeys else shutter

        if exptime < 0.5:
            raise ValueError('exptime>=0.5 (red shutter transientTime)')

        self.controller.expose(cmd=cmd,
                               exptime=exptime,
                               shutter=shutter)

        self.controller.generate(cmd)

    @threaded
    def init(self, cmd):
        """Go to biasha init state."""
        self.controller.gotoState(cmd, 'init')
        self.controller.generate(cmd)

    @threaded
    def rawCommand(self, cmd):
        """Send a raw command to the biasha board."""
        cmdKeys = cmd.cmd.keywords
        cmdStr = cmdKeys['raw'].values[0]
        ret = bufferedSocket.EthComm.sendOneCommand(self.controller, cmdStr=cmdStr, cmd=cmd)
        cmd.finish('text=%s' % (qstr('returned: %s' % (ret))))

    @singleShot
    def shutterRaw(self, cmd):
        """Send a raw command to the (blue|red) shutter controller via RS232 link."""
        cmdKeys = cmd.cmd.keywords

        shutter = 'blueshutter' if 'blue' in cmdKeys else 'redshutter'
        cmdStr = cmdKeys['raw'].values[0]

        sock = bufferedSocket.EthComm(host=self.actor.config.get(shutter, 'host'),
                                      port=int(self.actor.config.get(shutter, 'port')),
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
            cmd.inform('text="powering down enu rack..."')
            self.actor.ownCall(cmd, cmdStr='power off=ctrl,pows', failMsg='failed to power off enu rack')

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """Power on enu rack, wait for biasha host, connect controller."""
        cmdKeys = cmd.cmd.keywords
        mode = self.actor.config.get('biasha', 'mode')
        host = self.actor.config.get('biasha', 'host')
        port = self.actor.config.get('biasha', 'port')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        if not serverIsUp(host=host, port=port):
            cmd.inform('text="powering up enu rack ..."')
            self.actor.ownCall(cmd, cmdStr='power on=pows,ctrl', failMsg='failed to power on enu rack')
            waitForTcpServer(host=host, port=port, cmd=cmd, mode=mode)

        self.actor.connect('biasha', cmd=cmd, mode=mode)
        cmd.finish()
