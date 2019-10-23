#!/usr/bin/env python

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils import waitForTcpServer, serverIsUp
from enuActor.utils.wrap import threaded, blocking, singleShot


class SlitCmd(object):
    coordsName = ['X', 'Y', 'Z', 'U', 'V', 'W']

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('slit', 'status', self.status),
            ('slit', 'init [@(skipHoming)]', self.initialise),
            ('slit', 'abort', self.abort),
            ('slit', 'enable', self.motionEnable),
            ('slit', 'disable', self.motionDisable),
            ('slit', '@(get) @(work|tool|base)', self.getSystem),
            ('slit', '@(set) @(work|tool) [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.setSystem),
            ('slit', 'move home', self.goHome),
            ('slit', 'home', self.goHome),
            ('slit', 'move absolute [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.moveAbs),
            ('slit', 'move relative [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.moveRel),
            ('slit', '<focus> [@(microns)]', self.focus),
            ('slit', '<dither> [@(pixels|microns)]', self.dither),
            ('slit', '<shift> [@(pixels|microns)]', self.shift),
            ('slit', 'convert <X> <Y> <Z> <U> <V> <W>', self.convert),
            ('slit', 'stop', self.stop),
            ('slit', 'start [@(fullInit)] [@(operation|simulation)]', self.start),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('enu__slit', (1, 1),
                                        keys.Key('X', types.Float(), help='X coordinate'),
                                        keys.Key('Y', types.Float(), help='Y coordinate'),
                                        keys.Key('Z', types.Float(), help='Z coordinate'),
                                        keys.Key('U', types.Float(), help='U coordinate'),
                                        keys.Key('V', types.Float(), help='V coordinate'),
                                        keys.Key('W', types.Float(), help='W coordinate'),
                                        keys.Key('focus', types.Float(), help='move along focus axis'),
                                        keys.Key('dither', types.Float(), help='move along dither axis'),
                                        keys.Key('shift', types.Float(), help='move along shift axis')
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['slit']
        except KeyError:
            raise RuntimeError('slit controller is not connected.')

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
    def moveAbs(self, cmd):
        """ Move to (X, Y, Z, U, V, W) rel. to home if absolute specified\
                else if relative then incremental move. NB: In relative move parameters are optional.
        """
        cmdKeys = cmd.cmd.keywords
        current = self.controller.coords
        coords = [cmdKeys[c].values[0] if c in cmdKeys else current[i] for i, c in enumerate(self.coordsName)]

        self.controller.substates.move(cmd, reference='absolute', coords=coords)
        self.controller.generate(cmd)

    @blocking
    def moveRel(self, cmd):
        """ Move to (X, Y, Z, U, V, W) rel. to home if absolute specified\
                else if relative then incremental move. NB: In relative move parameters are optional.
        """
        cmdKeys = cmd.cmd.keywords
        coords = [cmdKeys[coord].values[0] if coord in cmdKeys else 0.0 for coord in self.coordsName]

        self.controller.substates.move(cmd, reference='relative', coords=coords)
        self.controller.generate(cmd)

    @blocking
    def goHome(self, cmd):
        """   Go to home related to work : [0,0,0,0,0,0] """
        reference = 'absolute'
        coords = 6 * [0.]

        self.controller.substates.move(cmd, reference=reference, coords=coords)
        self.controller.generate(cmd)

    @blocking
    def focus(self, cmd):
        """ Move wrt focus axis."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords['focus'].values[0]
        fact = 0.001 if 'microns' in cmdKeys else 1
        focus_axis = np.array([float(val) for val in self.actor.config.get('slit', 'focus_axis').split(',')])
        coords = focus_axis * fact * shift
        reference = 'relative'

        self.controller.substates.move(cmd, reference=reference, coords=coords)
        self.controller.generate(cmd)

    @blocking
    def dither(self, cmd):
        """ Move wrt dither axis."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords['dither'].values[0]

        if 'pixels' in cmdKeys:
            fact = float(self.actor.config.get('slit', 'pix_to_mm').split(',')[1])
        elif 'microns' in cmdKeys:
            fact = 0.001
        else:
            fact = 1

        dither_axis = np.array([float(val) for val in self.actor.config.get('slit', 'dither_axis').split(',')])
        coords = dither_axis * fact * shift
        reference = 'relative'

        self.controller.substates.move(cmd, reference=reference, coords=coords)
        self.controller.generate(cmd)

    @blocking
    def shift(self, cmd):
        """ Move wrt shift axis."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords['shift'].values[0]

        if 'pixels' in cmdKeys:
            fact = float(self.actor.config.get('slit', 'pix_to_mm').split(',')[0])
        elif 'microns' in cmdKeys:
            fact = 0.001
        else:
            fact = 1

        shift_axis = np.array([float(val) for val in self.actor.config.get('slit', 'shift_axis').split(',')])
        coords = shift_axis * fact * shift
        reference = 'relative'

        self.controller.substates.move(cmd, reference=reference, coords=coords)
        self.controller.generate(cmd)

    @threaded
    def getSystem(self, cmd):
        """ Return system coordinate value position (Work or Tool)"""

        cmdKeys = cmd.cmd.keywords
        if 'work' in cmdKeys:
            system = 'Work'
        elif 'tool' in cmdKeys:
            system = 'Tool'
        else:
            system = 'Base'

        self.controller.getSystem(cmd, system)
        cmd.finish()

    @threaded
    def setSystem(self, cmd):
        """ set new system coordinate value position (Work or Tool)"""

        cmdKeys = cmd.cmd.keywords

        if 'work' in cmdKeys:
            system, vec = ('Work', self.controller.workSystem)
        else:
            system, vec = ('Tool', self.controller.toolSystem)

        coords = [cmdKeys[coord].values[0] if coord in cmdKeys else vec[i] for i, coord in enumerate(self.coordsName)]

        try:
            self.controller.setSystem(system, coords)
            self.controller.getSystem(cmd, system)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.generate(cmd)

    @threaded
    def motionEnable(self, cmd):
        """ Enable hexapod actuators"""
        try:
            self.controller.motionEnable(cmd=cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.generate(cmd)

    @threaded
    def motionDisable(self, cmd):
        """ Disable hexapod actuators"""
        try:
            self.controller.motionDisable(cmd=cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.generate(cmd)

    def abort(self, cmd):
        """ Stop current motion."""
        self.controller.doAbort(cmd)
        cmd.finish("text='motion aborted'")

    def convert(self, cmd):
        """ Convert measure in the slit coordinate system to the world coordinate"""

        cmdKeys = cmd.cmd.keywords
        coords = [cmdKeys[coord].values[0] for coord in self.coordsName]
        coordsWorld = self.controller.convertToWorld(coords)
        cmd.finish('system=%s' % ','.join(['%.5f' % coord for coord in coordsWorld]))

    @singleShot
    def stop(self, cmd):
        """ stop current motion, save hexapod position, power off hxp controller and disconnect"""
        self.controller.substates.shutdown()
        self.actor.disconnect('slit', cmd=cmd)

        cmd.inform('text="powering down hxp controller ..."')
        self.actor.ownCall(cmd, cmdStr='power off=slit', failMsg='failed to power off hexapod controller')

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """ power on hxp controller, connect slit controller, and init"""
        cmdKeys = cmd.cmd.keywords
        mode = self.actor.config.get('slit', 'mode')
        host = self.actor.config.get('slit', 'host')
        port = self.actor.config.get('slit', 'port')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        skipHoming = '' if 'fullInit' in cmdKeys else 'skipHoming'

        if not serverIsUp(host=host, port=port):
            cmd.inform('text="powering up hxp controller ..."')
            self.actor.ownCall(cmd, cmdStr='power on=slit', failMsg='failed to power on hexapod controller')
            waitForTcpServer(host=host, port=port, cmd=cmd, mode=mode)

        self.actor.connect('slit', cmd=cmd, mode=mode)

        cmd.inform('text="slit %s ..."' % ('init from saved position' if skipHoming else 'fullInit'))
        self.actor.ownCall(cmd, cmdStr='slit init %s' % skipHoming, failMsg='failed to init slit')

        self.controller.generate(cmd)
