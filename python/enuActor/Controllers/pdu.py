__author__ = 'alefur'

from ics.utils.sps.controllers.pdu import aten


class pdu(aten.pdu):
    """ code shared among ics_utils package."""

    def __init__(self, *args, **kwargs):
        aten.pdu.__init__(self, *args, **kwargs)
