#!/usr/bin/env python
# encoding: utf-8
from enuActor.QThread import *
from enuActor.MyFSM import *
from interlock import interlock
import serial
import ConfigParser
import re
import os
import Error
import time
import copy
import socket

# file PWD + cfg
here = os.path.dirname(os.path.realpath(__file__))
path = here + '/cfg/'

# Common device state
MAP = {
'initial' : 'none',
'events': [
    {'name': 'load', 'src': ['IDLE', 'FAILED', 'none'], 'dst': 'LOADED'},
    {'name': 'init', 'src': 'LOADED', 'dst': 'INITIALISING'},
    {'name': 'idle', 'src': ['IDLE', 'INITIALISING', 'BUSY'],'dst': 'IDLE'},
    {'name': 'busy', 'src': ['BUSY', 'IDLE'], 'dst': 'BUSY'},
    {'name': 'off', 'src': 'LOADED', 'dst': 'SHUT_DOWN'},
    {'name': 'fail','src': ['none', 'FAILED', 'LOADED', 'INITIALISING', 'IDLE', 'BUSY', 'SAFE_OFF'],
    'dst': 'FAILED'},
    {'name': 'SafeStop', 'src': 'IDLE', 'dst': 'SAFE_OFF'},
    {'name': 'ShutDown', 'src': 'LOADED', 'dst': 'SHUT_DOWN'}
    ],
 'callbacks': {}
}

class Device(object):

    """All device (Shutter, BIA,...) should inherit this class

        Attributes:
         * link : ``TTL``, ``SERIAL`` or ``ETHERNET``
         * connection : object for link connection
         * cfg_path : path of the communication and parameter config files\
                 It should contains *devices_communication.cfg* and\
                 *devices_parameters.cfg* file.
    """

    cfg_files = {
            'communication': 'devices_communication.cfg',
            'parameters': 'devices_parameters.cfg'
            }
    available_link = ['TTL', 'SERIAL', 'ETHERNET', 'NOTSPECIFIED']

    def __init__(self, device, actor=None, cfg_path = None):

        # Communication attributes
        self._cfg_files = copy.deepcopy(Device.cfg_files)
        for it in Device.cfg_files.iterkeys():
            self._cfg_files[it] = path + Device.cfg_files[it]
        self._param = None
        self._cfg = None
        self.link = None
        self.connection = None


        # Device attributes
        self.device = device
        self.currPos = "undef. (bug. to be reported) "
        self.started = False
        self.currSimPos = None
        self.MAP = copy.deepcopy(MAP) # referenced
        #self.MAP['callbacks']['onload'] = lambda e: self.OnLoad()
        self.fsm = Fysom(self.MAP)

    #callbacks: init, safe_off, shut_down
    @transition('fail')
    def fail(self, reason):
        print "%s_FAILED : %s" % (self.device, reason)

    def startFSM(self):
        """ Instantiate the :mod:`.MyFSM` class (create the State Machine).

        """
        self.started = True
        self.fsm.startup()
        self.fsm.onchangestate = self.printstateonchange

    def printstateonchange(self, e):
        """What to display when state change

        :param e: event

        """
        print 'state :%s %s' % (self.device, e.dst)


    ############################
    #  COMMUNICATION HANDLING  #
    ############################

    def load_cfg(self, device):
        """Load configuration file of the device:
        * load data file to self._cfg ad self._param

        :param device: name of the device (``'SHUTTER'``, ``'BIA'``, ...)
        :type device: str.
        :returns: dict config
        :raises: :class:`~.Error.CfgFileErr``

        """

        # Parameters section
        config = ConfigParser.ConfigParser()
        config.readfp(open(self._cfg_files['parameters']))
        try:
            self._param = dict(config.items(device.upper()))
        except ConfigParser.NoSectionError, e:
            raise Error.CfgFileErr(e)

        # Communication section
        config = ConfigParser.ConfigParser()
        config.readfp(open(self._cfg_files['communication']))
        links = dict(config.items('LINK'))
        if not links.has_key(device.lower()):
            raise Error.CfgFileErr(\
                    "%s is not defined in LINK parameter section" % device)
        elif links[device.lower()] not in Device.available_link:
            raise Error.CfgFileErr(\
                    "%s is not an available LINK" % links[device.lower()])
        else:
            self.device = device.lower()
            self.link = links[device.lower()]
            try:
                self._cfg = dict(config.items(device.upper()))
            except ConfigParser.NoSectionError, e:
                raise Error.CfgFileErr(e)

    def OnLoad(self):
        """ Virtual callback method for FSM (should be overriden if used)

        .. note: called after ``op_start_communication`` or by load transition
        """
        return NotImplemented

    def start_communication(self, *args, **kwargs):
        """To be overriden virtual method
        """
        return NotImplemented

    def start_serial(self, input_buff=None):
        """To be overriden virtual method
        """
        return NotImplemented

    def start_ttl(self):
        """To be overriden virtual method
      """
        return NotImplemented

    def start_ethernet(self):
        """To be overriden virtual method
        """
        return NotImplemented

    def send(self, input_buff=None):
        """To be overriden virtual method
        """
        return NotImplemented


