__author__ = 'alefur'
import logging

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.Simulators.bsh import BshSim


def busyEvent(event):
    return [dict(name='%s_%s' % (src, event['name']), src='BUSY', dst=event['dst']) for src in event['src']]


class bsh(FSMDev, QThread, bufferedSocket.EthComm):
    bshFSM = {0: ('close', 'off'),
              10: ('close', 'on'),
              20: ('open', 'off'),
              30: ('openblue', 'off'),
              40: ('openred', 'off')}

    statwords = {'close': '010010',
                 'open': '100100',
                 'openblue': '100010',
                 'openred': '010100'}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        substates = ['IDLE', 'FAILED', 'BUSY', 'EXPOSING', 'OPENRED', 'OPENBLUE', 'BIA']
        events = [
            {'name': 'init', 'src': ['EXPOSING', 'OPENRED', 'OPENBLUE', 'BIA'], 'dst': 'IDLE'},
            {'name': 'shut_open', 'src': ['IDLE', 'OPENRED', 'OPENBLUE'], 'dst': 'EXPOSING'},
            {'name': 'shut_close', 'src': ['EXPOSING', 'OPENRED', 'OPENBLUE'], 'dst': 'IDLE'},
            {'name': 'red_open', 'src': ['IDLE'], 'dst': 'OPENRED'},
            {'name': 'red_open', 'src': ['OPENBLUE'], 'dst': 'EXPOSING'},
            {'name': 'red_close', 'src': ['EXPOSING'], 'dst': 'OPENBLUE'},
            {'name': 'red_close', 'src': ['OPENRED'], 'dst': 'IDLE'},
            {'name': 'blue_open', 'src': ['IDLE'], 'dst': 'OPENBLUE'},
            {'name': 'blue_open', 'src': ['OPENRED'], 'dst': 'EXPOSING'},
            {'name': 'blue_close', 'src': ['EXPOSING'], 'dst': 'OPENRED'},
            {'name': 'blue_close', 'src': ['OPENBLUE'], 'dst': 'IDLE'},
            {'name': 'bia_on', 'src': ['IDLE'], 'dst': 'BIA'},
            {'name': 'bia_off', 'src': ['BIA'], 'dst': 'IDLE'}]

        events += sum([busyEvent(event) for event in events], [])
        events += [{'name': 'fail', 'src': 'BUSY', 'dst': 'FAILED'},
                   {'name': 'lock', 'src': ['IDLE', 'EXPOSING', 'OPENRED', 'OPENBLUE', 'BIA'], 'dst': 'BUSY'}]

        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.stopExposure = False
        self.sock = None

        self.sim = None
        self.currCmd = False

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    def start(self, cmd=None, doInit=True, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('bsh', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('bsh', 'host'),
                                        port=int(self.actor.config.get('bsh', 'port')),
                                        EOL='\r\n')

        self.defaultPeriod = int(self.actor.config.get('bsh', 'bia_period'))
        self.defaultDuty = int(self.actor.config.get('bsh', 'bia_duty'))
        self.defaultStrobe = self.actor.config.get('bsh', 'bia_strobe')

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.sim = BshSim()  # Create new simulator

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='ok\r\n')
        s = self.connectSock()

    def init(self, cmd):
        """| Initialise the interlock board

        - Send the bia config to the interlock board
        - Init the interlock state machine

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """
        self.setBiaConfig(cmd, self.defaultPeriod, self.defaultDuty, self.defaultStrobe)
        self._gotoState('init', cmd=cmd)

    def gotoState(self, cmd, cmdStr):
        current = self.substates.current

        if self.substates.can(cmdStr):
            self.substates.lock()

            try:
                self._gotoState(cmdStr, cmd=cmd)
                cmdStr = '%s_%s' % (current, cmdStr)

            except:
                self.substates.fail()
                raise

        self.substates.trigger(cmdStr)

    def getStatus(self, cmd, doFinish=True):
        """| Call bsh.checkStatus() and generate shutters, bia keywords

        :param cmd: on going command
        :param doFinish: if True finish the command
        """
        cmd.inform('bshFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('bshMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            self.checkStatus(cmd)
            self.closeSock()

        if doFinish:
            cmd.finish()

    def checkStatus(self, cmd):
        """| Call bsh.biaStatus() and bsh.shutterStatus()

        :param cmd: on going command
        :raise: Exception if a command has failed
        """
        try:
            self.biaStatus(cmd=cmd)
        except:
            raise
        finally:
            self.shutterStatus(cmd=cmd)

    def shutterStatus(self, cmd):
        """| Get shutters status and generate shutters keywords

        :param cmd: on going command
        :raise: RuntimeError if statword and current state are incoherent
        """
        try:
            shutters, __ = bsh.bshFSM[self._state(cmd)]
            statword = self._statword(cmd)

            cmd.inform('shb=%s,%s,%s' % (statword[0], statword[1], statword[2]))
            cmd.inform('shr=%s,%s,%s' % (statword[3], statword[4], statword[5]))

            if bsh.statwords[shutters] != statword:
                raise RuntimeError('statword %s  does not match current state' % statword)
            cmd.inform('shutters=%s' % shutters)

        except:
            cmd.warn('shutters=undef')
            raise

    def biaStatus(self, cmd):
        """| Get bia status and generate bia keywords

        :param cmd: on going command
        :raise: Exception if communication has failed
        """
        try:
            __, bia = bsh.bshFSM[self._state(cmd)]
            strobe, period, duty = self._biaConfig(cmd)

            cmd.inform('biaConfig=%d,%d,%d' % (strobe, period, duty))
            cmd.inform('bia=%s' % bia)
        except:
            cmd.warn('bia=undef')
            raise

    def setBiaConfig(self, cmd, period=None, duty=None, strobe=None):
        """| Send new parameters for bia

        :param cmd: current command,
        :param period: bia period for strobe mode
        :param duty: bia duty cycle
        :param strobe: **on** | **off**
        :type period: int
        :type duty: int
        :type strobe: str
        :raise: Exception if a command has failed
        """

        if period is not None:
            if not (0 <= period < 65536):
                raise ValueError('period not in range 0:65535')

            self.sendOneCommand('set_period%i' % period, cmd=cmd)

        if duty is not None:
            if not (0 <= duty < 256):
                raise ValueError('duty not in range 0:255')

            self.sendOneCommand('set_duty%i' % duty, cmd=cmd)

        if strobe is not None:
            self.sendOneCommand('pulse_%s' % strobe, cmd=cmd)

        self.biaStatus(cmd)

    def _state(self, cmd):
        """| check and return interlock board current state .

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        ilockState = self.sendOneCommand("status", cmd=cmd)

        return int(ilockState)

    def _statword(self, cmd):
        """| check and return shutter status word .

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        statword = self.sendOneCommand("statword", cmd=cmd)

        return bin(int(statword))[-6:]

    def _biaConfig(self, cmd):
        """| check and return current bia configuration : strobe_mode_on, strobe_period, duty_cycle.

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        biastat = self.sendOneCommand("get_param", cmd=cmd)
        strobe, period, duty = biastat.split(',')

        return int(strobe), int(period), int(duty)

    def _gotoState(self, cmdStr, cmd):
        """| try to reach required state in bsh low level state machine
        :param cmdStr: command string
        :param cmd: current command,
        :raise: RuntimeError if a command has failed
        """
        reply = self.sendOneCommand(cmdStr, cmd=cmd)

        if reply != "":
            raise RuntimeError("bsh has replied nok, cmdStr : %s inappropriate in current state " % cmdStr)

        return reply

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
