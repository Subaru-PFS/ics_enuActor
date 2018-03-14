#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from fysom import FysomError
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
            ('slit', '@(operation|simulation)', self.changeMode),
            ('slit', '@(get) @(home|tool)', self.getSystem),
            ('slit', '@(set) @(home|tool) [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.setSystem),
            ('slit', 'move home', self.goHome),
            ('slit', 'move absolute <X> <Y> <Z> <U> <V> <W>', self.moveTo),
            ('slit', 'move relative [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.moveTo),
            ('slit', 'focus <pix>', self.goFocus),
            ('slit', 'dither <pix>', self.goDither),
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
                                        keys.Key("pix", types.Float(), help="Number of pixel"),
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

        try:
            self.controller.fsm.startInit(cmd=cmd)
        # That transition may not be allowed, see state machine
        except FysomError as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation call fsm changeMode event"""

        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"

        try:
            self.controller.fsm.changeMode(cmd=cmd, mode=mode)
        # That transition may not be allowed, see state machine
        except FysomError as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self.controller.getStatus(cmd)

    @threaded
    def moveTo(self, cmd):
        """ Move to (X, Y, Z, U, V, W) rel. to home if absolute specified\
                else if relative then incremental move. NB: In relative move parameters are optional.
        """
        cmdKeys = cmd.cmd.keywords
        mode = "absolute" if "absolute" in cmdKeys else "relative"
        posCoord = [cmdKeys[coord].values[0] if coord in cmdKeys else 0.0 for coord in
                    ['X', 'Y', 'Z', 'U', 'V', 'W']]

        self.controller.moveTo(cmd, mode, posCoord)

        self.controller.getStatus(cmd)

    @threaded
    def goHome(self, cmd):
        """   Go to home related to work : [0,0,0,0,0,0] """
        self.controller.moveTo(cmd, "absolute", [0.0] * 6)

        self.controller.getStatus(cmd)

    @threaded
    def getSystem(self, cmd):
        """ Return system coordinate value position (Home or Tool)"""

        cmdKeys = cmd.cmd.keywords
        system, keyword = ("Work", "slitHome") if "home" in cmdKeys else ("Tool", "slitTool")

        ret = self.controller.getSystem(system)
        cmd.finish("%s=%s" % (keyword, ','.join(["%.5f" % p for p in ret])))


    @threaded
    def setSystem(self, cmd):
        """ set new system coordinate value position (Home or Tool)"""

        cmdKeys = cmd.cmd.keywords
        coords = ['X', 'Y', 'Z', 'U', 'V', 'W']

        if "home" in cmdKeys:
            system, keyword, vec = ("Work", "slitHome", self.controller.home)
        else:
            system, keyword, vec = ("Tool", "slitTool", self.controller.tool_value)

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
    def goDither(self, cmd):
        """ Move along dither."""

        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("dither", pix)

        self.controller.moveTo(cmd, 'relative', posCoord)

        self.controller.getStatus(cmd)

    @threaded
    def goFocus(self, cmd):
        """ Move along focus."""

        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("focus", pix)

        self.controller.moveTo(cmd, 'relative', posCoord)

        self.controller.getStatus(cmd)

    def convert(self, cmd):
        """ Convert measure in the slit coordinate system to the world coordinate"""

        cmdKeys = cmd.cmd.keywords
        posCoord = [cmdKeys[coord].values[0] for coord in ['X', 'Y', 'Z', 'U', 'V', 'W']]

        cmd.finish("system=%s" % str(self.controller.convertToWorld(posCoord)))