class SimulationDevice(Device):

    """Device in simulation mode:

         Almost nothing"""

    def __init__(self, device, actor=None, cfg_path=path):
        super(SimulationDevice, self).__init__(device, actor, cfg_path)

    ###################
    #  communication  #
    ###################
    def start_communication(self, *args, **kwargs):
        print "[Simulation] %s: start communication" % self.device
        self.load_cfg(self.device)
        self.startFSM()
        self.OnLoad()

    def start_serial(self, input_buff=None):
        print "[Simulation] %s: start serial" % self.device

    def start_ethernet(self):
        print "[Simulation] %s: start ethernet" % self.device

    def start_ttl(self):
        print "[Simulation] %s: start ttl" % self.device

    def send(self, input_buff=None):
        import sys
        sys.stdout.write("[Simulation] %s: sending '%s'" %
                (self.device, input_buff))

    #########
    #  FSM  #
    #########
    @transition('init', 'idle')
    def initialise(self):
        self.load_cfg(self.device)

    @transition('load')
    def OnLoad(self):
        pass

    def check_status(self):
        pass

    def check_position(self):
        if self.currSimPos is not None:
            self.currPos = self.currSimPos


class OperationDevice(Device):

    """Device in operation mode:

         * Communication is implemented
         * Starting, sending and receiving message is implemented"""

    def __init__(self,device, actor=None, cfg_path=path):
        super(OperationDevice, self).__init__(device, actor, cfg_path)


    def start_communication(self, *args, **kwargs):
        """Docstring for start_communication.

        .. note:: Need first to specify config file and device by calling :func:`load_cfg`
                or in the header of :func:`start_communication`

        :param device: device name
        :type device: str.
        :param startCmd: starting command to check the communication
        :type startCmd: str.
        :param \**kwargs: remaining keywords are not treated
        :returns: Communication object (example: :py:class:`serial.Serial` object)
        :raises: :class:`~.Error.CfgFileErr`

        """
        self.load_cfg(self.device)
        # Load parameter link
        if kwargs.has_key('device'):
            if kwargs.has_key('configFile'):
                self._cfg_files['communication'] = kwargs['configFile']
            self.load_cfg(kwargs['device'])

        # Start communication
        if self.link == 'SERIAL':
            if kwargs.has_key('startCmd'):
                self.connection = self.start_serial(kwargs['startCmd'])
            else:
                self.connection = self.start_serial()
                # check connection
                #self.check_status()
        elif self.link == 'ETHERNET':
            self.connection = self.start_ethernet()
        elif self.link == 'TTL':
            raise NotImplementedError
        elif self.link != 'NOTSPECIFIED':
            raise Error.CfgFileErr("LINK section error in config file :\n\
LINK: %s\nCfgFile: %s\n " % (self.link, self._cfg))
        self.startFSM()

    def start_serial(self, input_buff=None):
        """Start a serial communication

        :param input_buff: Send at start to check communication
        :type input_buff: str.
        :returns: :py:class:`serial.Serial`

        """
        import serial
        connection = serial.Serial(
            port = self._cfg['port'],
            baudrate = int(self._cfg['baudrate']),
            parity = self._cfg['parity'],
            stopbits = int(self._cfg['stopbits']),
            bytesize = int(self._cfg['bytesize']),
            timeout = 1
        )

        if connection.isOpen is False:
            connection.open()
        else:
            time.sleep(.2)
            connection.flushInput()
            connection.flushOutput()
        return connection

    def start_ethernet(self):
        """@todo: Docstring for start_ethernet.

        :returns: @todo
        :raises: @todo

        """
        #TODO: Implement ehere
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(float(self._cfg['timeout']))
            sock.connect((self._cfg['ip_dst'], int(self._cfg['port'])))
            sock.settimeout(None)
        except IOError as e:
            raise Error.CommErr(e)
        return sock

    def start_ttl(self):
        """@todo: Docstring for start_ttl.

        :returns: @todo
        :raises: @todo

        """
        raise NotImplementedError

    def send(self, input_buff=None):
        """Send string to interface

        :param input_buff: string to send to check com.
        :type input_buff: str.
        :returns: returns from com.
        :raises: :class:`~.Error.CommErr`

        """
        buff = ''
        if self.link == 'SERIAL':
            if input_buff is not None:
                cmpt = 0
                while buff == '' and cmpt < 3:
                    # try 3 times if no response
                    try:
                        self.connection.write(input_buff)
                    except serial.SerialException as e:
                        raise Error.CommErr("[%s, %s]" % (e.errno, e.message))
                    time.sleep(0.3)
                    while self.connection.inWaiting() > 0:
                        buff += self.connection.read(1)
                    print "trying again (%i)..." % cmpt
                    cmpt += 1
                if buff == '':
                    raise Error.CommErr("No response from serial port")
                else:
                    return buff
        elif self.link == 'ETHERNET':
            #TODO: To improve
            try:
                self.connection.send(input_buff)
                data = self.connection.recv(1)
            except socket.error as e:
                raise Error.CommErr(e)
        elif self.link == 'TTL':
            raise NotImplementedError
        else:
            raise NotImplementedError


