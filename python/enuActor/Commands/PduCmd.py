#!/usr/bin/env python

from importlib import reload

from ics.utils.sps.pdu.commands import PduCmd as Cmd

reload(Cmd)


class PduCmd(Cmd.PduCmd):
    """ code shared among ics_utils package."""

    def __init__(self, actor):
        Cmd.PduCmd.__init__(self, actor)
