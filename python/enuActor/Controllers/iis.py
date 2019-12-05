__author__ = 'alefur'
import logging
import time

from enuActor.Controllers import pdu
from enuActor.Simulators.pdu import PduSim
from enuActor.utils import wait
from enuActor.utils.fsmThread import FSMThread


class iis(pdu.pdu):
    warmingTime = dict(hgar=15, neon=15)
    arcs = ['hgar', 'neon']

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
        self.abortWarmup = False

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def _loadCfg(self, cmd, mode=None):
        """Load iis configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        mode = self.actor.config.get('iis', 'mode') if mode is None else mode
        pdu.pdu._loadCfg(self, cmd=cmd, mode=mode)

        for arc in iis.arcs:
            if arc not in self.powerPorts.keys():
                raise ValueError(f'{arc} : unknown arc')

    def getStatus(self, cmd):
        """Get and generate iis keywords.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        for arc in iis.arcs:
            state = self.arcState(arc, cmd=cmd)
            cmd.inform(f'{arc}={state}')

    def arcState(self, arc, cmd):
        """Get current arc lamp state.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        state = self.sendOneCommand('read status o%s simple' % self.powerPorts[arc], cmd=cmd)
        if state == 'pending':
            wait(secs=2)
            return self.arcState(arc, cmd=cmd)

        return state

    def warming(self, cmd, arcOn, warmingTime, ti=0.01):
        """Switch on arc lamp and wait for iis.warmingTime.

        :param cmd: current command.
        :param arcOn: arc lamp list to switch on.
        :type arcOn: list
        :raise: Exception with warning message.
        """
        for outlet in arcOn:
            self.sendOneCommand('sw o%s on imme' % outlet, cmd=cmd)
            self.portStatus(cmd, outlet=outlet)

        if arcOn:
            start = time.time()
            self.abortWarmup = False
            while time.time() < start + warmingTime:
                time.sleep(ti)
                self.handleTimeout()
                if self.abortWarmup:
                    raise RuntimeError('iis warmup aborted')

    def isOff(self, arc):
        """Check if arc lamp is currently off.

        :param arc: arc lamp.
        :type arc: str
        :return: state
        :rtype: bool
        """
        state = self.actor.models[self.actor.name].keyVarDict[arc].getValue()
        return not bool(state)

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

        powerOff = dict([(self.powerPorts[name], 'off') for name in self.arcs])

        try:
            self.switching(cmd, powerPorts=powerOff)
            self.getStatus(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self._closeComm(cmd=cmd)
