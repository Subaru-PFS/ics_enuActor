#!/usr/bin/env python


from ics.utils.sps.controllers.pdu.commands import PduCmd as Cmd


class PduCmd(Cmd.PduCmd):
    def __init__(self, actor):
        Cmd.PduCmd.__init__(self, actor)
