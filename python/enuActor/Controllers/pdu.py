__author__ = 'alefur'

from importlib import reload

from ics.utils.sps.pdu.controllers import aten

reload(aten)


class pdu(aten.aten):
    """ code shared among ics_utils package."""

    def __init__(self, *args, **kwargs):
        aten.aten.__init__(self, *args, **kwargs)
