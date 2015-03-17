#!/usr/bin/env python
# encoding: utf-8
from enuActor.QThread import *
#from actorcore.QThread import QThread
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

# Configuration files in cfg directory
cfg_files = {
        'communication': 'devices_communication.cfg',
        'parameters': 'devices_parameters.cfg'
        }

for it in cfg_files.iterkeys():
    cfg_files[it] = path + cfg_files[it]


class Device(object):

    """All device (Shutter, BIA,...) should inherit this class

        Attributes:
         * link : ``TTL``, ``SERIAL`` or ``ETHERNET``
         * connection : object for link connection
         * cfg_path : path of the communication and parameter config files\
                 It should contains *devices_communication.cfg* and\
                 *devices_parameters.cfg* file.
    """

    available_link = ['TTL', 'SERIAL', 'ETHERNET', 'NOTSPECIFIED']

    def __init__(self, device, thread = None, cfg_path = None):
        # Communication attributes
        self._param = None
        self._cfg = None
        self.link = None
        self.connection = None
        self._connection = None

        # Device attributes
        self.thread = thread
        self.deviceName = device
        self.currPos = "undef. (bug. to be reported)"
        self.started = False
        self.currSimPos = None
        self.MAP = copy.deepcopy(MAP) # referenced
        #self.MAP['callbacks']['onload'] = lambda e: self.device.OnLoad()
        self.fsm = Fysom(self.MAP)

    def startFSM(self):
        """ Instantiate the :mod:`.MyFSM` class (create the State Machine).

        """
        self.started = True
        self.fsm.startup()
        self.fsm.onchangestate = self.printstateonchange

    def printstateonchange(self, e):
        """ What to display when state change

        :param e: event

        """
        if self.fsm.current == "FAILED":
            self.thread.error("state changed = %s" % self.fsm.current)
        else:
            self.thread.inform("state changed = %s" % self.fsm.current)


    ############################
    #  COMMUNICATION HANDLING  #
    ############################
    @staticmethod
    def load_cfg(device):
        """ Load configuration file of the device:

            * load data files to self._cfg an self._param

        :param device: name of the device (``'SHUTTER'``, ``'BIA'``, ...)
        :type device: str.
        :returns: dict config keys: 'param', 'com', 'link'
        :raises: :class:`~.Error.CfgFileErr``

        """

        # Parameters section
        config = ConfigParser.ConfigParser()
        config.readfp(open(cfg_files['parameters']))
        try:
            _param = dict(config.items(device.upper()))
        except ConfigParser.NoSectionError, e:
            raise Error.CfgFileErr(e)

        # Communication section
        config = ConfigParser.ConfigParser()
        try:
            config.readfp(open(cfg_files['communication']))
        except IOError, e:
            raise e
        links = dict(config.items('LINK'))
        if not links.has_key(device.lower()):
            raise Error.CfgFileErr(\
                    "%s is not defined in LINK parameter section" % device)
        elif links[device.lower()] not in Device.available_link:
            raise Error.CfgFileErr(\

                    "%s is not an available LINK" % links[device.lower()])
        else:
            link = links[device.lower()]
            try:
                _cfg = dict(config.items(device.upper()))
            except ConfigParser.NoSectionError, e:
                raise Error.CfgFileErr(e)
        return {
                'param' : _param,
                'com': _cfg,
                'link': link
                }

    def loadInlineCfg(self):
        """call load config inline (splitted because of external call)

        """
        dic = self.load_cfg(self.deviceName)
        self._param = dic['param']
        self._cfg = dic['com']
        self.link = dic['link']

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

    def __init__(self, device, thread=None, cfg_path=path):
        super(SimulationDevice, self).__init__(device, thread,  cfg_path)

    ###################
    #  communication  #
    ###################
    @transition(after_state='load')
    def start_communication(self, *args, **kwargs):
        self.thread.inform("starting communication...")
        self.loadInlineCfg()
        self.OnLoad()

    def start_serial(self, input_buff=None):
        self.thread.inform("start serial")

    def start_ethernet(self):
        self.thread.inform("start ethernet")

    def start_ttl(self):
        self.thread.inform("start ttl")

    def send(self, input_buff=None):
        """ Display what he is sent only in debug mode (to avoid spam)"""
        if self.thread.actor.bcast.debug:
            self.thread.inform("sending '%s'" % input_buff)

    #########
    #  FSM  #
    #########
    @transition('init', 'idle')
    def initialise(self):
        pass

    def OnLoad(self):
        self.load_cfg(self.deviceName)
        if self.deviceName.lower() == 'slit':
            self.thread._home = map(float, self._param['home'].split(','))

    def check_status(self):
        #self.thread.<method> to have access to deviceyy
        pass

    def check_position(self):
        #self.thread.<method> to have access to deviceyy
        if self.thread.currSimPos is not None:
            self.thread.currPos = self.thread.currSimPos


