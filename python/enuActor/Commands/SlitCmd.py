#!/usr/bin/env python

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class SlitCmd(object):
    coordsName = ['X', 'Y', 'Z', 'U', 'V', 'W']

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.name = 'slit'

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('slit', 'ping', self.ping),
            ('slit', 'status', self.status),
            ('slit', 'init [@(skipHoming)]', self.initialise),
            ('slit', 'abort', self.abort),
            ('slit', 'enable', self.motionEnable),
            ('slit', 'disable', self.motionDisable),
            ('slit', 'shutdown', self.shutdown),
            ('slit', '@(get) @(work|tool|base)', self.getSystem),
            ('slit', '@(set) @(work|tool) [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.setSystem),
            ('slit', 'move home', self.goHome),
            ('slit', 'move absolute <X> <Y> <Z> <U> <V> <W>', self.moveTo),
            ('slit', 'move relative [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.moveTo),
            ('slit', '<focus> [@(microns)]', self.focus),
            ('slit', '<dither> [@(pixels|microns)]', self.dither),
            ('slit', '<shift> [@(pixels|microns)]', self.shift),
            ('slit', 'convert <X> <Y> <Z> <U> <V> <W>', self.convert),
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
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name.upper()))

    @threaded
    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish('text="%s controller Present and (probably) well"' % self.name)

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""
        self.controller.generate(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise Slit, call fsm startInit event """
        doHome = 'skipHoming' not in cmd.cmd.keywords

        self.controller.substates.init(cmd=cmd, doHome=doHome)
        self.controller.generate(cmd)

    @threaded
    def moveTo(self, cmd):
        """ Move to (X, Y, Z, U, V, W) rel. to home if absolute specified\
                else if relative then incremental move. NB: In relative move parameters are optional.
        """
        cmdKeys = cmd.cmd.keywords
        reference = 'absolute' if 'absolute' in cmdKeys else 'relative'
        coords = [cmdKeys[coord].values[0] if coord in cmdKeys else 0.0 for coord in self.coordsName]

        self.controller.substates.move(cmd=cmd,
                                       reference=reference,
                                       coords=coords)

        self.controller.generate(cmd)

    @threaded
    def goHome(self, cmd):
        """   Go to home related to work : [0,0,0,0,0,0] """
        self.controller.substates.move(cmd=cmd,
                                       reference='absolute',
                                       coords=6 * [0.])

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

    @threaded
    def focus(self, cmd):
        """ Move wrt focus axis."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords['focus'].values[0]

        fact = 0.001 if 'microns' in cmdKeys else 1
        focus_axis = np.array([float(val) for val in self.actor.config.get('slit', 'focus_axis').split(',')])

        coords = focus_axis * fact * shift

        self.controller.substates.move(cmd=cmd,
                                       reference='relative',
                                       coords=coords)

        self.controller.generate(cmd)

    @threaded
    def dither(self, cmd):
        """ Move wrt dither axis."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords['dither'].values[0]

        if 'pixels' in cmdKeys:
            fact = float(self.actor.config.get('slit', 'pix_to_mm'))
        elif 'microns' in cmdKeys:
            fact = 0.001
        else:
            fact = 1

        dither_axis = np.array([float(val) for val in self.actor.config.get('slit', 'dither_axis').split(',')])

        coords = dither_axis * fact * shift

        self.controller.substates.move(cmd=cmd,
                                       reference='relative',
                                       coords=coords)

        self.controller.generate(cmd)

    @threaded
    def shift(self, cmd):
        """ Move wrt shift axis."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords['shift'].values[0]

        if 'pixels' in cmdKeys:
            fact = float(self.actor.config.get('slit', 'pix_to_mm'))
        elif 'microns' in cmdKeys:
            fact = 0.001
        else:
            fact = 1

        shift_axis = np.array([float(val) for val in self.actor.config.get('slit', 'shift_axis').split(',')])

        coords = shift_axis * fact * shift

        self.controller.substates.move(cmd=cmd,
                                       reference='relative',
                                       coords=coords)
        self.controller.generate(cmd)

    @threaded
    def shutdown(self, cmd):
        """ save hexapod position, turn power off and disconnect"""
        self.controller.substates.shutdown(cmd=cmd)
        cmdVar = self.actor.cmdr.call(actor=self.actor.name,
                                      cmdStr='power off=slit',
                                      forUserCmd=cmd,
                                      timeLim=15)
        if cmdVar.didFail:
            raise RuntimeError('failed to power off hexapod controller')

        self.controller.disconnect()
        cmd.finish()

    def abort(self, cmd):
        """ Stop current motion."""

        try:
            self.controller.abort(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.generate(cmd)
        cmd.finish()

    def convert(self, cmd):
        """ Convert measure in the slit coordinate system to the world coordinate"""

        cmdKeys = cmd.cmd.keywords
        coords = [cmdKeys[coord].values[0] for coord in self.coordsName]
        coordsWorld = self.controller.convertToWorld(coords)
        cmd.finish('system=%s' % ','.join(['%.5f' % coord for coord in coordsWorld]))
