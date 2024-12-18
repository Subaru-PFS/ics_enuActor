__author__ = 'alefur'

import logging
from importlib import reload

import enuActor.Simulators.biasha as simulator
import ics.utils.tcp.bufferedSocket as bufferedSocket
import ics.utils.time as pfsTime
import numpy as np
from ics.utils.fsm.fsmThread import FSMThread

reload(simulator)


def busyEvent(event):
    return [dict(name='%s_%s' % (src, event['name']), src='BUSY', dst=event['dst']) for src in event['src']]


class biasha(FSMThread, bufferedSocket.EthComm):
    # for state machine, not need to temporize before init
    forceInit = True

    status = {0: ('close', 'off'),
              10: ('close', 'on'),
              20: ('open', 'off'),
              30: ('openblue', 'off'),
              40: ('openred', 'off')}

    statwords = {'close': '010010',
                 'open': '100100',
                 'openblue': '100010',
                 'openred': '010100'}

    # shutterMask to cmdShutter
    cmdShutter = {0: 'none', 1: 'blue', 2: 'red', 3: 'shut'}
    shutterToMask = dict([(v, k) for k, v in cmdShutter.items()])

    # socket properties
    maxIOAttempt = 5
    maintainConnectionRate = 60
    maintainConnectionMargin = 5
    genElapsedTimeRate = 2

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
            {'name': 'bia_off', 'src': ['BIA'], 'dst': 'IDLE'},
            {'name': 'ack', 'src': ['FAILED'], 'dst': 'IDLE'}]

        events += sum([busyEvent(event) for event in events], [])
        events += [{'name': 'fail', 'src': 'BUSY', 'dst': 'FAILED'},
                   {'name': 'lock', 'src': ['IDLE', 'EXPOSING', 'OPENRED', 'OPENBLUE', 'BIA'], 'dst': 'BUSY'}]

        FSMThread.__init__(self, actor, name, events=events, substates=substates)

        self.finishExposure = False
        self.abortExposure = False
        self.redResolution = None
        self.sim = simulator.BiashaSim()

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
        self.mode = self.controllerConfig['mode'] if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.controllerConfig['host'],
                                        port=self.controllerConfig['port'],
                                        EOL='\r\n')

        self.defaultBiaParams = dict(period=self.controllerConfig['bia_period'],
                                     duty=self.controllerConfig['bia_duty'],
                                     power=self.controllerConfig['bia_power'],
                                     strobe=self.controllerConfig['bia_strobe'])

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

    def expose(self, cmd, exptime, shutterMask, visit=-1):
        """exposure routine with given exptime and shutter. Generate dateobs, transientTime and exptime keywords.

        :param cmd: current command.
        :param exptime: Exposure time.
        :param shutter: which shutter to open : shut (both), blue, red.
        :type exptime: float
        :type shutterMask: int
        """
        self.finishExposure = False
        self.abortExposure = False
        self.redResolution = None

        # translate shutterMask to commanded shutters.
        cmdShutter = biasha.cmdShutter[shutterMask]

        def shutterTransition(desiredState):
            """ command shutters to the desired state and check we reached desired state. """
            # make sure socket is open at the beginning that really should be marginal but ...
            self.connectSock()
            start = pfsTime.timestamp()
            # skip that part is no shutters needs to be commanded.
            if shutterMask:
                self.gotoState(cmd=cmd, cmdStr=f'{cmdShutter}_{desiredState}')
            # roughly time the transientTime, ultimately should come from the arduino itself but for now...
            end = pfsTime.timestamp()

            if shutterMask and desiredState not in self.shutterStatus(cmd):
                raise RuntimeError(f'{cmdShutter}_{desiredState} transition failed...')

            # lamps exposure requires a signal from the shutters to fire the lamps, so we are just pretending.
            if not shutterMask:
                cmd.inform(f'shutters={desiredState}')

            return start, end

        def waitUntil(integrationStartedAt, exptime):
            """Wait for the end of integration, check for an abort/finish command."""

            def remainingTime():
                return integrationEnd - now

            def maintainConnection():
                """Maintain connection with biasha board during a long exposure, generate shutter keywords."""
                try:
                    self.shutterStatus(cmd)
                except Exception as e:
                    cmd.warn('text=%s' % self.actor.strTraceback(e))
                    self._closeComm(cmd=cmd)

            integrationEnd = integrationStartedAt + exptime

            now = genElapsedTime = genStatus = pfsTime.timestamp()

            cmd.inform("integratingTime=%.2f" % exptime)
            cmd.inform("elapsedTime=%.2f" % (now - integrationStartedAt))

            while remainingTime() > 0:
                # check for early abort/finish
                if self.finishExposure or self.abortExposure:
                    return

                # dont generate elapsedTime at too fast rate.
                if now - genElapsedTime > biasha.genElapsedTimeRate:
                    genElapsedTime = pfsTime.timestamp()
                    cmd.inform("elapsedTime=%.2f" % (now - integrationStartedAt))

                # keep generating status to avoid STS timeout.
                if now - genStatus > self.maintainConnectionRate and remainingTime() > self.maintainConnectionMargin:
                    maintainConnection()
                    # raise a failure after trying to many times.
                    # if nAttempt > self.maxIOAttempt:
                    #    raise RuntimeError(f'failed to maintain connection after {nAttempt} attempts...')

                    # actually I dont think it makes sense operationally, currently, exposure would fail
                    # but since the shutter was open, you may want to read data in anycase.
                    genStatus = pfsTime.timestamp()

                pfsTime.sleep.millisec()
                now = pfsTime.timestamp()

        try:
            # OK, kind of scary to do that. if bia is on, the actor stateMachine does not reject the exposure command.
            # and the init turn off the bia really quickly so the arduino state machine also allows it, but
            # given the decay of the LED is not instantaneous, you get some extra photons on your detector.
            # you just basically bypassed the interlock, for certainly few photons, but still...
            # self.gotoState(cmd=cmd, cmdStr='init')

            # declaring exposure
            startExp = self._startExposure(shutterMask)

            # hanging on red resolution now.
            try:
                self.redResolution = self.actor.controllers['rexm'].position
            except KeyError:
                cmd.warn('text="rexm controller not connected, redResolution set to undef for this exposure..."')
                self.redResolution = 'undef'

            # open shutters.
            integrationStartedAt, openReturnedAt = shutterTransition('open')
            # wait for exposure time.
            waitUntil(integrationStartedAt, exptime)
            # close shutters.
            integrationEndedAt, closeReturnedAt = shutterTransition('close')

            transientTime1 = openReturnedAt - integrationStartedAt
            transientTime2 = closeReturnedAt - integrationEndedAt
            totalExptime = closeReturnedAt - integrationStartedAt

            transientTime1M, fullyOpenTimeM, transientTime2M = self._finishExposure(startExp)
            cmd.inform(f'biashaMeasures={transientTime1M},{fullyOpenTimeM},{transientTime2M}')
            totalExptimeM = fullyOpenTimeM + transientTime1M + transientTime2M

            # using measured values if they are available or stick to actor values.
            transientTime1 = transientTime1 if np.isnan(transientTime1M) else transientTime1M
            totalExptime = totalExptime if np.isnan(totalExptimeM) else totalExptimeM
            transientTime2 = transientTime2 if np.isnan(transientTime2M) else transientTime2M

            if self.abortExposure:
                raise RuntimeWarning('exposure aborted')

            totalTransient = transientTime1 + transientTime2
            exptime = totalExptime - totalTransient / 2

            cmd.inform('dateobs=%s' % pfsTime.Time.fromtimestamp(integrationStartedAt).isoformat())
            cmd.inform('transientTime=%.3f' % (transientTime1 + transientTime2))
            cmd.inform('exptime=%.3f' % exptime)
            cmd.inform('shutterMask=0x%01x' % shutterMask)
            cmd.inform('shutterTimings=%d,%s,%s,%s,%s' % (visit,
                                                          pfsTime.Time.fromtimestamp(integrationStartedAt).isoformat(),
                                                          pfsTime.Time.fromtimestamp(openReturnedAt).isoformat(),
                                                          pfsTime.Time.fromtimestamp(integrationEndedAt).isoformat(),
                                                          pfsTime.Time.fromtimestamp(closeReturnedAt).isoformat()))
            # latching a red resolution keyword for headers.
            cmd.inform(f"redResolution={visit},{self.redResolution}")
        except:
            cmd.warn('exptime=nan')
            raise

    def shutterStatus(self, cmd, state=None):
        """Get shutters status and generate shutters keywords.

        :param cmd: current command.
        :raise: RuntimeError if statword and current state are incoherent.
        """
        try:
            if state is None:
                state = self.getState(cmd)
                cmd.inform('%sFSM=%s,%s' % (self.name, self.states.current, self.substates.current))

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
            if state is None:
                state = self.getState(cmd)
                cmd.inform('%sFSM=%s,%s' % (self.name, self.states.current, self.substates.current))

            __, bia = biasha.status[state]
            duty, period, power = self._biaConfig(cmd)
            phr1, phr2 = self._photores(cmd)
            strobe = duty != 100
            biaPower = 0 if bia == 'off' else round(power * 100 / 255)

            pulseOn = period * duty / 100
            pulseOff = period - pulseOn

            cmd.inform('photores=%d,%d' % (phr1, phr2))
            cmd.inform('biaConfig=%d,%d,%d,%d' % (strobe, period, power, duty))
            cmd.inform('biaStatus=%d,%d,%d,%d,%d' % (biaPower, period, duty, pulseOn, pulseOff))
            cmd.inform('bia=%s' % bia)

        except:
            cmd.warn('bia=undef')
            raise

    def setBiaConfig(self, cmd, period=None, duty=None, power=None, strobe=None):
        """Send new parameters for bia.

        :param cmd: current command.
        :param period: bia period for strobe mode.
        :param duty: bia strobe duty cycle.
        :param power: bia led input power.
        :param strobe: **on** | **off**.
        :type period: int
        :type duty: int
        :type power: int
        :type strobe: str
        :raise: Exception with warning message.
        """
        if duty is not None and duty == 100:
            period = None
            duty = None
            strobe = False

        if period is not None:
            if not (0 < period < 2 ** 16):
                raise ValueError('period not in range 1:65535')

            self.sendOneCommand('set_period%i' % period, cmd=cmd)

        if duty is not None:
            if not (0 < duty <= 100):
                raise ValueError('duty not in range 1:100')

            self.sendOneCommand('set_duty%i' % duty, cmd=cmd)

        if power is not None:
            if not (0 < power <= 100):
                raise ValueError('power not in range 1:100')

            power = round(255 * power / 100)
            self.sendOneCommand('set_power%i' % power, cmd=cmd)

        if strobe is not None:
            cmdStr = 'pulse_on' if strobe else 'pulse_off'
            self.sendOneCommand(cmdStr, cmd=cmd)

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
        duty, period, power = biastat.split(',')

        return int(duty), int(period), int(power)

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
        try:
            reply = self.sendOneCommand(cmdStr, cmd=cmd)
        except RuntimeError:
            raise RuntimeError('biasha has replied nok, %s inappropriate in current state ' % cmdStr)

        if reply:
            raise RuntimeError('error : %s' % reply)

    def _startExposure(self, shutterMask):
        """Declaring a new exposure."""
        startExp = False

        if shutterMask:
            try:
                reply = self.sendOneCommand('start_exp')
                if not reply:
                    startExp = True
                elif reply == "exposure already declared.":
                    self.sendOneCommand('cancel_exp')
            except:
                # Since we can live without this, I'm not cancelling the exposure, even if this does not work."""
                pass

        return startExp

    def _finishExposure(self, useBiashaMeasures):
        """Finish exposure and get exposure measures from biasha board."""

        def msToSecs(ms):
            """convert milliseconds to seconds."""
            return float(ms) / 1000

        transientTime1 = fullyOpenTime = transientTime2 = np.NaN

        if useBiashaMeasures:
            try:
                reply = self.sendOneCommand('finish_exp')
                transientTime1, fullyOpenTime, transientTime2 = map(msToSecs, reply.split(','))
            except:
                # Since we can live without this, I'm not cancelling the exposure, even if this does not work."""
                pass

        return transientTime1, fullyOpenTime, transientTime2

    def doAbort(self):
        """Abort current exposure."""
        self.abortExposure = True

        # see ics.utils.fsm.fsmThread.LockedThread
        self.waitForCommandToFinish()

        return

    def doFinish(self):
        """Finish current exposure. """
        self.finishExposure = True

        # see ics.utils.fsm.fsmThread.LockedThread
        self.waitForCommandToFinish()

        return

    def leaveCleanly(self, cmd):
        """clear and leave.

        :param cmd: current command.
        """
        self.monitor = 0
        self.doFinish()

        if self.substates.current != "FAILED":
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

        if not 'ok' in ret:
            raise IOError('unexpected return from biasha ret:%s' % ret)

        reply, __ = ret.split('ok')

        if reply == 'n':
            raise RuntimeError(f'biasha {cmdStr} returned nok !')

        return reply

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