class OperationDevice(Device):

    """Device in operation mode:

         * Communication is implemented
         * Starting, sending and receiving message is implemented"""

    def __init__(self, device, thread=None, cfg_path=path):
        super(OperationDevice, self).__init__(device, thread, cfg_path)

    @transition(after_state = 'load')
    def start_communication(self, *args, **kwargs):
        """ Process to start communication following interface definition.

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
        self.loadInlineCfg()
        # Load parameter link
        if kwargs.has_key('device'):
            if kwargs.has_key('configFile'):
                self._cfg_files['communication'] = kwargs['configFile']
            self.load_cfg(kwargs['device'])

        # Start communication
        if self.link == 'SERIAL':
            if kwargs.has_key('startCmd'):
                self._connection = self.start_serial(kwargs['startCmd'])
            else:
                self._connection = self.start_serial()
                # check connection
                #self.check_status()
        elif self.link == 'ETHERNET':
            if self.connection != None:
                self.connection.close()
            self._connection = self.start_ethernet()
        elif self.link == 'TTL':
            raise NotImplementedError
        elif self.link != 'NOTSPECIFIED':
            raise Error.CfgFileErr("LINK section error in config file :\n\
LINK: %s\nCfgFile: %s\n " % (self.link, self._cfg))

    @transition(after_state = 'load')
    def OnLoad(self):
        pass

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
        """ Start an Ethernet communication

        :returns: socket
        :raises: :class:`~.Error.CommErr`

        """
        #TODO: Implement ehere
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(float(self._cfg['timeout']))
            sock.connect((self._cfg['ip_dst'], int(self._cfg['port'])))
            #sock.settimeout(None)
        except IOError as e:
            raise Error.CommErr(e)
        return sock

    def start_ttl(self):
        """ Not implemented.

        """
        raise NotImplementedError

    def send(self, input_buff=None):
        """Send string to interface

        :param input_buff: string to send to check com.
        :type input_buff: str.
        :returns: returns from com.
        :raises: :class:`~.Error.CommErr`

        """
        import sys
        buff = ''
        if self.link == 'SERIAL':
            if input_buff is not None:
                cmpt = 0
                sys.stdout.flush()
                while buff == '' and cmpt < 3:
                    # try 3 times if no response
                    try:
                        self.connection.write(input_buff)
                    except serial.SerialException as e:
                        raise Error.CommErr("[%s, %s]" % (e.errno, e.message))
                    time.sleep(0.3)
                    #while self.connection.inWaiting() > 0:
                    buff = self.connection.read(
                            self.connection.inWaiting())
                    cmpt += 1
                    print buff
                if buff == '':
                    raise Error.CommErr("No response from serial port")
                else:
                    return buff
        elif self.link == 'ETHERNET':
            #TODO: To improve
            try:
                self.connection.send(input_buff)
                data = self.connection.recv(512)
                return data #TODO: Tobe improve
            except socket.error as e:
                raise Exception(e)
        elif self.link == 'TTL':
            raise NotImplementedError
        elif self.link == 'NOTSPECIFIED':
            raise Error.DeviceErr(
            "Link not specified the method send shouldn't be called.",
            device = self.deviceName)
        else:
            raise NotImplementedError("send method: link not known %s " % self.link)


class DualModeDevice(QThread):

    """ Switch between OperationDevice or SimulationDevice class following the\
            device mode"""

    def __init__(self, actor=None):
        self.deviceName = self.__class__.__name__
        super(DualModeDevice, self).__init__(actor, self.deviceName, timeout = 2)
        self.start()

        #communication part
        self.link = None
        self._cfg = None
        self._param = None

        #factory part
        self.mode = None
        self.deviceStarted = False
        self._map = {
                'operation' : OperationDevice,
                'simulated' : SimulationDevice
                }

        #debug
        self.debug = False

    def startDevice(self):
        """ Preprocessing before instantiation of a device when the\
                command start is launched. Maybe function can be refactored

        """
        self.load_cfg()
        self.curModeDevice = self._map[self.mode](self.deviceName, thread = self)

    def handleTimeout(self):
        """Override method :meth:`.QThread.handleTimeout`.
        Process while device is idling.

        :raises: :class:`~.Error.CommErr`

        """
        if self.deviceStarted:
            self.check_status()
            self.check_position()
            self.updateFactory()
            if self.fsm.current in ['BUSY']:
                self.fsm.idle()

    def generate(self, var):
        """Called each time the Dictionary variable are changed

        """
        if self.debug:
            self.finish("Generator update dictionary")

    #############
    #  Factory  #
    #############
    def updateFactory(self):
        """Update attributes of curModeDevice object (of current "Device")

        """
        self.curModeDevice.currPos = self.currPos
        self.curModeDevice._param = self._param
        self.curModeDevice._cfg = self._cfg
        self.curModeDevice.link = self.link

    def change_mode(self, mode):
        """It does all pre/post processing for changing mode :
                * reallocate & instanciate a Device
                * Start the device

        :param mode: ``operation``, ``simulated``

        """
        self.currPos = None
        self.mode = mode
        # it calls start device which create new Op/SimDevice
        self.startDevice()
        #Have to go throw curModeDevice avoid bug Exception 1000 device not started yet
        self.curModeDevice.startFSM()
        self.curModeDevice.start_communication()
        if self.deviceName.lower() == 'shutters':
            if self.actor.bia.deviceStarted:
                #Bia and Shutter are same connection through arduino
                #So point to other connection (socket)
                self.curModeDevice.connection =\
                    self.actor.bia.curModeDevice.connection
            else:
                #Else overwrite connection
                self.curModeDevice.connection = self.curModeDevice._connection
        elif self.deviceName.lower() == 'bia':
            if self.actor.shutter.deviceStarted:
                #Bia and Shutter are same connection through arduino
                #So point to other connection (socket)
                self.curModeDevice.connection =\
                    self.actor.shutter.curModeDevice.connection
            else:
                #Else overwrite connection
                self.curModeDevice.connection = self.curModeDevice._connection
        # We tell deviceStarted here because of handleTimeout which checkstatus
        # So we need to have connection set before
        self.deviceStarted = True
        self.OnLoad()


    ############
    #  Device  #
    ############
    def load_cfg(self):
        """Load configuration (call :meth:`.Devices.Device.load_cfg`) file of
        the device:
        * load data file to self._cfg ad self._param

        :returns: dict config
        :raises: :class:`~.Error.CfgFileErr``

        """
        dic = Device.load_cfg(self.deviceName)
        self._param = dic['param']
        self._cfg = dic['com']
        self.link = dic['link']

    def getStatus(self):
        """return status of Device (FSM) when asked from client MHS

        :returns: string. "(state, position)"
        """
        if self.currPos in [None, 'undef.']:
            currPos = 'undef.'
        elif type(self.currPos) == list:
            currPos = map(lambda x: round(x, 2), self.currPos)
        else:
            currPos = self.currPos
        try:
            return '(%s, %s)' % (self.fsm.current, currPos)
        except Error.DeviceErr as e:
            if e.code == 1000:
                self.warn("'GetStatus' called before device \
%s started." % self.deviceName)
            else:
                raise e

    @transition('fail')
    def fail(self, reason=None):
        """ Routine launched when device go to FAILED state.

        """
        raise Error.DeviceErr(reason, device = self.deviceName)

    def inform(self, msg):
        if self.deviceName.lower() == 'enu':
            self.actor.bcast.inform("text='[%s] %s'" %\
                                    (self.deviceName, msg))
        else:
            self.actor.bcast.inform("text='[%s, %s] %s'" %\
                                    (self.deviceName, self.mode, msg))

    def warn(self, msg):
        if self.deviceName.lower() == 'enu':
            self.actor.bcast.warn("text='[%s] %s'" %\
                                    (self.deviceName, msg))
        else:
            self.actor.bcast.warn("text='[%s, %s] %s'" %\
                                    (self.deviceName, self.mode, msg))

    def error(self, msg):
        if self.deviceName.lower() == 'enu':
            self.actor.bcast.error("text='[%s] %s'" %\
                                    (self.deviceName, msg))
        else:
            self.actor.bcast.error("text='[%s, %s] %s'" %\
                                    (self.deviceName, self.mode, msg))

    def finish(self, msg=None):
        if self.deviceName.lower() == 'enu':
            self.actor.bcast.finish("text='[%s] %s'" %\
                                    (self.deviceName, msg))
        else:
            self.actor.bcast.finish("text='[%s, %s] %s'" %\
                                (self.deviceName, self.mode, msg))

    def diag(self, msg):
        if self.deviceName.lower() == 'enu':
            self.actor.bcast.diag("text='[%s] %s'" %\
                                    (self.deviceName, msg))
        else:
            self.actor.bcast.diag("text='[%s, %s] %s'" %\
                                    (self.deviceName, self.mode, msg))

    def __getattr__(self, name):
        if self.deviceStarted is True:
            return getattr(self.curModeDevice, name)
        else:
            raise Error.DeviceErr("Try to access: %s"% name,
                                  device = self.deviceName,
                                  code = 1000)

    def __getattribute__(self, name):
        if name in [
                'check_status',
                'check_position',
                'start_communication'
                ]:
            if self.mode == 'simulated' and self.deviceStarted:
                return self.__getattr__(name)
        return super(DualModeDevice, self).__getattribute__(name)

