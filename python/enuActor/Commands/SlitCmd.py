#!/usr/bin/env python

import subprocess


import opscore.protocols.keys as keys
import opscore.protocols.types as types

from enuActor.Controllers.wrap import threaded


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
            ('slit', 'mode [@(operation|simulation)]', self.changeMode),
            ('slit', 'get [@(home|tool)]', self.getSystem),
            ('slit', 'set [@(home|tool)] [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.setSystem),
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
            raise RuntimeError('%s controller is not connected.' % (self.name))

    @threaded
    def ping(self, cmd):
        """Query the actor for liveness/happiness."""
        cmd.inform('version=%s' % subprocess.check_output(["git", "describe"]))
        cmd.finish("text='Present and (probably) well'")

    @threaded
    def status(self, cmd):
        """Report state, mode, position"""

        [ok, ret] = self.controller.getInfo()
        talk = cmd.inform if ok == 0 else cmd.warn
        talk("slitInfo='%s'" % ret)

        ok, ret = self.controller.getStatus(cmd)
        ender = cmd.finish if ok else cmd.fail
        ender('slit=%s' % ret)

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        try:
            self.controller.fsm.startInit(cmd=cmd)
        except Exception as e:
            cmd.warn('text="failed to initialise for %s: %s"' % (self.name, e))

        self.status(cmd)

    @threaded
    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        try:
            self.controller.fsm.changeMode(cmd=cmd, mode=mode)
        except Exception as e:
            cmd.warn('text="failed to change mode for %s: %s"' % (self.name, e))

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
        print posCoord
        ok, ret = self.controller.moveTo(cmd, mode, posCoord)
        if ok:
            cmd.inform("text='move ok'")
        else:
            cmd.warn("text='%s" % ret)

        self.status(cmd)

    @threaded
    def goHome(self, cmd):
        """    # Go to home related to work : [0,0,0,0,0,0]
        """

        ok, ret = self.controller.moveTo(cmd, "absolute", [0.0] * 6)
        if ok:
            cmd.inform("text='move ok'")
        else:
            cmd.warn("text='%s" % ret)

        self.status(cmd)

    @threaded
    def getSystem(self, cmd, doFinish=True):
        """ Return system coordinate value position (Home or Tool)
        """
        cmdKeys = cmd.cmd.keywords
        system, keyword = ("Work", "slitHome") if "home" in cmdKeys else ("Tool", "slitTool")

        ender = cmd.finish if doFinish else cmd.inform
        nender = cmd.fail if doFinish else cmd.warn
        ok, ret = self.controller.getSystem(system)
        if ok:
            ender("%s=%s" % (keyword, ','.join(["%.5f" % p for p in ret])))
        else:
            nender("text='get %s failed : %s" % (system, ret))

    @threaded
    def setSystem(self, cmd):
        """ set new system coordinate value position (Home or Tool)
        """

        cmdKeys = cmd.cmd.keywords
        system, vec = ("Work", self.controller.home) if "home" in cmdKeys else ("Tool", self.controller.tool_value)

        posCoord = [cmdKeys[coord].values[0] if coord in cmdKeys else vec[i] for i, coord in
                    enumerate(['X', 'Y', 'Z', 'U', 'V', 'W'])]

        ok, ret = self.controller.setSystem(system, posCoord)
        if ok:
            self.getSystem(cmd, doFinish=False)
        else:
            cmd.warn("text='set new system failed : %s" % ret)
        self.status(cmd)


    @threaded
    def shutdown(self, cmd):
        """ Not implemented yet. It should stop movement.
        """
        ok, ret = self.controller.shutdown(cmd)
        if ok:
            cmd.inform("text='slit controller is now offline'")
        else:
            cmd.warn("text='%s" % ret)
        self.status(cmd)
        # pdu should do something at this point

    @threaded
    def halt(self, cmd):
        """ Not implemented yet. It should stop movement.
        """
        cmd.finish()
        # if self.controller.fsm.current in ["INIT", "IDLE"]:
        #     if self.controller.shutdown(cmd):
        #         cmd.finish("text='Go to sleep'")
        #         self.controller.fsm.shutdown()
        #     else:
        #         self.controller.fsm.cmdFailed()
        #
        # else:
        #     cmd.fail("text='It's impossible to halt system from current state: %s'" % self.actor.controllers[
        #         'slit'].fsm.current)
        #     self.controller.fsm.cmdFailed()

    @threaded
    def goDither(self, cmd):
        """ Move along dither.
        """

        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("dither", pix)

        ok, ret = self.controller.moveTo(cmd, 'relative', posCoord)
        if ok:
            cmd.inform("text='move ok'")
        else:
            cmd.warn("text='%s" % ret)
        self.status(cmd)

    @threaded
    def goFocus(self, cmd):
        """ Move along focus.
        """

        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("focus", pix)

        ok, ret = self.controller.moveTo(cmd, 'relative', posCoord)
        if ok:
            cmd.inform("text='move ok'")
        else:
            cmd.warn("text='%s" % ret)
        self.status(cmd)



    def convert(self, cmd):
        """ Convert measure in the slit coordinate system to the world coordinate
        """
        cmdKeys = cmd.cmd.keywords
        posCoord = [cmdKeys[coord].values[0] for coord in ['X', 'Y', 'Z', 'U', 'V', 'W']]

        cmd.finish("system=%s" % str(self.controller.convertToWorld(posCoord)))
