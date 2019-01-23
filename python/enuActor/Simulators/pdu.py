import socket
import time


class PduSim(socket.socket):

    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.sendall = self.fakeSend
        self.recv = self.fakeRecv

        self.buf = []
        self.channels = {}
        for nb in ['o%s' % (str(i + 1).zfill(2)) for i in range(15)]:
            self.channels[nb] = 'off'

        self.vals = {'volt': '110',
                     'curr': '2',
                     'pow': '220'}

    def connect(self, server):
        (ip, port) = server
        time.sleep(0.5)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

        self.buf.append('Login: \r\n>')

    def fakeSend(self, cmdStr):
        time.sleep(0.1)
        cmdStr = cmdStr.decode()

        if cmdStr == 'teladmin\r\n':
            self.buf.append('Password: \r\n>')

        elif cmdStr == 'toto\r\n':
            self.buf.append('Logged in successfully \r\n>')

        elif 'read status' in cmdStr:
            __, __, nb, __ = cmdStr.split(' ')
            self.buf.append('%s Outlet %s %s\r\n> ' % (cmdStr, nb[1:], self.channels[nb]))

        elif 'read meter dev' in cmdStr:
            __, __, __, val, __ = cmdStr.split(' ')
            self.buf.append('%s %s\r\n\r\n> ' % (cmdStr, self.vals[val]))

        elif 'sw o' in cmdStr:
            __, nb, state, __ = cmdStr.split(' ')
            self.channels[nb] = state
            self.buf.append('%s  Outlet<%s> command is setting\r\n>' % (cmdStr, nb))

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
