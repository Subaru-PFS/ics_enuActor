__author__ = 'alefur'

import logging
import time

from enuActor.Controllers import pdu
from enuActor.Simulators.pdu import PduSim
from ics.utils.fsm.fsmThread import FSMThread


class iis(pdu.pdu):
    warmingTime = dict(hgar=15, neon=15)
    names = warmingTime.keys()

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
        :type name: str
        """
        substates = ['IDLE', 'WARMING', 'FAILED']
        events = [{'name': 'warming', 'src': 'IDLE', 'dst': 'WARMING'},
                  {'name': 'idle', 'src': ['WARMING', ], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['WARMING', ], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('WARMING', self.warming)
        self.sim = PduSim()
        self.warmupTime = dict()
        self.abortWarmup = False

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    @property
    def sourcesOn(self):
        return [source for source in self.names if not self.isOff(source)]

    def _loadCfg(self, cmd, mode=None):
        """Load iis configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        mode = self.actor.config.get('iis', 'mode') if mode is None else mode
        pdu.pdu._loadCfg(self, cmd=cmd, mode=mode, name='pdu')

        for source in iis.names:
            if source not in self.powerPorts.keys():
                raise ValueError(f'{source} : unknown source')

    def getStatus(self, cmd):
        """Get and generate iis keywords.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        for source in iis.names:
            state = self.getState(source, cmd=cmd)
            cmd.inform(f'{source}={state},{self.elapsed(source)}')

    def getState(self, source, cmd):
        """Get current light source state.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        state = self.sendOneCommand('read status o%s simple' % self.powerPorts[source], cmd=cmd)
        if state == 'pending':
            # the outlet is currently in a intermediate state so wait and retry.
            time.sleep(2)
            return self.getState(source, cmd=cmd)

        return state

    def switchOff(self, cmd, sources):
        """Switch on/off sources dictionary.

        :param cmd: current command.
        :param powerPorts: list(hgar,neon).
        :type powerPorts: list.
        :raise: Exception with warning message.
        """
        for source in sources:
            self.warmupTime.pop(source, None)

        powerOff = dict([(self.powerPorts[name], 'off') for name in sources])
        return pdu.pdu.switching(self, cmd, powerOff)

    def warming(self, cmd, sourcesOn, warmingTime, ti=0.01):
        """Switch on source lamp and wait for iis.warmingTime.

        :param cmd: current command.
        :param sourcesOn: light source lamp to switch on.
        :type sourcesOn: list
        :raise: Exception with warning message.
        """
        start = time.time()
        self.abortWarmup = False

        for source in sourcesOn:
            if self.isOff(source):
                outlet = self.powerPorts[source]
                self.warmupTime[source] = time.time()
                self.safeOneCommand('sw o%s on imme' % outlet, cmd=cmd)
                self.portStatus(cmd, outlet=outlet)

        while time.time() < start + warmingTime:
            time.sleep(ti)
            self.handleTimeout()
            if self.abortWarmup:
                raise UserWarning('sources warmup aborted')

    def isOff(self, source):
        """Check if light source is currently off.

        :param source: source name.
        :type source: str
        :return: state
        :rtype: bool
        """
        state, __ = self.actor.models[self.actor.name].keyVarDict[source].getValue()
        return not bool(state)

    def elapsed(self, source):
        """Check for how much time source has been powered on.

        :param source: source name.
        :type source: str
        :return: elapsed time
        :rtype: float
        """
        try:
            return int(round(time.time() - self.warmupTime[source]))
        except KeyError:
            return 0

    def doAbort(self):
        """Abort warmup.
        """
        self.abortWarmup = True
        while self.currCmd:
            pass
        return

    def leaveCleanly(self, cmd):
        """Clear and leave.

        :param cmd: current command.
        """
        self.monitor = 0
        self.doAbort()

        try:
            self.switchOff(cmd, self.sourcesOn)
            self.getStatus(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self._closeComm(cmd=cmd)
