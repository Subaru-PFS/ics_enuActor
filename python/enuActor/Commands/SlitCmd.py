#!/usr/bin/env python

import subprocess

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from wrap import threaded


def degToRad(deg):
    return 2 * np.pi * deg / 360


def convertToWorld(array):
    [X, Y, Z, U, V, W] = array
    x = X * np.cos(degToRad(W)) - Y * np.sin(degToRad(W))
    y = X * np.sin(degToRad(W)) + Y * np.cos(degToRad(W))
    return [x, y, float(Z), float(U), float(V), float(W)]


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
            ('slit', 'mode [@(operation|simulation)]', self.changeMode),
            ('slit', 'get <system>', self.getSystem),
            ('slit', 'set <system> <X> <Y> <Z> <U> <V> <W>', self.setSystem),
            ('slit', 'set home', self.setHomeCurrent),
            ('slit', 'move home', self.goHome),
            ('slit', 'move absolute <X> <Y> <Z> <U> <V> <W>', self.moveTo),
            ('slit', 'move relative [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]', self.moveTo),
            ('slit', 'focus <pix>', self.goFocus),
            ('slit', 'dither <pix>', self.goDither),
            ('slit', 'ack', self.ack),
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
                                        keys.Key("system", types.String(), help="coordinate system"),
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
    def status(self, cmd, doFinish=True):
        """Report state, mode, position"""

        ender = cmd.finish if doFinish else cmd.inform
        ok, pos = self.controller.getPosition(cmd)
        if not ok:
            self.controller.fsm.cmdFailed()
        ender('slit=%s,%s,%s' % (
            self.controller.fsm.current, self.controller.currMode, ','.join(["%.4f" % p for p in pos])))

    @threaded
    def initialise(self, cmd):
        """Initialise Device LOADED -> INIT
        """
        if self.controller.initialise(cmd):
            self.controller.fsm.initOk()
            self.status(cmd)
        else:
            self.controller.fsm.initFailed()

    @threaded
    def changeMode(self, cmd, doFinish=True):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords
        mode = "simulation" if "simulation" in cmdKeys else "operation"
        self.controller.fsm.changeMode()
        if self.controller.changeMode(cmd, mode):
            self.status(cmd, doFinish)

    @threaded
    def getSystem(self, cmd):
        """ Return Home value position
        """
        system = cmd.cmd.keywords["system"].values[0]
        if not self.controller.getSystem(cmd, system):
            pass
            # self.controller.fsm.cmdFailed()

    @threaded
    def setSystem(self, cmd):
        """ Change Home value position
        """
        X = cmd.cmd.keywords["X"].values[0]
        Y = cmd.cmd.keywords["Y"].values[0]
        Z = cmd.cmd.keywords["Z"].values[0]
        U = cmd.cmd.keywords["U"].values[0]
        V = cmd.cmd.keywords["V"].values[0]
        W = cmd.cmd.keywords["W"].values[0]
        system = cmd.cmd.keywords["system"].values[0]

        if self.controller.setSystem(cmd, system, [X, Y, Z, U, V, W]):
            cmd.finish()
        else:
            pass

    @threaded
    def convert(self, cmd):
        """ Change Home value position
        """
        X = cmd.cmd.keywords["X"].values[0]
        Y = cmd.cmd.keywords["Y"].values[0]
        Z = cmd.cmd.keywords["Z"].values[0]
        U = cmd.cmd.keywords["U"].values[0]
        V = cmd.cmd.keywords["V"].values[0]
        W = cmd.cmd.keywords["W"].values[0]
        cmd.finish("system=%s" % str(convertToWorld([X, Y, Z, U, V, W])))

    # @threaded
    # def getHome(self, cmd):
    #     """ Return Home value position
    #     """
    #     if not self.controller.getHome(cmd):
    #         self.controller.fsm.cmdFailed()
    #
    # @threaded
    # def setHome(self, cmd):
    #     """ Change Home value position
    #     """
    #     X = cmd.cmd.keywords["X"].values[0]
    #     Y = cmd.cmd.keywords["Y"].values[0]
    #     Z = cmd.cmd.keywords["Z"].values[0]
    #     U = cmd.cmd.keywords["U"].values[0]
    #     V = cmd.cmd.keywords["V"].values[0]
    #     W = cmd.cmd.keywords["W"].values[0]
    #     if self.controller.setHome(cmd, [X, Y, Z, U, V, W]):
    #         cmd.finish()
    #     else:
    #         self.controller.fsm.cmdFailed()

    @threaded
    def setHomeCurrent(self, cmd):
        """ Change Home value position according to current
        """
        if self.controller.setHome(cmd):
            cmd.finish()
        else:
            self.controller.fsm.cmdFailed()

    def goHome(self, cmd):
        self.controller.fsm.getBusy()
        if not self.controller.moveTo(cmd, 'absolute'):
            self.controller.fsm.cmdFailed()
        else:
            self.controller.fsm.getIdle()
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
        self.controller.fsm.getBusy()
        if not self.controller.moveTo(cmd, mode, posCoord):
            self.controller.fsm.cmdFailed()
        else:
            self.controller.fsm.getIdle()
            self.status(cmd)

    @threaded
    def halt(self, cmd):
        """ Not implemented yet. It should stop movement.
        """
        if self.controller.fsm.current in ["INIT", "IDLE"]:
            if self.controller.shutdown(cmd):
                cmd.finish("text='Go to sleep'")
                self.controller.fsm.shutdown()
            else:
                self.controller.fsm.cmdFailed()

        else:
            cmd.fail("text='It's impossible to halt system from current state: %s'" % self.actor.controllers[
                'slit'].fsm.current)
            self.controller.fsm.cmdFailed()

    @threaded
    def goDither(self, cmd):
        """ Move along dither.
        """
        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("dither", pix)
        self.controller.fsm.getBusy()
        if not self.controller.moveTo(cmd, 'relative', posCoord):
            self.controller.fsm.cmdFailed()
        else:
            self.controller.fsm.getIdle()
            self.status(cmd)

    @threaded
    def goFocus(self, cmd):
        """ Move along focus.
        """
        pix = cmd.cmd.keywords["pix"].values[0]
        posCoord = self.controller.compute("focus", pix)

        self.controller.fsm.getBusy()
        if not self.controller.moveTo(cmd, 'relative', posCoord):
            self.controller.fsm.cmdFailed()
        else:
            self.controller.fsm.getIdle()
            self.status(cmd)

    @threaded
    def ack(self, cmd):
        self.controller.fsm.ack()
