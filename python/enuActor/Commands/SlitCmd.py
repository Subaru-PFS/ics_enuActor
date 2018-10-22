#!/usr/bin/env python

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class SlitCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.name = "slit"

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('slit', 'ping', self.ping),
            ('slit', 'status', self.status),
            ('slit', 'init', self.initialise),
            ('slit', 'abort', self.abort),
            ('slit', '@(disable|enable)', self.shutdown),
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
        self.keys = keys.KeysDictionary("enu__slit", (1, 1),
                                        keys.Key("X", types.Float(), help="X coordinate"),
                                        keys.Key("Y", types.Float(), help="Y coordinate"),
                                        keys.Key("Z", types.Float(), help="Z coordinate"),
                                        keys.Key("U", types.Float(), help="U coordinate"),
                                        keys.Key("V", types.Float(), help="V coordinate"),
                                        keys.Key("W", types.Float(), help="W coordinate"),
                                        keys.Key("focus", types.Float(), help="move along focus axis"),
                                        keys.Key("dither", types.Float(), help="move along dither axis"),
                                        keys.Key("shift", types.Float(), help="move along shift axis")
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

        cmd.finish("text='%s controller Present and (probably) well'" % self.name)

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise Slit, call fsm startInit event """

        self.controller.substates.init(cmd=cmd)
        self.controller.getStatus(cmd)

    @threaded
    def moveTo(self, cmd):
        """ Move to (X, Y, Z, U, V, W) rel. to home if absolute specified\
                else if relative then incremental move. NB: In relative move parameters are optional.
        """
        cmdKeys = cmd.cmd.keywords
        reference = "absolute" if "absolute" in cmdKeys else "relative"
        allCoords = ['X', 'Y', 'Z', 'U', 'V', 'W']
        coords = [cmdKeys[coord].values[0] if coord in cmdKeys else 0.0 for coord in allCoords]

        self.controller.substates.move(cmd=cmd,
                                       reference=reference,
                                       coords=coords)

        self.controller.getStatus(cmd)

    @threaded
    def goHome(self, cmd):
        """   Go to home related to work : [0,0,0,0,0,0] """
        self.controller.substates.move(cmd=cmd,
                                       reference='absolute',
                                       coords=6 * [0.])

        self.controller.getStatus(cmd)

    @threaded
    def getSystem(self, cmd):
        """ Return system coordinate value position (Work or Tool)"""

        cmdKeys = cmd.cmd.keywords
        if "work" in cmdKeys:
            system, keyword = ("Work", "slitWork")
        elif 'tool' in cmdKeys:
            system, keyword = ("Tool", "slitTool")
        else:
            system, keyword = ("Base", "slitBase")

        ret = self.controller.getSystem(system)
        cmd.finish("%s=%s" % (keyword, ','.join(["%.5f" % p for p in ret])))

    @threaded
    def setSystem(self, cmd):
        """ set new system coordinate value position (Work or Tool)"""

        cmdKeys = cmd.cmd.keywords
        coords = ['X', 'Y', 'Z', 'U', 'V', 'W']

        if "work" in cmdKeys:
            system, keyword, vec = ("Work", "slitWork", self.controller.workSystem)
        else:
            system, keyword, vec = ("Tool", "slitTool", self.controller.toolSystem)

        posCoord = [cmdKeys[coord].values[0] if coord in cmdKeys else vec[i] for i, coord in enumerate(coords)]

        try:
            self.controller.setSystem(system, posCoord)
            ret = self.controller.getSystem(system)
            cmd.inform("%s=%s" % (keyword, ','.join(["%.5f" % p for p in ret])))
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

    @threaded
    def shutdown(self, cmd):
        """ Not implemented yet. It should stop movement."""
        cmdKeys = cmd.cmd.keywords
        enable = True if "enable" in cmdKeys else False
        try:
            self.controller.shutdown(cmd, enable)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

        # pdu should do something at this point

    def abort(self, cmd):
        """ Stop current motion."""

        try:
            self.controller.abort(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

    @threaded
    def focus(self, cmd):
        """ Move along focus."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords["focus"].values[0]

        fact = 0.001 if "microns" in cmdKeys else 1
        focus_axis = np.array([float(val) for val in self.actor.config.get('slit', 'focus_axis').split(',')])

        coords = focus_axis * fact * shift

        self.controller.substates.move(cmd=cmd,
                                       reference='relative',
                                       coords=coords)

        self.controller.getStatus(cmd)

    @threaded
    def dither(self, cmd):
        """ Move along dither."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords["dither"].values[0]

        if "pixels" in cmdKeys:
            fact = float(self.actor.config.get('slit', 'pix_to_mm'))
        elif "microns" in cmdKeys:
            fact = 0.001
        else:
            fact = 1

        dither_axis = np.array([float(val) for val in self.actor.config.get('slit', 'dither_axis').split(',')])

        coords = dither_axis * fact * shift

        self.controller.substates.move(cmd=cmd,
                                       reference='relative',
                                       coords=coords)

        self.controller.getStatus(cmd)

    @threaded
    def shift(self, cmd):
        """ Move along shift."""
        cmdKeys = cmd.cmd.keywords
        shift = cmd.cmd.keywords["shift"].values[0]

        if "pixels" in cmdKeys:
            fact = float(self.actor.config.get('slit', 'pix_to_mm'))
        elif "microns" in cmdKeys:
            fact = 0.001
        else:
            fact = 1

        shift_axis = np.array([float(val) for val in self.actor.config.get('slit', 'shift_axis').split(',')])

        coords = shift_axis * fact * shift

        self.controller.substates.move(cmd=cmd,
                                       reference='relative',
                                       coords=coords)

        self.controller.getStatus(cmd)

    def convert(self, cmd):
        """ Convert measure in the slit coordinate system to the world coordinate"""

        cmdKeys = cmd.cmd.keywords
        posCoord = [cmdKeys[coord].values[0] for coord in ['X', 'Y', 'Z', 'U', 'V', 'W']]

        cmd.finish("system=%s" % str(self.controller.convertToWorld(posCoord)))
