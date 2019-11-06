import socket
import time


class PduSim(socket.socket):

    def __init__(self):
        """Fake pdu tcp server."""
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.buf = []
        self.channels = {}
        for nb in ['o%s' % (str(i + 1).zfill(2)) for i in range(16)]:
            self.channels[nb] = 'off'

        self.vals = {'volt': '240',
                     'curr': '0.5',
                     'pow': '120'}

    def connect(self, server):
        """Fake the connection to tcp server."""
        (ip, port) = server
        time.sleep(0.2)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

        self.buf.append('Login: \r\n>')

    def sendall(self, cmdStr, flags=None):
        """Send fake packets, append fake response to buffer."""
        cmdStr = cmdStr.decode()
        time.sleep(0.05)
        if cmdStr == 'teladmin\r\n':
            self.buf.append('Password: ')

        elif 'pdu.enu_sm' in cmdStr:
            self.buf.append('Telnet server 1.1\r\n\r\n> ')

        elif 'pfsait' in cmdStr:
            self.buf.append('Telnet server 1.1\r\n\r\n> ')

        elif 'read status' in cmdStr:
            __, __, nb, __ = cmdStr.split(' ')
            self.buf.append('%s%s\r\n\r\n> ' % (cmdStr, self.channels[nb]))

        elif 'read meter olt' in cmdStr:
            _, _, _, _, val, _ = cmdStr.split(' ')
            self.buf.append('%s%s\r\n\r\n> ' % (cmdStr, self.vals[val]))

        elif 'read meter dev' in cmdStr:
            _, _, _, val, _ = cmdStr.split(' ')
            self.buf.append('%s%s\r\n\r\n> ' % (cmdStr, self.vals[val]))

        elif 'sw o' in cmdStr:
            __, nb, state, __ = cmdStr.split(' ')
            self.channels[nb] = state
            self.buf.append('%sOutlet<%s> command is setting\r\n\r\n> ' % (cmdStr, nb))

    def recv(self, buffersize, flags=None):
        """Return and remove fake response from buffer."""
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
