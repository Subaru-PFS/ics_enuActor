#!/usr/bin/env python

import sys
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
from enuActor.MyFSM import FysomError
import enuActor.Devices.Error as Error

class EnuCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('status', '', self.status),
            ('start', '', self.start),
            ('SaveConfig', '', self.saveCfg),
            ('@(off|load|busy|idle|SafeStop|fail)', '', self.set_state),
            ('init', '', self.init),
            ('ping', '', self.ping),
             ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("enu_enu", (1, 1),
                                        )

    def saveCfg(self, cmd):
        """Save session data into config file (device_parameter.cfg)

        """
        dir = None
        try:
            dir = self.actor.enu.saveConfig()
        except Exception as e:
            self.actor.enu.error("Cfg file not saved. Err:%s" % e)
        else:
            self.actor.enu.inform("Cfg file saved into: %s" % dir)

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Enu Actor: o/'")

    def init(self, cmd):
        """ Initialise Enu device

        """
        self.actor.enu.initialise()

    def start(self, cmd):
        """ Start and initialise Enu actor"""
        self.actor.enu.startUp()
        try:
            self.actor.enu.initialise()
        except Error.CfgFileErr, e:
            self.actor.enu.inform(e)
        else:
            self.actor.enu.finish("start operation done successfully!")

    def set_state(self, cmd):
        """ Change current Enu state to BUSY, IDLE, LOADED, ...

        """
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.enu.fsm, state)()
        except AttributeError as e:
            cmd.error("text='Enu did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text='%s'" % e)

    def status(self, cmd):
        """Report camera status and actor version. """
        self.actor.sendVersionKey(cmd)
        try:
            self.actor.enu.inform("status:%s" % self.actor.enu.getStatus())
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))

