#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
import sys
from enuActor.Devices.Error import CommErr, DeviceErr
from enuActor.MyFSM import FysomError

class TemperatureCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('temperature', 'status', self.status),
            ('temperature', 'read <sensorId>', self.read),
            ('temperature', 'start [@(operation|simulation)]', self.set_mode),
            ('temperature', '@(off|load|busy|idle|SafeStop|fail)', self.set_state),
            ('temperature', 'init', self.init),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary(
                "temperature_temperature", (1, 1),
                keys.Key("sensorId", types.Int(), help="sensor Identity"),
                                        )

    def init(self, cmd):
        self.actor.temperature.initialise()

    def read(self, cmd):
        sensorId = cmd.cmd.keywords["sensorId"].values[0]
        value = self.actor.temperature.read(sensorId)
        cmd.inform("text='Temperature of sensor %s: %s'" % (sensorId, value))

    def status(self, cmd):
        try:
            status = self.actor.temperature.getStatus()
            cmd.inform("text='{}'".format(status))
        except AttributeError as e:
            cmd.error("text='Temperature did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: %s'" % sys.exc_info()[0])

    def set_mode(self, cmd):
        name = cmd.cmd.keywords[-1].name
        if name in ['start','operation']:
            mode = 'operation'
        elif name == 'simulation':
            mode = 'simulated'
        else:
            cmd.error("text='unknow operation %s'" % name)

        try:
            self.actor.temperature.change_mode(mode)
        except CommErr as e:
            cmd.error("text='%s'" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))
        else:
            cmd.inform("text='Temperature mode %s enabled'" % mode)

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.temperature.fsm, state)()
        except AttributeError as e:
            cmd.error("text='Bia did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text='%s'" % e)



