__author__ = 'alefur'
import logging
import time

from enuActor.Controllers import pdu
from enuActor.Simulators.pdu import PduSim
from enuActor.utils.fsmThread import FSMThread


class iis(pdu.pdu):
    warmingTime = 15.0
    arcs = ['hgar']

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
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
        self.doStop = False

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file.

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        mode = self.actor.config.get('iis', 'mode') if mode is None else mode
        pdu.pdu._loadCfg(self, cmd=cmd, mode=mode)

        for arc in iis.arcs:
            if arc not in self.powerPorts.keys():
                raise ValueError(f'{arc} : unknown arc')

    def getStatus(self, cmd):
        """| get and generate iis keywords

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        for arc in iis.arcs:
            state = self.arcState(arc, cmd=cmd)
            cmd.inform(f'{arc}={state}')

    def arcState(self, arc, cmd):
        """| get arc state

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        state = self.sendOneCommand('read status o%s simple' % self.powerPorts[arc], cmd=cmd)
        if state == 'pending':
            return self.getState(arc, cmd=cmd)

        return state

    def warming(self, cmd, arcOn, ti=0.01):
        """ switch on and warm up arc lamp

        :param cmd : current command
        :param arcOn : arc lamp list to switch on,
        :raise: Exception if the communication has failed with the controller
        """
        for outlet in arcOn:
            self.sendOneCommand('sw o%s on imme' % outlet, cmd=cmd)
            self.portStatus(cmd, outlet=outlet)

        if arcOn:
            start = time.time()
            self.doStop = False
            while time.time() < start + iis.warmingTime:
                time.sleep(ti)
                self.handleTimeout()
                if self.doStop:
                    raise RuntimeError('iis warmup aborted')

    def isOff(self, arc):
        """| check if arc lamp is currently off

        :param arc: arc lamp
        :type arc:str
        :return state
        """
        state = self.actor.models[self.actor.name].keyVarDict[arc].getValue()
        return not bool(state)