class DualModeDevice(QThread):

    """Switch between class following the device mode"""

    def __init__(self, actor=None):
        """@todo: to be defined1. """
        self.device = self.__class__.__name__
        QThread.__init__(self, actor, self.device)
        self.start()
        self._mode = 'operation'
        self._map = {
                'operation' : OperationDevice,
                'simulated' : SimulationDevice
                }
        self.curModeDevice = self._map[self._mode](self.device)

    def handleTimeout(self):
        """Override method :meth:`.QThread.handleTimeout`.
        Process while device is idling.

        :returns: @todo
        :raises: :class:`~.Error.CommErr`

        """
        if self.started:
            self.check_status()
            self.check_position()
            self.updateFactory()
            if self.fsm.current in ['BUSY']:
                self.fsm.idle()
            elif self.fsm.current == 'none':
                self.fsm.load()

    def getStatus(self):
        """return status of Device (FSM)

        :returns: ``'LOADED'``, ``'IDLE'``, ``'BUSY'``, ...
        """
        return "%s status [%s, %s]" % (self.device.upper(),
                self.fsm.current, self.currPos)


    def updateFactory(self):
        """Update attributes of curModeDevice object
        :returns: @todo
        :raises: @todo

        """
        self.curModeDevice.currPos = self.currPos

    def mode():
        """Mode attribute : On change instantiate
        OperationDevice/SimulationDevice

        """
        def fget(self):
            return self._mode

        def fset(self, value):
            if self._mode != value:
                self.curModeDevice = self._map[value](self.device)
            self._mode = value
        return locals()

    mode = property(**mode())

    def __getattr__(self, name):
        return getattr(self.curModeDevice, name)

    def __getattribute__(self, name):
        if name in [
                'check_status',
                'check_position',
                'start_communication',
                'initialise'
                ]:
            if self.mode == 'simulated':
                return self.__getattr__(name)
        return super(DualModeDevice, self).__getattribute__(name)
