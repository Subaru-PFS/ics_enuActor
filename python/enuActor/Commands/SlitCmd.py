#!/usr/bin/env python

import enuActor.Controllers.slit as slitCtrl
import ics.utils.tcp.utils as tcpUtils
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.utils.threading import threaded, blocking, singleShot


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
            ('slit', '<focus> [@(microns)] [abs]', self.focus),
            ('slit', 'dither [<X>] [<Y>] [@(pixels|microns)] [abs]', self.dither),
            ('slit', '@softwareLimits @(on|off) [@force]', self.hxpSoftwareLimits),
            ('slit', 'linearVerticalMove <expTime> [<pixelRange>]', self.linearVerticalMove),

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
                                        keys.Key('shift', types.Float(), help='move along shift axis'),
                                        keys.Key('expTime', types.Float(), help='expTime'),
                                        keys.Key('pixelRange', types.Float() * (1, 2),
                                                 help='pixels array(start, stop )')
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['slit']
        except KeyError:
            raise RuntimeError('slit controller is not connected.')

    @property
    def connected(self):
        return 'slit' in self.actor.controllers

    def config(self, option):
        return self.actor.actorConfig['slit'][option]

    def status(self, cmd):
        """Report state, mode, position."""

        @threaded
        def thStatus(self, cmd):
            self.controller.generate(cmd)

        if self.connected:
            thStatus(self, cmd=cmd)
        else:
            coords = self.actor.actorData.loadKey('slit')
            cmd.inform('slitFSM=OFF,SHUTDOWN')
            cmd.inform('slit=%s' % ','.join(['%.5f' % p for p in coords]))
            cmd.finish('slitPosition=%s' % slitCtrl.slit.slitPosition(coords, config=self.actor.actorConfig['slit']))

    @blocking
    def initialise(self, cmd):
        """Initialise slit, reload from saved position if skipHoming."""
        doHome = 'skipHoming' not in cmd.cmd.keywords

        self.controller.substates.init(cmd, doHome=doHome)
        self.controller.generate(cmd)

    @blocking
    def moveAbs(self, cmd):
        """Move to (X, Y, Z, U, V, W) in absolute."""
        cmdKeys = cmd.cmd.keywords
        current = self.controller.coords
        coords = [cmdKeys[c].values[0] if c in cmdKeys else current[i] for i, c in enumerate(self.coordsName)]

        self.controller.substates.move(cmd, reference='absolute', coords=coords)
        self.controller.generate(cmd)

    @blocking
    def moveRel(self, cmd):
        """Move to (X, Y, Z, U, V, W) rel. to home."""
        cmdKeys = cmd.cmd.keywords
        coords = [cmdKeys[coord].values[0] if coord in cmdKeys else 0.0 for coord in self.coordsName]

        self.controller.substates.move(cmd, reference='relative', coords=coords)
        self.controller.generate(cmd)

    @blocking
    def goHome(self, cmd):
        """Go to home related to work : [0,0,0,0,0,0]."""
        coords = 6 * [0.]

        self.controller.substates.move(cmd, reference='absolute', coords=coords)
        self.controller.generate(cmd)

    @blocking
    def focus(self, cmd):
        """Move wrt focus axis."""
        cmdKeys = cmd.cmd.keywords
        value = cmd.cmd.keywords['focus'].values[0]
        coeff = 0.001 if 'microns' in cmdKeys else 1
        reference = 'absolute' if 'abs' in cmdKeys else 'relative'
        focus_axis = np.array(self.config('focus_axis'), dtype=bool)

        coords = np.array(self.controller.coords, dtype=float) if reference == 'absolute' else np.zeros(6)
        coords[focus_axis] = coeff * value

        self.controller.substates.move(cmd, reference=reference, coords=coords)
        self.controller.generate(cmd)

    @blocking
    def dither(self, cmd):
        """Move wrt dither axis."""
        ditherXaxis = np.array(self.config('dither_x_axis'), dtype=bool)
        ditherYaxis = np.array(self.config('dither_y_axis'), dtype=bool)
        pix2mm = self.config('pix_to_mm')

        cmdKeys = cmd.cmd.keywords
        reference = 'absolute' if 'abs' in cmdKeys else 'relative'

        if not ('X' in cmdKeys or 'Y' in cmdKeys):
            raise ValueError('X or Y at least needs to be specified')

        coeffX, coeffY = 1, 1
        coeffX, coeffY = pix2mm if 'pixels' in cmdKeys else [coeffX, coeffY]
        coeffX, coeffY = [0.001, 0.001] if 'microns' in cmdKeys else [coeffX, coeffY]

        coords = np.array([c for c in self.controller.coords], dtype=float) if reference == 'absolute' else np.zeros(6)
        coords[ditherXaxis] = coeffX * cmdKeys['X'].values[0] if 'X' in cmdKeys else coords[ditherXaxis]
        coords[ditherYaxis] = coeffY * cmdKeys['Y'].values[0] if 'Y' in cmdKeys else coords[ditherYaxis]

        self.controller.substates.move(cmd, reference=reference, coords=coords)
        self.controller.generate(cmd)

    @threaded
    def getSystem(self, cmd):
        """Return system coordinate value position (Work or Tool)."""
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
        """Set new system coordinate value position (Work or Tool)."""
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
        """Enable hexapod actuators."""
        try:
            self.controller.motionEnable(cmd=cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.generate(cmd)

    @threaded
    def motionDisable(self, cmd):
        """Disable hexapod actuators."""
        try:
            self.controller.motionDisable(cmd=cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.generate(cmd)

    @threaded
    def hxpSoftwareLimits(self, cmd):
        """Activate/deactivate hexapod software limits"""
        cmdKeys = cmd.cmd.keywords

        futureState = 'on' in cmdKeys
        force = 'force' in cmdKeys

        if futureState:
            self.controller.softwareLimitsActivated = futureState
            cmd.inform('text="Hexapod software limits ACTIVATED ...')
        else:
            if force:
                self.controller.softwareLimitsActivated = futureState
                cmd.warn('text="WARNING Hexapod software limits DEACTIVATED, decision is yours...')
            else:
                cmd.warn('text="NOT deactivating hexapod software limits, add force argument to proceed..')

        self.controller.generate(cmd)

    @blocking
    def linearVerticalMove(self, cmd):
        """Move wrt focus axis."""
        cmdKeys = cmd.cmd.keywords

        expTime = cmdKeys['expTime'].values[0]
        pixMin, pixMax = cmdKeys['pixelRange'].values if 'pixelRange' in cmdKeys else [-6, 6]
        ditherXaxis = np.array(self.config('dither_x_axis'), dtype=bool)
        coeffX, coeffY = self.config('pix_to_mm')

        startPosition, endPosition = coeffX * pixMin, coeffX * pixMax

        # calculating speed in mm/s.
        desiredMotion = endPosition - startPosition
        speed = desiredMotion / expTime

        # Making start and end coordinates taking in account acceleration and deceleration.
        startCoords = np.zeros(6)
        endCoords = np.zeros(6)

        realStartPosition = startPosition - self.controller.slitAtSpeedAfter * speed
        realEndPosition = endPosition + self.controller.slidingOvershoot * speed

        startCoords[ditherXaxis] = realStartPosition

        # RELATIVE MOVE so total motion *MUST* include the overshoots on both sides.
        totalMotion = realStartPosition - realEndPosition
        endCoords[ditherXaxis] = totalMotion

        # moving to start position first.
        self.controller.substates.move(cmd, reference='absolute', coords=startCoords)
        self.controller.generate(cmd, doFinish=False)

        try:
            # temporary increasing timeout.
            self.controller.myxps.hangLimit = round(totalMotion / speed) + 10
            self.controller.substates.slide(cmd, speed=speed, coords=endCoords)
            self.controller.generate(cmd)
        finally:
            self.controller.myxps.hangLimit = 45

    def abort(self, cmd):
        """Stop current motion."""
        self.controller.doAbort(cmd)
        cmd.finish("text='motion aborted'")

    def convert(self, cmd):
        """Convert measure in the slit coordinate system to the world coordinate."""
        cmdKeys = cmd.cmd.keywords

        coords = [cmdKeys[coord].values[0] for coord in self.coordsName]
        coordsWorld = self.controller.convertToWorld(coords)
        cmd.finish('system=%s' % ','.join(['%.5f' % coord for coord in coordsWorld]))

    @singleShot
    def stop(self, cmd):
        """Stop current motion, save hexapod position, power off hxp controller and disconnect."""
        self.controller.substates.shutdown()

        self.actor.disconnect('slit', cmd=cmd)
        self.actor.powerSwitch('slit', state='off', cmd=cmd)

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """Power on hxp controller, connect slit controller, and init."""
        cmdKeys = cmd.cmd.keywords

        host, port = self.config('host'), int(self.config('port'))

        mode = self.config('mode')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        doHome = 'fullInit' in cmdKeys

        # if hexapod is turned off or slit controller disconnected.
        if (mode == 'operation' and not tcpUtils.serverIsUp(host, port)) or not self.connected:
            self.actor.startController('slit', cmd=cmd, mode=mode)

        # init is required if LOADED state or if fullInit is specified.
        if self.controller.states.current == 'LOADED' or doHome:
            self.controller.substates.init(cmd, doHome=doHome)

        self.controller.generate(cmd)
