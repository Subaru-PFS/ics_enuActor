#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                        FPSA SW device module                        #
#######################################################################
from enuActor.QThread import *
from Device import *
import serial, time
import Error
from utils import hxp_drivers
import numpy as np
import re
import sys


class Slit(DualModeDevice):

    """SW device: Fiber Slit Positionning Sub Assembly

        Attributes:

            * currPos : current position of the slit
            * link_busy : flag saying if connection is busy

    """

    def __init__(self, actor=None):
        super(Slit, self).__init__(actor)
        # Device attributes
        self.currPos = None
        self.link_busy = False

        # Hexapod Attributes
        self.groupName = 'HEXAPOD'
        self.myxps = None
        self.socketId = None

        # Slit Attributes
        self._dither_axis = None
        self._focus_axis = None
        self._magnification = None
        self._dithering_value = None
        self._focus_value = None
        self._home = None

    @transition('init', 'idle')
    def initialise(self):
        """ Initialise slit

        - init hxp
        - search home
        - go home
        - check status
        """
        self._kill()
        print "initialising hxp ..."
        self._initialize()
        print "seeking home ..."
        self._homeSearch()
        if self._home is None:
            raise Exception("Bug: Home not initialised")
        else:
            self.getHome()
            self.setHome(self._home)
        print "going to home ..."
        self._hexapodMoveAbsolute(*[0, 0, 0, 0, 0, 0])
        self.check_status()
        self.check_position()

    #############
    #  HEXAPOD  #
    #############
    def getHome(self):
        """getHome.

        :returns: [x, y, z, u, v, w]
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        hxpHome = self._hexapodCoordinateSytemGet('Tool')
        return [sum(x) for x in zip(hxpHome, self._slit_position)]

    def setHome(self, posCoord=None):
        """setHome.
        setHome to posCoord or to current if posCoord is None

        :param posCoord: [x, y, z, u, v, w] or nothing if current
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        if posCoord is None:
            posCoord = self._getCurrentPosition()
            curHome = self._hexapodCoordinateSytemGet('Tool')
            posCoord = [sum(x) for x in zip(posCoord, curHome)]
        curHome = [xi - xj for xi, xj  in zip(posCoord, self._slit_position)]
        self._hexapodCoordinateSytemSet('Work', *curHome)

    @transition('busy', 'idle')
    def moveTo(self, reference, posCoord=None):
        """MoveTo.
        Move to posCoord or to home if posCoord is None

        :param reference: 'absolute' or 'relative'
        :param posCoord: [x, y, z, u, v, w] or nothing if home
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        if posCoord == None:
            # Go to home related to work : [0,0,0,0,0,0]
            posCoord = [0] * 6

        if reference == 'absolute':
            self._hexapodMoveAbsolute(*posCoord)
        elif reference == 'relative' :
            self._hexapodMoveIncremental('Work', *posCoord)

    ############################
    #  DITHER & THROUGH FOCUS  #
    ############################
    @transition('busy', 'idle')
    def dither(self, length):
        """Move in dither (dither_axis) to length pixel.\
                Size of pixel is 34.64 :math:`\mu{}m` on\
                the slit.
                .. math::
                                dither = G * PixelSize

        :param length: length in pixel
        """
        axis = np.array(self.dither_axis + [0] * 3)
        dithering = length * axis * self.magnification
        self._hexapodMoveIncremental('Work', *dithering)
        self.currSimPos = [sum(x) for x in zip(dithering , self.currPos)]

    @transition('busy', 'idle')
    def focus(self, length):
        """Move in focus (focus_axis) to length pixel

        :param length: @todo
        """
        axis = np.array(self.focus_axis + [0] * 3)
        through_focus = axis * length
        self._hexapodMoveIncremental('Work', *through_focus)
        self.currSimPos = [sum(x) for x in zip(through_focus , self.currPos)]

    def magnification():
        """Change magnification.

        :param G: magnification
        :raises: Exception (not init yet)
        """
        def fget(self):
            if self._magnification is None:
                raise Exception("Magnification not defined yet.")
            return self._magnification

        def fset(self, value):
            if value <= 0:
                raise Exception("Wrong magnification value (<=0).")
            self._magnification = value
        return locals()

    magnification = property(**magnification())

    def dither_axis():
        """Accessor to dither_axis attribute

        :param axis: [X, Y, Z] in pixel
        :raises: Exception (not init yet)
        """
        def fget(self):
            if self._dither_axis is None:
                raise Exception("Dither axis not defined yet.")
            return self._dither_axis

        def fset(self, value):
            if value == [0, 0, 0]:
                raise Exception("Wrong axis value: (0, 0, 0)\
is not a direction")
            self._dither_axis = value
        return locals()

    dither_axis = property(**dither_axis())

    def focus_axis():
        """Accessor to focus_axis attribute

        :param axis: [X, Y, Z] in :math:`\mu{}m`
        :raises: Exception (not init yet).
        """
        def fget(self):
            if self._focus_axis is None:
                raise Exception("Focus axis not defined yet.")
            return self._focus_axis

        def fset(self, value):
            if value == [0, 0, 0]:
                raise Exception("Wrong axis value: (0, 0, 0)\
is not a direction")
            self._focus_axis = value
        return locals()

    focus_axis = property(**focus_axis())

    def dithering_value():
        """Accessor to dithering_value attribute for dithering function

        :raises: Exception (not init yet).
        """
        def fget(self):
            if self._dithering_value is None:
                raise Exception("Dithering value not defined yet.")
            return self._dithering_value

        def fset(self, value):
            if value <=0:
                raise Exception("Wrong dithering value (<=0).")
            self._dithering_value = value
        return locals()

    dithering_value = property(**dithering_value())

    def focus_value():
        """Accessor to focus_value attribute for focusing function

        """
        def fget(self):
            if self._focus_value is None:
                raise Exception("Focus value not defined yet.")
            return self._focus_value

        def fset(self, value):
            if value <=0:
                raise Exception("Wrong focus value (<=0).")
            self._focus_value = value
        return locals()

    focus_value = property(**focus_value())

    @transition(after_state = "SafeStop")
    def safeOff(self):
        """Preprocessing before shutdown.

        """
        print "seeking home ..."
        self._hexapodMoveAbsolute(*[0] * 6)
        print "killing connection ..."
        self._kill()
        print "shutdown!"

    @transition(after_state = "ShutDown")
    def shutdown(self):
        """ Preprocessing before manual shutdowf

        """
        print "seeking home ..."
        self._hexapodMoveAbsolute(*[0] * 6)
        print "killing connection ..."
        self._kill()
        print "shutdown!"

    ############
    #  DEVICE  #
    ############o
    def OnLoad(self):
        """Override callback of load transition (FSM):
            load all parameter from cfg file.

        .. warning: It does not load communication parameters

        :raises: :class:`~.Error.CfgFileError`

        """
        print "LOADING..."
        try:
            self.dither_axis = map(float, self._param['dither_axis'].split(','))
        except Exception, e:
            raise Error.CfgFileErr("Wrong value dither_axis (%s)" % e)
        try:
            self.focus_axis = map(float, self._param['focus_axis'].split(','))
        except Exception, e:
            raise Error.CfgFileErr("Wrong value focus_axis (%s)" % e)
        try:
            self.magnification = float(self._param['magnification'])
        except Exception, e:
            raise Error.CfgFileErr("Wrong value magnification (%s)" % e)
        try:
            self.focus_value = float(self._param['focus_value'])
        except Exception, e:
            raise Error.CfgFileErr("Wrong value focus_value")
        try:
            self.dithering_value = float(self._param['dithering_value'])
        except Exception, e:
            raise Error.CfgFileErr("Wrong value dithering_value")
        try:
            self._home = map(float, self._param['home'].split(','))
        except Exception, e:
            raise Error.CfgFileErr("Wrong value home (%s)" % e)
        try:
            self._slit_position = map(float, self._param['slit_position'].split(','))
        except Exception, e:
            raise Error.CfgFileErr("Wrong value home (%s)" % e)


    def start_communication(self):
        #self.startDevice() # Instantiation of Operation/SimuDevice
        print "Connecting to HXP..."
        self.myxps = hxp_drivers.XPS()
        self.socketId = self.myxps.TCP_ConnectToServer(
            str(self._cfg['ip']),
            int(self._cfg['port']),
            int(self._cfg['timeout'])
        )
        if self.socketId == -1:
            raise Error.CommErr("Connection to Hexapod failed check IP & Port")
        else:
            self.startFSM()
            self.OnLoad()

    def check_status(self):
        """Check status of hexapod

        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """

        if self.fsm.current not in ['none', 'INITIALISING']:
            time.sleep(.1)# have to wait else return busy socke
            # check status
            status_code = self._getStatus()
            status = self._getStatusString(int(status_code))

    def check_position(self):
        """Check position of hexapod

        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        if self.fsm.current not in ['none', 'LOADED', 'INITIALISING']:
            # check position
            self.currPos = self._getCurrentPosition()
        else:
            self.currPos = "undef."
        self.generate(self.currPos)

    #############
    #  Parsers  #
    #############
    def _getCurrentPosition(self):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.GroupPositionCurrentGet,
                    self.socketId,
                    self.groupName,
                    6)
        else:
            return self.currSimPos

    def _getStatus(self):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.GroupStatusGet,
                    self.socketId,
                    self.groupName)[0]
        else:
            return NotImplemented

    def _getStatusString(self, code):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.GroupStatusStringGet,
                    self.socketId,
                    code)
        else:
            return NotImplemented

    def _kill(self):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.GroupKill,
                    self.socketId,
                    self.groupName)

    def _initialize(self):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.GroupInitialize,
                    self.socketId,
                    self.groupName)

    def _homeSearch(self):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.GroupHomeSearch,
                    self.socketId,
                    self.groupName)

    def _hexapodCoordinateSytemGet(self, coordSystem):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.HexapodCoordinateSystemGet,
                    self.socketId,
                    self.groupName,
                    coordSystem)
        else:
            return self._home # TODO: take care of reference : 'Work' or 'Base'

    def _hexapodCoordinateSytemSet(self, coordSystem, x, y, z, u, v, w):
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.HexapodCoordinateSystemSet,
                    self.socketId,
                    self.groupName,
                    coordSystem,
                    x, y, z, u, v, w)
        self._home = [x, y, z, u, v, w]

    def _hexapodMoveAbsolute(self, x, y, z, u, v, w):
        """
        ..note: coordSystem not specified because has to be 'Work'

        """
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.HexapodMoveAbsolute,
                    self.socketId,
                    self.groupName,
                    'Work',
                    x, y, z, u, v, w)
        else:
            self.currSimPos = [x, y, z, u, v, w]

    def _hexapodMoveIncremental(self, coordSystem, x, y, z, u, v, w):
        """
        ..todo: Add algorithm for simulation mode

        """
        if self.mode == 'operation':
            return self.errorChecker(
                    self.myxps.HexapodMoveIncremental,
                    self.socketId,
                    self.groupName,
                    coordSystem,
                    x, y, z, u, v, w)
        else:
            # TODO: add rotation algo
            self.currSimPos = [
                    sum(i) for i in zip(self.currPos, [x, y, z, u, v, w])
                    ]

    def errorChecker(self, func, *args):
        """ Kind of decorator who check error after routine.

        :returns: value receive from TCP
        :raises: :class:`~.Error.DeviceErr`, :class:`~.Error.CommErr`
        """
        #Check if sending or receiving
        if self.link_busy == True:
            time.sleep(0.2)
            return self.errorChecker(func, *args)
        else:
            self.link_busy = True
        buf = func(*args)
        self.link_busy = False
        if buf[0] != 0:
            if buf[0] not in [-2, -108]:
                [errorCode, errorString] = self.myxps.ErrorStringGet(
                        self.socketId, buf[0]
                        )
                if buf[0] == -17:
                    raise Exception("Warning: [X, Y, Z, U, V, W] exceed : %s"
                            % errorString)
                elif errorCode != 0:
                    err = func.func_name + ' : ERROR ' + str(errorCode)
                else:
                    err = func.func_name + ' : ' + errorString
            else:
                if buf[0] == -2:
                    raise Error.CommErr(func.func_name + 'TCP timeout')
                elif buf[0] == -108:
                    raise Error.CommErr(func.func_name +
                            'TCP/IP connection was closed by an admin')
            self.fsm.fail()
            raise Error.DeviceErr(err)#a traiter si Device ou COmm suivant cas
        return buf[1:]
