__author__ = 'alefur'

from importlib import reload

from ics.utils.sps.pdu.controllers import aten

reload(aten)


class pdu(aten.aten):
    """ code shared among ics_utils package."""

    def __init__(self, *args, **kwargs):
        aten.aten.__init__(self, *args, **kwargs)

    def getStatus(self, cmd):
        """Get envioall ports status.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self.readEnvSensors(cmd)
        aten.aten.getStatus(self, cmd)

    def readEnvSensors(self, cmd):
        """Get temps and humidity reading from the rack."""

        try:
            temps, humidity, NA = self.sendOneCommand('read sensor o01 simple', cmd=cmd).split('\r\n')
            temps = float(temps)
            humidity = float(humidity)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            temps, humidity = 'nan', 'nan'

        cmd.inform(f'rackSensor={float(temps):.2f},{float(humidity):.2f}')
