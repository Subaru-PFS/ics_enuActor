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
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
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
        """Return True if self.mode=='simulation', return False if self.mode='operation'."""
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    @property
    def biaOverHeat(self):
        """Check temps biaOverHeat flag."""
        try:
            ret = self.actor.controllers['temps'].biaOverHeat
        except KeyError:
            ret = False

        return ret

    def _loadCfg(self, cmd, mode=None):
        """Load biasha configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
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
        """Open socket with biasha board or simulate it.
        
        :param cmd: current command.
        :raise: socket.error if the communication has failed.
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')
        s = self.connectSock()

    def _closeComm(self, cmd):
        """Close socket.

        :param cmd: current command.
        """
        self.closeSock()

    def _testComm(self, cmd):
        """Test communication.

        :param cmd: current command.
        :raise: Exception if the communication has failed with the controller.
        """
        self.getState(cmd=cmd)

    def _init(self, cmd):
        """Initialise biasha board : send default bia config and init biasha embedded state machine.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        self.setBiaConfig(cmd, **self.defaultBiaParams)
        self._gotoState('init', cmd=cmd)

    def getStatus(self, cmd):
        """Get bia and shutters status.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        state = self.getState(cmd=cmd)
        self.biaStatus(cmd=cmd, state=state)
        self.shutterStatus(cmd=cmd, state=state)

    def getState(self, cmd):
        """Get biasha current state from embedded state machine.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        state = self._state(cmd)
        cmd.inform('biasha=%d' % state)
        return state

    def gotoState(self, cmd, cmdStr):
        """trigger cmdStr transition.

        :param cmd: current command.
        :param cmdStr: transition command.
        :type cmdStr: str
        :raise: Exception with warning message.
        """
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
        """exposure routine with given exptime and shutter. Generate dateobs, transientTime and exptime keywords.

        :param cmd: current command.
        :param exptime: Exposure time.
        :param shutter: which shutter to open : shut (both), blue, red.
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
        """Get shutters status and generate shutters keywords.

        :param cmd: current command.
        :raise: RuntimeError if statword and current state are incoherent.
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
        """Get bia status and generate bia keywords.

        :param cmd: current command.
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
        """Send new parameters for bia.

        :param cmd: current command.
        :param period: bia period for strobe mode.
        :param duty: bia duty cycle.
        :param strobe: **on** | **off**.
        :type period: int
        :type duty: int
        :type strobe: str
        :raise: Exception with warning message.
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
        """Check and return biasha board current state.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        state = self.sendOneCommand("status", cmd=cmd)
        return int(state)

    def _statword(self, cmd):
        """Check and return shutter status word.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        statword = self.sendOneCommand("statword", cmd=cmd)

        return bin(int(statword))[-6:]

    def _biaConfig(self, cmd):
        """Check and return current bia configuration : strobeOn, strobePeriod, strobeDutyCycle.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        biastat = self.sendOneCommand("get_param", cmd=cmd)
        strobe, period, duty = biastat.split(',')

        return int(strobe), int(period), int(duty)

    def _photores(self, cmd):
        """Check and return current photoresistances values.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        photores = self.sendOneCommand("read_phr", cmd=cmd)
        phr1, phr2 = photores.split(',')

        return int(phr1), int(phr2)

    def _gotoState(self, cmdStr, cmd):
        """Try to reach required state in biasha embedded state machine.

        :param cmdStr: command string.
        :param cmd: current command.
        :raise: Exception with warning message.
        """
        reply = self.sendOneCommand(cmdStr, cmd=cmd)

        if reply == '':
            return reply
        elif reply == 'n':
            raise RuntimeError('biasha has replied nok, %s inappropriate in current state ' % cmdStr)
        else:
            raise RuntimeError('error : %s' % reply)

    def _waitUntil(self, cmd, start, exptime, ti=0.001):
        """Temporization, check every 0.001 sec for an abort command.

        :param cmd: current command.
        :param exptime: exposure time.
        :type exptime: float
        :return: end as datetime.datetime, 0 if abortExposure.
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
        """Abort current exposure.
        """
        self.abortExposure = True
        while self.currCmd:
            pass
        return

    def doFinish(self):
        """Finish current exposure.
        """
        self.finishExposure = True
        while self.currCmd:
            pass
        return

    def leaveCleanly(self, cmd):
        """clear and leave.

        :param cmd: current command.
        """
        self.monitor = 0
        self.doFinish()

        try:
            self.gotoState(cmd, 'init')
            self.getStatus(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self._closeComm(cmd=cmd)

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        """Send cmdStr to biasha board and handle response, raise IOError if ok not in ret.

        :param cmdStr: string to send.
        :param doClose: close socket.
        :param cmd: current command.
        :type cmdStr: str
        :type doClose: bool
        :return: response with ok stripped.
        """
        ret = bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)

        if 'ok' in ret:
            return ret.split('ok')[0]
        else:
            raise IOError('unexpected return from biasha ret:%s' % ret)

    def createSock(self):
        """create socket in operation, simulator otherwise.
        """
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def handleTimeout(self, cmd=None):
        """call FSMThread.handleTimeout, if bia is on check for biaOverHeat.

        :param cmd: current command.
        """
        FSMThread.handleTimeout(self, cmd=cmd)
        cmd = self.actor.bcast if cmd is None else cmd

        if self.substates.current == 'BIA' and self.biaOverHeat:
            cmd.warn('text="bia temp above safety threshold, turning off ..."')
            self.gotoState(cmd, cmdStr='bia_off')
            self.biaStatus(cmd)
