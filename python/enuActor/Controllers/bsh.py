__author__ = 'alefur'
import datetime
import logging
import time
from datetime import datetime as dt

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from enuActor.Simulators.bsh import BshSim


class bsh(FSMDev, QThread, bufferedSocket.EthComm):
    ilockFSM = {0: ('close', 'off'),
                10: ('close', 'on'),
                20: ('open', 'off'),
                30: ('openblue', 'off'),
                40: ('openred', 'off')}

    shut_stat = [{0: 'close', 1: 'open'}, {0: 'open', 1: 'close'}, {0: 'ok', 1: 'error'}]
    in_position = {0: '010010',
                   10: '010010',
                   20: '100100',
                   30: '100010',
                   40: '010100'}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        substates = ['IDLE', 'EXPOSING', 'FAILED']
        events = [{'name': 'expose', 'src': 'IDLE', 'dst': 'EXPOSING'},
                  {'name': 'idle', 'src': ['EXPOSING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['EXPOSING'], 'dst': 'FAILED'},
                  ]

        bufferedSocket.EthComm.__init__(self)
        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('EXPOSING', self.expose)

        self.shState = 'undef'
        self.biaState = 'undef'

        self.stopExposure = False
        self.ilockState = 0
        self.sock = None
        self.sim = None
        self.EOL = '\r\n'

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='ok\r\n')

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

    @property
    def shuttersClosed(self):
        return self.shState == 'close'

    def start(self, cmd=None, doInit=True, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice().
        | Convert to world tool and home.

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.mode = self.actor.config.get('bsh', 'mode') if mode is None else mode
        self.host = self.actor.config.get('bsh', 'host')
        self.port = int(self.actor.config.get('bsh', 'port'))
        self.biaPeriod = int(self.actor.config.get('bsh', 'bia_period'))
        self.biaDuty = int(self.actor.config.get('bsh', 'bia_duty'))
        self.biaStrobe = self.actor.config.get('bsh', 'bia_strobe')

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        self.sim = BshSim()  # Create new simulator
        s = self.connectSock()

        self.checkStatus(cmd=cmd, doClose=True)

    def init(self, cmd):
        """| Initialise the interlock board, called y device.initDevice().

        - Send the bia config to the interlock board
        - Init the interlock state machine

        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """

        self.setBiaConfig(cmd, self.biaPeriod, self.biaDuty, self.biaStrobe, doClose=False)
        self._sendOrder(cmd, 'init')

    def switch(self, cmd, cmdStr):
        """| *wrapper @busy* handles the state machine.
        | Call bsh._safeSwitch() 

        :param cmd: on going command
        :param cmdStr: String command sent to the board
        :type cmdStr: str
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """

        self._safeSwitch(cmd, cmdStr)

    def expose(self, args):
        """| Command opening and closing of shutters with a chosen exposure time and publish keywords:

        - dateobs : exposure starting time isoformatted
        - transientTime : opening+closing shutters transition time
        - exptime : absolute exposure time

        :param cmd: on going command
        :param exptime: Exposure time
        :type exptime: float
        :return: - True if the command raise no error, fsm (BUSY => IDLE)
                 - False, if the command fail,fsm (BUSY => FAILED)
        """
        cmd, shutter, exptime = args.cmd, args.shutter, args.exptime
        self.checkStatus(cmd)
        try:
            start = dt.utcnow()

            self._safeSwitch(cmd, '%s_open' % shutter)

            transientTime1 = (dt.utcnow() - start).total_seconds()

            self.checkStatus(cmd)
            if self.shState not in ['open', 'openred']:
                raise Exception('OPEN failed')

            stopExposure = self.waitUntil(cmd, exptime - (dt.utcnow() - start).total_seconds())
            if stopExposure:
                raise UserWarning('expose aborted by user')

            if not self.shuttersClosed:
                transientTime2 = dt.utcnow()
                self._safeSwitch(cmd, '%s_close' % shutter)

                end = dt.utcnow()
                transientTime2 = (end - transientTime2).total_seconds()
                self.checkStatus(cmd)
            else:
                end = dt.utcnow()
                transientTime2 = transientTime1

            if not self.shuttersClosed:
                raise Exception('CLOSE failed')

            cmd.inform('dateobs=%s' % start.isoformat())
            cmd.inform('transientTime=%.3f' % (transientTime1 + transientTime2))
            cmd.inform('exptime=%.3f' % ((end - start).total_seconds() - 0.5 * (transientTime1 + transientTime2)))
            self.substates.idle()

        except UserWarning:
            cmd.warn('exptime=nan')
            self.substates.idle()
            self._safeSwitch(cmd, '%s_close' % shutter)

        except:
            cmd.warn('exptime=nan')
            self.substates.fail()
            raise

    def getStatus(self, cmd, doClose=True):
        """| Call bsh._checkStatus() and publish shutters, bia keywords:

        - shutters = fsm_state, mode, position
        - bia = fsm_state, mode, state

        :param cmd: on going command
        :param doFinish: if True finish the command
        """

        cmd.inform('bshFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('bshMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            self.checkStatus(cmd, doClose=doClose)

        cmd.finish()

    def checkStatus(self, cmd, doClose=False):
        """| Get status from bsh board and update controller's attributes.
        | Warn the user if the shutters limits switch state does not match with interlock state machine

        :param cmd: on going command
        :raise: Exception if a command has failed
        :rtype: tuple
        :return: (shuttersPosition, biaState)
        """

        try:
            ilockState = self._ilockStat(cmd)
            statword = self._shutstat(cmd, doClose=doClose)

            cmd.inform('shb=%s,%s,%s' % (statword[0], statword[1], statword[2]))
            cmd.inform('shr=%s,%s,%s' % (statword[3], statword[4], statword[5]))

            if bsh.in_position[ilockState] != statword:
                raise UserWarning('shutters not in position')

            self.shState, self.biaState = bsh.ilockFSM[ilockState]

        except:
            cmd.warn('shutters=undef')
            cmd.warn('bia=undef')
            raise

        cmd.inform('shutters=%s' % self.shState)
        cmd.inform('bia=%s' % self.biaState)

    def getBiaConfig(self, cmd, doClose=False):
        """|publish bia configuration keywords.

        - biaStrobe=off|on
        - biaConfig=period,duty

        :param cmd: current command,
        :param doClose: if True close socket
        :raise: Exception if a command has failed
        """
        biaStrobe, biaPeriod, biaDuty = self._biastat(cmd, doClose=doClose)
        cmd.inform('biaStrobe=%s' % biaStrobe)
        cmd.inform('biaConfig=%i,%i' % (biaPeriod, biaDuty))

        return biaStrobe, biaPeriod, biaDuty

    def setBiaConfig(self, cmd, biaPeriod=None, biaDuty=None, biaStrobe=None, doClose=False):
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
            self._sendOrder(cmd, 'set_period%i' % biaPeriod)

        if biaDuty is not None:
            self._sendOrder(cmd, 'set_duty%i' % biaDuty)

        if biaStrobe is not None:
            self._sendOrder(cmd, 'pulse_%s' % biaStrobe)

        self.biaStrobe, self.biaPeriod, self.biaDuty = self.getBiaConfig(cmd, doClose=doClose)

    def checkInterlock(self, cmdStr, shState=False, biaState=False):
        """| Check transition and raise Exception if cmdStr is violating shutters/bia interlock.

        :param shState: shutter state,
        :param biaState: bia state,
        :param cmdStr: command string
        :type shState: str
        :type biaState: str
        :type cmdStr: str
        :raise: Exception("Transition not allowed")
        """
        shState = shState if shState else self.shState
        biaState = biaState if biaState else self.biaState

        transition = {
            (('close', 'off'), 'shut_open'): '',
            (('close', 'off'), 'red_open'): '',
            (('close', 'off'), 'blue_open'): '',
            (('close', 'off'), 'shut_close'): 'shutters already closed',
            (('close', 'off'), 'red_close'): 'red shutter already closed',
            (('close', 'off'), 'blue_close'): 'blue shutter already closed',
            (('close', 'off'), 'bia_off'): 'bia already off',
            (('close', 'off'), 'bia_on'): '',

            (('close', 'on'), 'shut_open'): 'Interlock !',
            (('close', 'on'), 'red_open'): 'Interlock !',
            (('close', 'on'), 'blue_open'): 'Interlock !',
            (('close', 'on'), 'shut_close'): 'shutters already closed',
            (('close', 'on'), 'red_close'): 'red shutter already closed',
            (('close', 'on'), 'blue_close'): 'blue shutter already closed',
            (('close', 'on'), 'bia_off'): '',
            (('close', 'on'), 'bia_on'): 'bia already on',

            (('open', 'off'), 'shut_open'): 'shutters already open',
            (('open', 'off'), 'red_open'): 'shutters already open',
            (('open', 'off'), 'blue_open'): 'shutters already open',
            (('open', 'off'), 'shut_close'): '',
            (('open', 'off'), 'red_close'): '',
            (('open', 'off'), 'blue_close'): '',
            (('open', 'off'), 'bia_off'): 'bia already off',
            (('open', 'off'), 'bia_on'): 'Interlock !',

            (('openred', 'off'), 'shut_open'): '',
            (('openred', 'off'), 'red_open'): 'shutter red already open',
            (('openred', 'off'), 'blue_open'): '',
            (('openred', 'off'), 'shut_close'): '',
            (('openred', 'off'), 'red_close'): '',
            (('openred', 'off'), 'blue_close'): 'shutter blue already closed',
            (('openred', 'off'), 'bia_off'): 'bia already off',
            (('openred', 'off'), 'bia_on'): 'Interlock !',

            (('openblue', 'off'), 'shut_open'): '',
            (('openblue', 'off'), 'red_open'): '',
            (('openblue', 'off'), 'blue_open'): 'shutter blue already open',
            (('openblue', 'off'), 'shut_close'): '',
            (('openblue', 'off'), 'red_close'): 'shutter red already closed',
            (('openblue', 'off'), 'blue_close'): '',
            (('openblue', 'off'), 'bia_off'): 'bia already off',
            (('openblue', 'off'), 'bia_on'): 'Interlock !',

        }

        ret = transition[(shState, biaState), cmdStr]
        if ret:
            raise UserWarning("Transition not allowed : %s" % ret)

    def waitUntil(self, cmd, exptime, ti=0.01):
        """| Temporization, check every 0.01 sec for a user abort command.

        :param cmd: current command,
        :param exptime: exposure time,
        :type exptime: float
        :raise: Exception("Exposure aborted by user") if the an abort command has been received
        """

        t0 = dt.utcnow()
        tlim = t0 + datetime.timedelta(seconds=exptime)

        cmd.inform("integratingTime=%.2f" % exptime)
        cmd.inform("elapsedTime=%.2f" % (dt.utcnow() - t0).total_seconds())
        inform = dt.utcnow()

        while dt.utcnow() < tlim:
            if self.stopExposure or self.shuttersClosed:
                break
            if (dt.utcnow() - inform).total_seconds() > 2:
                cmd.inform("elapsedTime=%.2f" % (dt.utcnow() - t0).total_seconds())
                inform = dt.utcnow()
            time.sleep(ti)

        return self.stopExposure

    def _safeSwitch(self, cmd, cmdStr):
        """| Send the command string to the interlock board.

        - Command bia or shutters
        - check is not cmdStr is breaking interlock

        :param cmd: on going command
        :param cmdStr: String command sent to the board
        :type cmdStr: str
        :return: - True if the command raise no error
                 - False if the command fail
        """

        try:
            self.checkInterlock(cmdStr)
            self._sendOrder(cmd, cmdStr)

        except UserWarning as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))
            return

    def _ilockStat(self, cmd):
        """| check and return interlock board current state .

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        ilockState = self.sendOneCommand("status", doClose=False, cmd=cmd)

        return int(ilockState)

    def _shutstat(self, cmd, doClose=False):
        """| check and return shutter status word .

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        statword = self.sendOneCommand("statword", doClose=doClose, cmd=cmd)

        return bin(int(statword))[-6:]

    def _biastat(self, cmd, doClose=False):
        """| check and return current bia configuration.

        :param cmd: current command,
        :raise: Exception if a command has failed
        """
        biastat = self.sendOneCommand("get_param", doClose=doClose, cmd=cmd)
        strobe, period, duty = biastat.split(',')
        strobe = 'on' if int(strobe) else 'off'

        return strobe, int(period), int(duty)

    def _sendOrder(self, cmd, cmdStr):
        reply = self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)

        if reply != "":
            raise Exception("%s  %s cmd has replied nok" % (cmdStr, self.name))

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
