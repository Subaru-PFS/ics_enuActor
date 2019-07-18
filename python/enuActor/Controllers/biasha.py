__author__ = 'alefur'
import logging
import time
from datetime import datetime as dt
from datetime import timedelta

import enuActor.utils.bufferedSocket as bufferedSocket
from enuActor.Simulators.biasha import BiashaSim
from enuActor.utils.fsmThread import FSMThread


def busyEvent(event):
    return [dict(name='%s_%s' % (src, event['name']), src='BUSY', dst=event['dst']) for src in event['src']]


class biasha(FSMThread, bufferedSocket.EthComm):
    status = {0: ('close', 'off'),
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
            {'name': 'init', 'src': ['IDLE', 'EXPOSING', 'OPENRED', 'OPENBLUE', 'BIA'], 'dst': 'IDLE'},
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

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.finishExposure = False
        self.abortExposure = False
        self.sim = BiashaSim()

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

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('biasha', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('biasha', 'host'),
                                        port=int(self.actor.config.get('biasha', 'port')),
                                        EOL='\r\n')

        self.defaultBiaParams = dict(period=int(self.actor.config.get('biasha', 'bia_period')),
                                     duty=int(self.actor.config.get('biasha', 'bia_duty')),
                                     strobe=self.actor.config.get('biasha', 'bia_strobe'))

    def _openComm(self, cmd):
        """| Open socket with biasha board or simulate it.
        | Called by FSMDev.loadDevice()

        :param cmd: on going command
        :raise: socket.error if the communication has failed with the controller
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')
        s = self.connectSock()

    def _closeComm(self, cmd):
        """| Close communication.
        | Called by FSMThread.stop()

        :param cmd: on going command
        """
        self.closeSock()

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.getState(cmd=cmd)

    def _init(self, cmd):
        """| Initialise the interlock board

        - Send the bia config to the interlock board
        - Init the interlock state machine

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """
        self.setBiaConfig(cmd, **self.defaultBiaParams)
        self._gotoState('init', cmd=cmd)

    def getStatus(self, cmd):
        """| Call biasha.biaStatus() and biasha.shutterStatus()

        :param cmd: on going command
        :raise: Exception if a command has failed
        """
        state = self.getState(cmd=cmd)
        self.biaStatus(cmd=cmd, state=state)
        self.shutterStatus(cmd=cmd, state=state)

    def getState(self, cmd):
        """| Call biasha.biaStatus() and biasha.shutterStatus()

        :param cmd: on going command
        :raise: Exception if a command has failed
        """
        state = self._state(cmd)
        cmd.inform('biasha=%d' % state)
        return state

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

    def expose(self, cmd, exptime, shutter):
        """| Command opening and closing of shutters with a chosen exposure time and generate keywords:
        | dateobs : exposure starting time isoformatted
        | transientTime : opening+closing shutters transition time
        | exptime : absolute exposure time

        :param cmd: on going command
        :param exptime: Exposure time
        :param shutter: which shutter to open
        :type exptime: float
        :type shutter: str
        """
        self.finishExposure = False
        self.abortExposure = False

        try:
            self.gotoState(cmd=cmd, cmdStr='init')

            start = dt.utcnow()
            self.gotoState(cmd=cmd, cmdStr='%s_open' % shutter)
            transientTime1 = (dt.utcnow() - start).total_seconds()

            if 'open' not in self.shutterStatus(cmd):
                raise RuntimeError('shutter(s) not open')

            integEnd = self._waitUntil(cmd, start, exptime)
            self.gotoState(cmd=cmd, cmdStr='%s_close' % shutter)

            if not integEnd:
                self.shutterStatus(cmd)
                raise RuntimeWarning('exposure aborted')

            end = dt.utcnow()
            transientTime2 = (end - integEnd).total_seconds()

            if self.shutterStatus(cmd) != 'close':
                raise RuntimeError('shutter(s) not close')

            cmd.inform('dateobs=%s' % start.isoformat())
            cmd.inform('transientTime=%.3f' % (transientTime1 + transientTime2))
            cmd.inform('exptime=%.3f' % ((end - start).total_seconds() - 0.5 * (transientTime1 + transientTime2)))

        except:
            cmd.warn('exptime=nan')
            raise

    def shutterStatus(self, cmd, state=None):
        """| Get shutters status and generate shutters keywords

        :param cmd: on going command
        :raise: RuntimeError if statword and current state are incoherent
        """
        try:
            state = self.getState(cmd) if state is None else state
            shutters, __ = biasha.status[state]
            statword = self._statword(cmd)

            cmd.inform('shb=%s,%s,%s' % (statword[0], statword[1], statword[2]))
            cmd.inform('shr=%s,%s,%s' % (statword[3], statword[4], statword[5]))

            if biasha.statwords[shutters] != statword:
                raise RuntimeError('statword %s  does not match current state' % statword)
            cmd.inform('shutters=%s' % shutters)

        except:
            cmd.warn('shutters=undef')
            raise

        return shutters

    def biaStatus(self, cmd, state=None):
        """| Get bia status and generate bia keywords

        :param cmd: on going command
        :raise: Exception if communication has failed
        """
        try:
            state = self.getState(cmd) if state is None else state
            __, bia = biasha.status[state]
            strobe, period, duty = self._biaConfig(cmd)
            phr1, phr2 = self._photores(cmd)

            cmd.inform('photores=%d,%d' % (phr1, phr2))
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

    def _state(self, cmd):
        """| check and return biasha board current state .

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        state = self.sendOneCommand("status", cmd=cmd)
        return int(state)

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

    def _photores(self, cmd):
        """| check and return current photoresistances values.

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        photores = self.sendOneCommand("read_phr", cmd=cmd)
        phr1, phr2 = photores.split(',')

        return int(phr1), int(phr2)

    def _gotoState(self, cmdStr, cmd):
        """| try to reach required state in bsh low level state machine
        :param cmdStr: command string
        :param cmd: current command,
        :raise: RuntimeError if a command has failed
        """
        reply = self.sendOneCommand(cmdStr, cmd=cmd)

        if reply == '':
            return reply
        elif reply == 'n':
            raise RuntimeError('bsh has replied nok, %s inappropriate in current state ' % cmdStr)
        else:
            raise RuntimeError('error : %s' % reply)

    def _waitUntil(self, cmd, start, exptime, ti=0.001):
        """| Temporization, check every 0.01 sec for a user abort command.

        :param cmd: current command,
        :param exptime: exposure time,
        :type exptime: float
        :raise: Exception("Exposure aborted by user") if the an abort command has been received
        """
        tlim = start + timedelta(seconds=exptime)
        inform = dt.utcnow()
        cmd.inform("integratingTime=%.2f" % (tlim - inform).total_seconds())
        cmd.inform("elapsedTime=%.2f" % (inform - start).total_seconds())

        while dt.utcnow() < tlim:
            if self.finishExposure:
                break
            if self.abortExposure:
                return 0
            if (dt.utcnow() - inform).total_seconds() > 2:
                inform = dt.utcnow()
                cmd.inform("elapsedTime=%.2f" % (inform - start).total_seconds())
            time.sleep(ti)

        return dt.utcnow()

    def doAbort(self):
        self.abortExposure = True
        while self.currCmd:
            pass
        return

    def doFinish(self):
        self.finishExposure = True
        while self.currCmd:
            pass
        return

    def leaveCleanly(self, cmd):
        self.monitor = 0
        self.doFinish()

        try:
            self.gotoState(cmd, 'init')
            self.getStatus(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self._closeComm(cmd=cmd)

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        ret = bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)

        if 'ok' in ret:
            return ret.split('ok')[0]
        else:
            raise IOError('unexpected return from biasha ret:%s' % ret)

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def biaOverHeat(self, cmd=None):
        cmd = self.actor.bcast if cmd is None else cmd

        if self.substates.current == 'BIA' and self.actor.controllers['temps'].biaOverHeat:
            cmd.warn('text="bia temp above safety threshold, turning off ..."')
            self.gotoState(cmd, cmdStr='bia_off')
            self.biaStatus(cmd)

    def handleTimeout(self, cmd=None):
        FSMThread.handleTimeout(self, cmd=cmd)
        self.biaOverHeat(cmd=cmd)
