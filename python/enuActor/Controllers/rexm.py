#!/usr/bin/env python

import logging

import serial

from Controllers.device import Device
from Controllers.Simulator.rexm_simu import RexmSimulator
from enuActor.Controllers.wrap import safeCheck, busy


class rexm(Device):
    timeout = 5

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        super(rexm, self).__init__(actor, name)

        self.logger = logging.getLogger('rexm')
        self.logger.setLevel(loglevel)

        self.EOL = '\n'
        self.currPos = 'nan'
        self.serial = None

    def loadCfg(self, cmd, mode=None):
        """loadCfg
        load Configuration file
        :param cmd
        :param mode (operation or simulation, loaded from config file if None
        :return: True, ret : Config File successfully loaded'
                 False, ret : Config file badly formatted, Exception ret
        """
        self.actor.reloadConfiguration(cmd=cmd)

        try:
            self.currMode = self.actor.config.get('rexm', 'mode') if mode is None else mode
            self.port = self.actor.config.get('rexm', 'port')

        except Exception as e:
            return False, 'Config file badly formatted, Exception : %s ' % str(e)

        return True, ''

    def startCommunication(self, cmd):
        """startCommunication
        Start socket with the controller or simulate it
        :param cmd,
        :return: True, ret: if the communication is established with the board, fsm (LOADING => LOADED)
                 False, ret: if the communication failed with the board, ret is the error, fsm (LOADING => FAILED)
        """

        self.rexmSimu = RexmSimulator() if self.currMode == "simulation" else None  # Create new simulator
        cmd.inform("text='Connecting to REXM Controller in ...%s'" % self.currMode)
        try:
            s = self.openSerial(cmd)
            return True, "Connected to REXM controller"
        except Exception as e:
            return False, e

    @safeCheck
    def initialise(self, e):
        """ Initialise Rexm


        wrapper @safeCheck handles the state machine
        :param e, fsm event
        :return: True, ret : if every steps are successfully operated, fsm (LOADED => IDLE)
                 False, ret : if a command fail, user if warned with error ret, fsm (LOADED => FAILED)
        """

        cmd = e.cmd if hasattr(e, "cmd") else self.actor.bcast
        cmd.inform("text='initialising rexm ..._'")

        return True, 'Rexm Successfully initialised'

    def getStatus(self, cmd=None):
        """getStatus
        position is nan if the controller is unreachable
        :param cmd,
        :return True, state, mode, pos_x, pos_y, pos_z, pos_u, pos_v, pos_w
                 False, state, mode, nan, nan, nan, nan, nan, nan if not initialised or an error had occured
        """

        if self.fsm.current in ['IDLE', 'BUSY']:
            ok, ret = self._getCurrentPosition()
            self.currPos = ret if ok else "undef"
        else:
            ok, self.currPos = True, "undef"

        return ok, "%s,%s,%s" % (self.fsm.current, self.currMode, self.currPos)

    def openSerial(self, cmd):
        """ Connect socket if self.serial is None

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """
        if self.serial is None:
            try:
                s = serial.Serial(port=self.port,
                                  baudrate=9600,
                                  parity=serial.PARITY_ODD,
                                  stopbits=serial.STOPBITS_TWO,
                                  bytesize=serial.SEVENBITS) if self.currMode == "operation" else self.rexmSimu

            except Exception as e:
                cmd.warn('text="failed to create serial for %s: %s"' % (self.name, e))
                raise
            try:
                s.open()
            except Exception as e:
                cmd.warn('text="failed to open serial for %s: %s"' % (self.name, e))
                raise
            self.serial = s

        return self.serial

    @busy
    def moveTo(self, cmd, position):
        """MoveTo.
        Move to position

        wrapper @busy handles the state machine
        :param cmd
        :param position: 'low' or 'mid'
        :param posCoord: [x, y, z, u, v, w]
        :return: True, ret : if the command raise no error
                 False, ret: if the command fail
        """
        return True, ""

    def _getCurrentPosition(self):
        return True, "low"
