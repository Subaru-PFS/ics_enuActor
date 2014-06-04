#!/usr/bin/env python
# encoding: utf-8
from enuActor.QThread import *
from enuActor.MyFSM import *
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
    {'name': 'load', 'src': ['IDLE', 'FAIL', 'none'], 'dst': 'LOADED'},
    {'name': 'init', 'src': 'LOADED', 'dst': 'INITIALISING'},
    {'name': 'idle', 'src': ['IDLE', 'INITIALISING', 'BUSY'],'dst': 'IDLE'},
    {'name': 'busy', 'src': ['BUSY', 'IDLE'], 'dst': 'BUSY'},
    {'name': 'off', 'src': 'LOADED', 'dst': 'SHUT_DOWN'},
    {'name': 'fail','src': ['none', 'FAIL', 'LOADED', 'INITIALISING', 'IDLE', 'BUSY', 'SAFE_OFF'],
    'dst': 'FAIL'},
    {'name': 'SafeStop', 'src': 'IDLE', 'dst': 'SAFE_OFF'},
    {'name': 'ShutDown', 'src': 'LOADED', 'dst': 'SHUT_DOWN'}
    ],
 'callbacks': {}
}


class Device(QThread):

    """All device (Shutter, BIA,...) should inherit this class

        Attributes:
         * link : ``TTL``, ``SERIAL`` or ``ETHERNET``
         * ser : serial object from serial module @todo: change into link object
         * mode : ``operation`` or ``simulated``
         * cfg_path : path of the communication and parameter config files\
                 It should contains *devices_communication.cfg* and\
                 *devices_parameters.cfg* file.
    """

    cfg_files = {
            'communication': 'devices_communication.cfg',
            'parameters': 'devices_parameters.cfg'
            }
    available_link = ['TTL', 'SERIAL', 'ETHERNET']

    def __init__(self, actor=None, cfg_path = None):
        QThread.__init__(self, actor, self.__class__)

        # Communication attributes
        self._cfg_files = copy.deepcopy(Device.cfg_files)
        for it in Device.cfg_files.iterkeys():
            self._cfg_files[it] = path + Device.cfg_files[it]
        self._param = None
        self._cfg = None
        self.link = None
        self.ser = None
        self.connection = None

        # Device attributes
        self.device = self.__class__.__name__
        self.mode = "operation"
        self.status = None
        self.MAP = copy.deepcopy(MAP) # referenced
        self.MAP['callbacks']['oninit'] = lambda e: self.initialise()
        self.MAP['callbacks']['onload'] = lambda e:\
            self.load_cfg(self.__class__.__name__)
        self.start()

    ###################
    #  STATE MACHINE  #
    ###################

    def startFSM(self):
        """ Instantiate the :mod:`.MyFSM` class (create the State Machine).

        """
        self.started = True
        self.fsm = Fysom(self.MAP)
        self.fsm.startup()
        self.fsm.onchangestate = self.printstateonchange

    def printstateonchange(self, e):
        """What to display when state change

        :param e: event

        """
        print 'state :%s %s' % (self.device, e.dst)

    def initialise(self):
        """Overriden by subclasses:
         * (Re)Load parameters from config files
         * Check communication

        .. todo:: Add load cfg file routine

        """
        self.load_cfg(self.device)
        self.handleTimeout()

    def getStatus(self):
        """return status of shutter (FSM)

        :returns: ``'LOADED'``, ``'IDLE'``, ``'BUSY'``, ...
        """
        return "%s status [%s, %s]" % (self.device.upper(), self.fsm.current, self.status)

    #callbacks: init, safe_off, shut_down

    ############################
    #  COMMUNICATION HANDLING  #
    ############################

    def load_cfg(self, device):
        """Load configuration file of the device.

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
                    "%s is not an available LINK" % links[device])
        else:
            self.device = device.lower()
            self.link = links[device.lower()]
            try:
                self._cfg = dict(config.items(device.upper()))
            except ConfigParser.NoSectionError, e:
                raise Error.CfgFileErr(e)

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

    def __init__(self, actor=None, cfg_path=path):
        super(SimulationDevice, self).__init__(actor, cfg_path)

    def sim_start_communication(self, *args, **kwargs):
        print "Simulation: start comm"
        self.startFSM()

    def sim_start_serial(self, input_buff=None):
        print "Simulation: start serial"

    def sim_start_ethernet(self):
        print "Simulation: start ethernet"

    def sim_start_ttl(self):
        pass

    def sim_send(self, input_buff=None):
        print "Simulation: send"


class OperationDevice(Device):

    """Device in operation mode:

         * Communication is implemented
         * Starting, sending and receiving message is implemented"""

    def __init__(self, actor=None, cfg_path=path):
        super(OperationDevice, self).__init__(actor, cfg_path)


    def op_start_communication(self, *args, **kwargs):
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
        if self.mode == "simulated":
            self.startFSM()
            print "[simulated]"
        # Load parameter link
        if kwargs.has_key('device'):
            if kwargs.has_key('configFile'):
                self._cfg_files['communication'] = kwargs['configFile']
            self.load_cfg(kwargs['device'])

        # Start communication
        if self.link == 'SERIAL':
            if kwargs.has_key('startCmd'):
                self.ser = self.start_serial(kwargs['startCmd'])
            else:
                self.ser = self.start_serial()
            #self.connection = self.ser #TODO: to be changed
        elif self.link == 'ETHERNET':
            self.connection = self.start_ethernet()
        elif self.link == 'TTL':
            raise NotImplementedError
        else:
            raise Error.CfgFileErr("LINK section error in config file :\n\
LINK: %s\nCfgFile: %s\n " % (self.link, self._cfg))
        self.startFSM()

    def op_start_serial(self, input_buff=None):
        """Start a serial communication

        :param input_buff: Send at start to check communication
        :type input_buff: str.
        :returns: :py:class:`serial.Serial`

        """
        import serial
        self.ser = serial.Serial(
            port = self._cfg['port'],
            baudrate = int(self._cfg['baudrate']),
            parity = self._cfg['parity'],
            stopbits = int(self._cfg['stopbits']),
            bytesize = int(self._cfg['bytesize']),
            timeout = 1
        )

        if self.ser.isOpen is False:
            self.ser.open()
        else:
            time.sleep(.2)
            self.ser.flushInput()
            self.ser.flushOutput()
        return self.ser

    def op_start_ethernet(self):
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

    def op_start_ttl(self):
        """@todo: Docstring for start_ttl.

        :returns: @todo
        :raises: @todo

        """
        raise NotImplementedError

    def op_send(self, input_buff=None):
        """Send string to interface

        :param input_buff: string to send to check com.
        :type input_buff: str.
        :returns: returns from com.
        :raises: :class:`~.Error.CommErr`

        """
        buff = ''
        if self.link == 'SERIAL':
            if input_buff is not None:
                try:
                    self.ser.write(input_buff)
                except serial.SerialException, e:
                    raise Error.CommErr("[%s, %s]"% (e.errno, e.message))
                time.sleep(0.3)
                while self.ser.inWaiting() > 0:
                    buff += self.ser.read(1)
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


class DualModeDevice(OperationDevice, SimulationDevice):

    """Switch between class following the device mode"""

    def __init__(self, actor=None):
        """@todo: to be defined1. """
        super(DualModeDevice, self).__init__(actor)
        self._start_communication_map = {
                'simulated': self.sim_start_communication,
                'operation': self.op_start_communication
                }
        self._start_serial_map = {
                'simulated': self.sim_start_serial,
                'operation': self.op_start_serial
                }
        self._start_ethernet_map = {
                'simulated': self.sim_start_ethernet,
                'operation': self.op_start_ethernet
                }
        self._start_ttl_map = {
                'simulated': self.sim_start_ttl,
                'operation': self.op_start_ttl
                }
        self._send_map = {
                'simulated': self.sim_send,
                'operation': self.op_send
                }

    def start_communication(self, *args, **kwargs):
        self._start_communication_map[self.mode]()
        #self.startFSM()

    def start_serial(self, *args, **kwargs):
        #self.startFSM()
        return self._start_serial_map[self.mode](*args, **kwargs)

    def start_ethernet(self, *args, **kwargs):
        print "in DualModeDevice start_ethernet"
        return self._start_ethernet_map[self.mode](*args, **kwargs)

    def start_ttl(self, *args, **kwargs):
        return self._start_ttl_map[self.mode](*args, **kwargs)

    def send(self, *args, **kwargs):
        return self._send_map[self.mode](*args, **kwargs)





def transition(during_state, after_state=None):
    """Decorator enabling the function to trigger state of the FSM.

    :param during_state: event at beginning of the function
    :param after_state: event after the function is performed if specified
    :returns: function return
    :raises: :class:`~.Error.DeviceErr`

    """
    def wrapper(func):
        def wrapped_func(self, *args):
            self.fsm.trigger(during_state)
            try:
                res = func(self, *args)
                if after_state is not None:
                    self.fsm.trigger(after_state)
                return res
            except Error.DeviceErr, e:
                self.fsm.fail()
                raise e
        return wrapped_func
    return wrapper

def interlock(self_position, target_position, target):
    """Interlock between self device and target device

    .. note:: Choice of iterable is exclusive either
    ``self_position`` or ``target_position``

    :param self_position: position(s) from current device class
    :type self_position: str, int, float, iterable (list, tuple,...)
    :param target_position: position from target device class
    :type target_position: str, int, float, iterable.
    :param target: target device class

    """
    def wrapper(func):
        def wrapped_func(self, *args):
            target_currPos = getattr(getattr(self.actor, target), "currPos")
            # TODO: To improve args
            if hasattr(self_position, '__iter__'):
                #self_position is iterable
                for position in self_position:
                    if position in args and\
                            target_currPos == target_position:
                                print "Interlock !"
                                return 0
            elif hasattr(target_position, '__iter__'):
                #target_position is iterable
                for position in target_position:
                    if self_position in args and\
                            target_currPos == position:
                                print "Interlock !"
                                return 0
            elif self_position in args and\
                    target_currPos == target_position:
                print "Interlock !"
                return 0
            return func(self, *args)
        return wrapped_func
    return wrapper
