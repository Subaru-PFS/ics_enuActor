#!/usr/bin/env python

import subprocess

import opscore.protocols.keys as keys
import opscore.protocols.types as types
import sys
from enuActor.utils.wrap import threaded
from enuActor.fysom import FysomError

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
            ('slit', 'halt', self.halt),
            ('slit', 'shutdown', self.shutdown),
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
        cmd.inform('version=%s' % subprocess.check_output(["git", "describe"]))
        cmd.finish("text='Present and (probably) well'")

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """

        try:
            self.controller.fsm.startInit(cmd=cmd)

        except FysomError as e:
            cmd.warn("text='%s  %s'" % (self.name.upper(),
                                        self.controller.formatException(e, sys.exc_info()[2])))

        self.status(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"

        try:
            self.controller.fsm.changeMode(cmd=cmd, mode=mode)

        except FysomError as e:
            cmd.warn("text='%s  %s'" % (self.name.upper(),
                                        self.controller.formatException(e, sys.exc_info()[2])))

        self.status(cmd)

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

        self.status(cmd)

    @threaded
    def goHome(self, cmd):
        """    # Go to home related to work : [0,0,0,0,0,0]
        """
        self.controller.moveTo(cmd, "absolute", [0.0] * 6)

        self.status(cmd)

    @threaded
    def getSystem(self, cmd, doFinish=True):
        """ Return system coordinate value position (Home or Tool)
        """
        cmdKeys = cmd.cmd.keywords
        system, keyword = ("Work", "slitHome") if "home" in cmdKeys else ("Tool", "slitTool")

        ender = cmd.finish if doFinish else cmd.inform
        nender = cmd.fail if doFinish else cmd.warn
        try:
            ret = self.controller.getSystem(system)
            ender("%s=%s" % (keyword, ','.join(["%.5f" % p for p in ret])))
        except Exception as e:
            nender("text='%s get %s failed %s'" % (self.name.upper(), system,
                                                   self.controller.formatException(e, sys.exc_info()[2])))


    @threaded
    def setSystem(self, cmd):
        """ set new system coordinate value position (Home or Tool)
        """

        cmdKeys = cmd.cmd.keywords
        system, vec = ("Work", self.controller.home) if "home" in cmdKeys else ("Tool", self.controller.tool_value)

        posCoord = [cmdKeys[coord].values[0] if coord in cmdKeys else vec[i] for i, coord in
                    enumerate(['X', 'Y', 'Z', 'U', 'V', 'W'])]

        try:
            self.controller.setSystem(system, posCoord)
            self.getSystem(cmd, doFinish=False)
        except Exception as e:
            cmd.warn("text='%s set %s failed %s'" % (self.name.upper(), system,
                                                     self.controller.formatException(e, sys.exc_info()[2])))

        self.status(cmd)

    @threaded
    def shutdown(self, cmd):
        """ Not implemented yet. It should stop movement.
        """
        try:
            self.controller.shutdown(cmd)
        except Exception as e:
            cmd.warn("text='%s shutdown failed %s'" % (self.name.upper(),
                                                       self.controller.formatException(e, sys.exc_info()[2])))
        self.status(cmd)

        # pdu should do something at this point

    def halt(self, cmd):
        """ Not implemented yet. It should stop movement.
        """
        cmd.finish()

    @threaded
    def goDither(self, cmd):
        """ Move along dither.
        """

        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("dither", pix)

        self.controller.moveTo(cmd, 'relative', posCoord)

        self.status(cmd)

    @threaded
    def goFocus(self, cmd):
        """ Move along focus.
        """

        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("focus", pix)

        self.controller.moveTo(cmd, 'relative', posCoord)

        self.status(cmd)

    def convert(self, cmd):
        """ Convert measure in the slit coordinate system to the world coordinate
        """
        cmdKeys = cmd.cmd.keywords
        posCoord = [cmdKeys[coord].values[0] for coord in ['X', 'Y', 'Z', 'U', 'V', 'W']]

        cmd.finish("system=%s" % str(self.controller.convertToWorld(posCoord)))
