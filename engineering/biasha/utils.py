import select
import socket

from enuActor.Simulators.bsh import BshSim
from enuActor.utils.wrap import busy


class EthComm(object):
    def __init__(self, host, port, EOL='\r\n', timeout=3.0):
        object.__init__(self)
        self.sock = None
        self.isBusy = False
        self.host = host
        self.port = port
        self.EOL = EOL
        self.timeout = timeout

    def connectSock(self):
        """| Connect socket if self.sock is None.
        :return: - socket
        """
        if self.sock is None:
            s = self.createSock()
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))

            self.sock = s

        return self.sock

    def createSock(self):
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def closeSock(self):
        """| Close the socket.
        :raise: Exception if closing socket has failed
        """
        try:
            self.sock.close()
        except:
            pass

        self.sock = None

    @busy
    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        """| Send one command and return one response.
        :param cmdStr: (str) The command to send.
        :param doClose: If True (the default), the device socket is closed before returning.
        :param cmd: on going command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        fullCmd = ('%s%s' % (cmdStr, self.EOL)).encode('utf-8')

        s = self.connectSock()

        try:
            s.sendall(fullCmd)

        except:
            self.closeSock()
            raise

        reply = self.getOneResponse(sock=s, cmd=cmd)

        if doClose:
            self.closeSock()

        return reply

    def getOneResponse(self, sock=None, cmd=None):
        """| Attempt to receive data from the socket.
        :param sock: socket
        :param cmd: command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """
        if sock is None:
            sock = self.connectSock()

        ret = self.ioBuffer.getOneResponse(sock=sock, cmd=cmd)
        reply = ret.strip()

        return reply


class BufferedSocket(object):
    """ Buffer the input from a socket and block it into lines. """

    def __init__(self, name, sock=None, loggerName=None, EOL='\n', timeout=3.0):
        self.EOL = EOL
        self.sock = sock
        self.name = name
        self.timeout = timeout

        self.buffer = ''

    def getOutput(self, sock=None, timeout=None, cmd=None):
        """ Block/timeout for input, then return all (<=1kB) available input. """

        if sock is None:
            sock = self.sock
        if timeout is None:
            timeout = self.timeout

        readers, writers, broken = select.select([sock.fileno()], [], [], timeout)
        if len(readers) == 0:
            msg = "Timed out reading character from %s" % self.name
            raise IOError(msg)

        return sock.recv(1024).decode('utf8', 'ignore')

    def getOneResponse(self, sock=None, timeout=None, cmd=None):
        """ Return the next available complete line. Fetch new input if necessary.
        Args
        ----
        sock : socket
           Uses self.sock if not set.
        timeout : float
           Uses self.timeout if not set.
        Returns
        -------
        str or None : a single line of response text, with EOL character(s) stripped.
        """

        while self.buffer.find(self.EOL) == -1:
            more = self.getOutput(sock=sock, timeout=timeout, cmd=cmd)
            msg = '%s added: %r' % (self.name, more)

            self.buffer += more

        eolAt = self.buffer.find(self.EOL)
        ret = self.buffer[:eolAt]

        self.buffer = self.buffer[eolAt + len(self.EOL):]

        return ret


class bsh(EthComm):
    states = ['init', 'shut_open', 'red_open', 'blue_open', 'bia_on']
    cmdList = ['shut_open', 'shut_close', 'red_open', 'blue_open', 'red_close', 'blue_close', 'bia_on', 'bia_off']
    statList = {'init': 0,
                'bia_on': 10,
                'shut_open': 20,
                'blue_open': 30,
                'red_open': 40}

    statwords = {'init': 82, 'bia_on': 82, 'shut_open': 100, 'blue_open': 98, 'red_open': 84}

    def __init__(self, mode, host, port):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.
        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        self.name = 'bsh'
        self.mode = mode
        EthComm.__init__(self,
                         host=host,
                         port=port,
                         EOL='\r\n')

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    def startComm(self):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()
        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.sim = BshSim()  # Create new simulator

        self.ioBuffer = BufferedSocket(self.name + "IO", EOL='ok\r\n')
        s = self.connectSock()

    def setBiaConfig(self, biaPeriod=None, biaDuty=None, biaStrobe=None):
        """| Send new parameters for bia
        :param cmd: current command,
        :param biaPeriod: bia period for strobe mode
        :param biaDuty: bia duty cycle
        :param biaStrobe: **on** | **off**
        :type biaPeriod: int
        :type biaDuty: int
        :type biaStrobe: str
        :raise: Exception if a command has failed
        """

        if biaPeriod is not None:
            self.sendOneCommand('set_period%i' % biaPeriod)

        if biaDuty is not None:
            self.sendOneCommand('set_duty%i' % biaDuty)

        if biaStrobe is not None:
            self.sendOneCommand('pulse_%s' % biaStrobe)

    def getBiaConfig(self):
        """|publish bia configuration keywords.
        - biaStrobe=off|on
        - biaConfig=period,duty
        :param cmd: current command,
        :param doClose: if True close socket
        :raise: Exception if a command has failed
        """

        biastat = self.sendOneCommand("get_param")
        strobe, period, duty = biastat.split(',')
        strobe = 'on' if int(strobe) else 'off'
        return strobe, int(period), int(duty)

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = EthComm.createSock(self)

        return s


def createSimData():
    sim = bsh('simulation', 'toto', 5432)
    sim.startComm()

    simData = {}

    for cmdStr in sim.cmdList:
        res = []

        for state in sim.states:
            sim.sendOneCommand('init')
            sim.sendOneCommand(state)
            stat = sim.sendOneCommand('status')

            ret = sim.sendOneCommand(cmdStr)
            newstat = int(sim.sendOneCommand('status'))
            res.append((state, (ret, newstat)))

        simData[cmdStr] = dict(res)

    return simData
