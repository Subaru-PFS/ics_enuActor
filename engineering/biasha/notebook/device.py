import select
import logging

from opscore.utility.qstr import qstr

class Device(object):
    def __init__(self, host, port, EOL='\r\n'):
        object.__init__(self)
        self.name = 'bsh'
        self.host = host
        self.port = port
        self.EOL = EOL
        self.sock = None
        self.ioBuffer = BufferedSocket(self.name + "IO", EOL='ok\r\n')

    def connectSock(self):
        """| Connect socket if self.sock is None.

        :return: - sock in operation
                 - simulator in simulation
        """
        if self.sock is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
            except Exception as e:
                raise Exception("%s failed to create socket" % (self.name))

            try:
                s.connect((self.host, self.port))
            except Exception as e:
                raise Exception("%s failed to connect socket" % (self.name))

            self.sock = s

        return self.sock

    def closeSock(self):
        """| Close the socket.

        :raise: Exception if closing socket has failed
        """

        if self.sock is not None:
            try:
                self.sock.close()

            except Exception as e:
                self.sock = None
                raise Exception("%s failed to close socket : %s" % (self.name))

        self.sock = None

    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
        """| Send one command and return one response.

        :param cmdStr: (str) The command to send.
        :param doClose: If True (the default), the device socket is closed before returning.
        :param cmd: on going command
        :return: reply : the single response string, with EOLs stripped.
        :raise: IOError : from any communication errors.
        """

        fullCmd = "%s%s" % (cmdStr, self.EOL)

        s = self.connectSock()
        try:
            s.sendall(fullCmd)

        except Exception as e:
            raise Exception(
                "%s failed to send %s" % (self.name.upper(), fullCmd))

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


