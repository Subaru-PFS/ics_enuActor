#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
import sys
from enuActor.Devices.Error import CommErr, DeviceErr
from enuActor.MyFSM import FysomError

class RexmCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('rexm', 'status', self.status),
            ('rexm', '@(medium|low)', self.switch),
            ('rexm', 'status', self.status),
            ('rexm', 'SetHome CURRENT', self.setHomeCurrent),
            ('rexm', 'SetHome <X>', self.setHome),
            ('rexm', 'GetHome', self.getHome),
            ('rexm', 'GoHome', self.goHome),
            ('rexm', 'MoveTo <X>', self.moveTo),
            ('rexm', 'start [@(operation|simulation)]', self.set_mode),
            ('rexm', '@(off|load|busy|idle|SafeStop|fail)', self.set_state),
            ('rexm', 'init', self.init),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary(
                "rexm_rexm", (1, 1),
                keys.Key("X", types.Float(), help="encode value "),
                                        )

    def init(self, cmd):
        self.actor.rexm.initialise()

    def status(self, cmd):
        try:
            status = self.actor.rexm.getStatus()
            cmd.inform("text='{}'".format(status))
        except AttributeError as e:
            cmd.error("text='rexm did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: %s'" % sys.exc_info()[0])

    def getHome(self, cmd):
        try:
            homePosition = self.actor.rexm.getHome()
            self.actor.rexm.finish("Home position : %s" % homePosition)
        except Exception, e:
            cmd.error("text= %s" % e)

    def setHome(self, cmd):
        X = cmd.cmd.keywords["X"].values[0]
        try:
            self.actor.rexm.setHome(X)
        except Exception, e:
            cmd.error("text= '%s'" % e)
        else:
            self.actor.rexm.finish("setHome done successfully!")

    def setHomeCurrent(self, cmd):
        try:
            self.actor.rexm.setHome()
        except Exception, e:
            cmd.error("text= '%s'" % e)
        else:
            self.actor.rexm.finish("setHome done successfully!")

    def goHome(self, cmd):
        try:
            self.actor.rexm.moveTo()
        except Exception, e:
            cmd.error("text= '%s'" % e)
        else:
            self.actor.rexm.finish("goHome done successfully !!")

    def switch(self, cmd):
        resolution = cmd.cmd.keywords[0].name
        try:
            self.actor.rexm.switch(resolution)
        except Exception, e:
            self.actor.rexm.error("text= '%s'" % e)
        else:
            self.actor.rexm.finish("text= 'moveTo done successfully !!'")

    def moveTo(self, cmd):
        X = cmd.cmd.keywords["X"].values[0]
        try:
            self.actor.rexm.moveTo(X)
        except Exception, e:
            self.actor.rexm.error("text= '%s'" % e)
        else:
            self.actor.rexm.finish("text= 'moveTo done successfully !!'")

    def set_mode(self, cmd):
        name = cmd.cmd.keywords[-1].name
        if name.lower() in ['start','operation']:
            mode = 'operation'
        elif name.lower() == 'simulation':
            mode = 'simulated'
        else:
            cmd.error("text='unknow operation %s'" % name)

        try:
            self.actor.rexm.change_mode(mode)
        except CommErr as e:
            cmd.error("text='%s'" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))
        else:
            cmd.inform("text='rexm mode %s enabled'" % mode)

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.rexm.fsm, state)()
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text='%s'" % e)



