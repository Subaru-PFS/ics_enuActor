#!/usr/bin/env python

import subprocess

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from wrap import threaded


class HxpCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.name = "hxp"

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
            ('slit', 'mode [@(operation|simulation)]', self.changeMode),
            ('slit', 'get home', self.getHome),
            ('slit', 'set home <X> <Y> <Z> <U> <V> <W>', self.setHome),
            ('slit', 'set home', self.setHomeCurrent),
            ('slit', 'move home', self.goHome),
            ('slit', 'move absolute <X> <Y> <Z> <U> <V> <W>', self.moveTo),
            ('slit', 'move relative [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.moveTo),
            ('slit', 'focus <pix>', self.goFocus),
            ('slit', 'dither <pix>', self.goDither),

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

    @threaded
    def ping(self, cmd):
        """Query the actor for liveness/happiness."""
        cmd.inform('version=%s' % subprocess.check_output(["git", "describe"]))
        cmd.finish("text='Present and (probably) well'")

    @threaded
    def status(self, cmd, doFinish=True):
        """Report state, mode, position"""
        ender = cmd.finish if doFinish else cmd.inform
        cmd.inform('state=%s' % self.actor.controllers['hxp'].fsm.current)
        cmd.inform('mode=%s' % self.actor.controllers['hxp'].currMode)
        ok, pos = self.actor.controllers['hxp'].getPosition(cmd)
        if ok:
            ender('position=%s' % ','.join(["%.2f" % p for p in pos]))
        else:
            self.actor.controllers['hxp'].fsm.cmdFailed()

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        if self.actor.controllers['hxp'].initialise(cmd):
            self.actor.controllers['hxp'].fsm.initOk()
            self.status(cmd)
        else:
            self.actor.controllers['hxp'].fsm.initFailed()

    @threaded
    def changeMode(self, cmd, doFinish=True):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        self.actor.controllers['hxp'].fsm.changeMode()
        if self.actor.controllers['hxp'].changeMode(cmd, mode):
            self.status(cmd, doFinish)

    @threaded
    def getHome(self, cmd):
        """ Return Home value position
        """
        if not self.actor.controllers['hxp'].getHome(cmd):
            self.actor.controllers['hxp'].fsm.cmdFailed()

    @threaded
    def setHome(self, cmd):
        """ Change Home value position
        """
        X = cmd.cmd.keywords["X"].values[0]
        Y = cmd.cmd.keywords["Y"].values[0]
        Z = cmd.cmd.keywords["Z"].values[0]
        U = cmd.cmd.keywords["U"].values[0]
        V = cmd.cmd.keywords["V"].values[0]
        W = cmd.cmd.keywords["W"].values[0]
        if self.actor.controllers['hxp'].setHome(cmd, [X, Y, Z, U, V, W]):
            cmd.finish()
        else:
            self.actor.controllers['hxp'].fsm.cmdFailed()

    @threaded
    def setHomeCurrent(self, cmd):
        """ Change Home value position according to current
        """
        if self.actor.controllers['hxp'].setHome(cmd):
            cmd.finish()
        else:
            self.actor.controllers['hxp'].fsm.cmdFailed()

    def goHome(self, cmd):
        self.actor.controllers['hxp'].fsm.getBusy()
        if not self.actor.controllers['hxp'].moveTo(cmd, 'absolute'):
            self.actor.controllers['hxp'].fsm.cmdFailed()
        else:
            self.actor.controllers['hxp'].fsm.getIdle()
            self.status(cmd)

    @threaded
    def moveTo(self, cmd):
        """ Move to (X, Y, Z, U, V, W) rel. to home if absolute specified\
                else if relative then incremental move. NB: In relative move parameters are optional.
        """
        cmdKeys = cmd.cmd.keywords
        mode = "absolute" if "absolute" in cmdKeys else "relative"
        posCoord = [cmd.cmd.keywords[coord].values[0] if coord in cmdKeys else 0 for coord in
                    ['X', 'Y', 'Z', 'U', 'V', 'W']]
        self.actor.controllers['hxp'].fsm.getBusy()
        if not self.actor.controllers['hxp'].moveTo(cmd, mode, posCoord):
            self.actor.controllers['hxp'].fsm.cmdFailed()
        else:
            self.actor.controllers['hxp'].fsm.getIdle()
            self.status(cmd)

    @threaded
    def halt(self, cmd):
        """ Not implemented yet. It should stop movement.
        """
        if self.actor.controllers['hxp'].fsm.current in ["INIT", "IDLE"]:
            if self.actor.controllers['hxp'].shutdown(cmd):
                cmd.finish("text='Go to sleep'")
                self.actor.controllers['hxp'].fsm.shutdown()
            else:
                self.actor.controllers['hxp'].fsm.cmdFailed()

        else:
            cmd.fail("text='It's impossible to halt system from current state: %s'" % self.actor.controllers[
                'hxp'].fsm.current)
            self.actor.controllers['hxp'].fsm.cmdFailed()

    @threaded
    def goDither(self, cmd):
        """ Move along dither.
        """
        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.actor.controllers['hxp'].compute("dither", pix)
        self.actor.controllers['hxp'].fsm.getBusy()
        if not self.actor.controllers['hxp'].moveTo(cmd, 'relative', posCoord):
            self.actor.controllers['hxp'].fsm.cmdFailed()
        else:
            self.actor.controllers['hxp'].fsm.getIdle()
            self.status(cmd)

    @threaded
    def goFocus(self, cmd):
        """ Move along focus.
        """
        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.actor.controllers['hxp'].compute("focus", pix)

        self.actor.controllers['hxp'].fsm.getBusy()
        if not self.actor.controllers['hxp'].moveTo(cmd, 'relative', posCoord):
            self.actor.controllers['hxp'].fsm.cmdFailed()
        else:
            self.actor.controllers['hxp'].fsm.getIdle()
            self.status(cmd)
