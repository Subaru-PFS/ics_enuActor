import logging
import select
import socket


class EthComm(object):
    def __init__(self, host, port, EOL='\r\n'):
        object.__init__(self)
        self.sock = None
        self.host = host
        self.port = port
        self.EOL = EOL

    def connectSock(self, timeout=3.0):
        """| Connect socket if self.sock is None.

        :return: - socket
        """
        if self.sock is None:
            s = self.createSock()
            s.settimeout(timeout)
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

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        """| Send one command and return one response.

        :param cmdStr: (str) The command to send.
        :param doClose: If True (the default), the device socket is closed before returning.
        :param cmd: on going command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """

        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = ('%s%s' % (cmdStr, self.EOL)).encode('utf-8')
        self.logger.debug('sending %r', fullCmd)

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

        self.logger.debug('received %r', reply)

        return reply


class BufferedSocket(object):
    """ Buffer the input from a socket and block it into lines. """

    def __init__(self, name, sock=None, loggerName=None, EOL='\n', timeout=3.0,
                 logLevel=logging.INFO):
        self.EOL = EOL
        self.sock = sock
        self.name = name
        self.logger = logging.getLogger(loggerName)
        self.logger.setLevel(logLevel)
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
            cmd.warn('text="Timed out reading character from %s"' % self.name)
            raise IOError

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
            try:
                more = self.getOutput(sock=sock, timeout=timeout, cmd=cmd)
                if not more:
                    raise IOError

            except IOError:
                return ''
            msg = '%s added: %r' % (self.name, more)
            self.logger.debug(msg)
            self.buffer += more

        eolAt = self.buffer.find(self.EOL)
        ret = self.buffer[:eolAt]

        self.buffer = self.buffer[eolAt + len(self.EOL):]

        return ret
