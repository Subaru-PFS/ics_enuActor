#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                        FPSA SW device module                        #
#######################################################################

from enuActor.QThread import *
import serial, time
import Error
from Device import *
import numpy as np
import re


class Slit(DualModeDevice):

    """SW device: Fiber Slit Positionning Sub Assembly

        Attributes:
         * currPos : current position of the slit

    """

    def __init__(self, actor=None):
        """@todo: to be defined1. """
        super(Slit, self).__init__(actor)
        self.currPos = None

    @transition('busy', 'idle')
    def slit(self, arg1):
        """Not Implemented yet

        :param arg1: @todo
        :returns: @todo
        :raises: @todo

        """
        pass

    def op_check_status(self):
        """Not Implemented yet
        :returns: @todo
        :raises: @todo

        """
        pass
