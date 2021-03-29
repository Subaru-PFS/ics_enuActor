#!/usr/bin/env python


import argparse
import logging

import actorcore.ICC
import numpy as np
from enuActor.utils import serverIsUp, waitForTcpServer
from pfs.utils.instdata import InstData
from twisted.internet import reactor


class enuActor(actorcore.ICC.ICC):
    stateList = ['OFF', 'LOADED', 'ONLINE']
    state2logic = dict([(state, val) for val, state in enumerate(stateList)])
    logic2state = {v: k for k, v in state2logic.items()}

    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName,
                                   configFile=configFile,
                                   modelNames=name)
        self.addModels([self.name])
        self.instData = InstData(self)
        self.logger.setLevel(logLevel)

        self.everConnected = False
        self.onsubstate = 'IDLE'

    @property
    def states(self):
        """Return list of controller current state."""
        return [controller.states.current for controller in self.controllers.values()]

    @property
    def substates(self):
        """Return list of controller current substate."""
        return [controller.substates.current for controller in self.controllers.values()]

    @property
    def state(self):
        """Return current enu meta state as a result of underlying state machine."""
        if not self.controllers.values():
            return 'OFF'

        minLogic = np.min([enuActor.state2logic[state] for state in self.states])
        return enuActor.logic2state[minLogic]

    @property
    def substate(self):
        """Return current enu meta substate as a result of underlying state machine."""
        if not self.controllers.values():
            return 'IDLE'

        if 'FAILED' in self.substates:
            substate = 'FAILED'
        elif list(set(self.substates)) == ['IDLE']:
            substate = 'IDLE'
        else:
            substate = self.onsubstate

        return substate

    @property
    def monitors(self):
        """Return controller monitor value."""
        return dict([(name, controller.monitor) for name, controller in self.controllers.items()])

    def controllerKey(self):
        """Return formatted keyword listing all loaded controllers."""
        controllerNames = list(self.controllers.keys())
        key = 'controllers=%s' % (','.join([c for c in controllerNames]) if controllerNames else None)

        return key

    def reloadConfiguration(self, cmd):
        """Reload configuration file."""
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        """Attach all controllers."""
        if self.everConnected is False:
            try:
                doAutoStart = self.config.getboolean(self.name, 'autoStart')
            except:
                doAutoStart = False
            try:
                self.connect('pdu')
                reactor.callLater(3, self.genPersistedKeys)
                if doAutoStart:
                    reactor.callLater(5, self.autoStart)


            except Exception as e:
                self.logger.warn('text=%s' % self.strTraceback(e))

            self.everConnected = True

    def genPersistedKeys(self):
        """Make sure that hexapodMoved and gratingMoved are generated as soon as enuActor start."""
        cmd = self.bcast
        try:
            hexapodMoved, = self.instData.loadKey('hexapodMoved')
        except:
            hexapodMoved = np.nan

        try:
            gratingMoved, = self.instData.loadKey('gratingMoved')
        except:
            gratingMoved = np.nan

        cmd.inform(f'hexapodMoved={hexapodMoved:0.6f}')
        cmd.inform(f'gratingMoved={gratingMoved:0.6f}')

    def autoStart(self, cmd=None):
        """start each device automatically."""
        cmd = self.bcast if cmd is None else cmd

        self.callCommand('slit status')
        self.startDevice(cmd, 'temps', outlet='temps')
        self.startDevice(cmd, 'rexm', outlet='pows,ctrl')
        self.startDevice(cmd, 'biasha', outlet='pows,ctrl')

    def startDevice(self, cmd, device, outlet=None):
        """power up device if not on the network, wait and connect"""
        host, port = self.config.get(device, 'host'), self.config.get(device, 'port')
        mode = self.config.get(device, 'mode')
        if not serverIsUp(host, port):
            if outlet is not None:
                self.callCommand(f'power on={outlet}')
                waitForTcpServer(host, port, cmd=cmd, mode=mode)
                self.connect(device)

    def ownCall(self, cmd, cmdStr, failMsg='', timeLim=20):
        """Call enuActor itself.
        :param cmd: current command.
        :param cmdStr: command string.
        :param failMsg: failure message.
        :type cmdStr: str
        :type failMsg: str
        :raise: Exception if cmdVar.didFail and failMsg !=''.
        """
        cmdVar = self.cmdr.call(actor=self.name, cmdStr=cmdStr, forUserCmd=cmd, timeLim=timeLim)

        if cmdVar.didFail:
            cmd.warn(cmdVar.replyList[-1].keywords.canonical(delimiter=';'))
            if failMsg:
                raise RuntimeError(failMsg)

        return cmdVar

    def connect(self, controller, cmd=None, **kwargs):
        """Connect the given controller name.

        :param controller: controller name.
        :param cmd: current command.
        :type controller: str
        :raise: Exception with warning message.
        """
        cmd = self.bcast if cmd is None else cmd
        cmd.inform('text="attaching %s..."' % controller)
        try:
            actorcore.ICC.ICC.attachController(self, controller, cmd=cmd, **kwargs)
        except:
            cmd.warn(self.controllerKey())
            cmd.warn('text="failed to connect controller %s' % controller)
            raise

        cmd.inform(self.controllerKey())

    def disconnect(self, controller, cmd=None):
        """Disconnect the given controller name.

        :param controller: controller name.
        :param cmd: current command.
        :type controller: str
        :raise: Exception with warning message.
        """
        cmd = self.bcast if cmd is None else cmd
        cmd.inform('text="detaching %s..."' % controller)
        try:
            actorcore.ICC.ICC.detachController(self, controller, cmd=cmd)

        except:
            cmd.warn(self.controllerKey())
            cmd.warn('text="failed to disconnect controller %s"')
            raise

        cmd.inform(self.controllerKey())

    def monitor(self, controller, period, cmd=None):
        """Change controller monitoring value.

        :param controller: controller name.
        :param period: monitoring value(secs).
        :param cmd: current command.
        :type controller: str
        :type period: int
        :raise: Exception with warning message.
        """
        cmd = self.bcast if cmd is None else cmd

        if controller not in self.controllers:
            raise ValueError('controller %s is not connected' % controller)

        self.controllers[controller].monitor = period
        cmd.warn('text="setting %s loop to %gs"' % (controller, period))

    def updateStates(self, cmd, onsubstate=False):
        """Generate metaFSM keyword.

        :param cmd: current command.
        :param onsubstate: current substate.
        :type onsubstate: str
        """
        self.onsubstate = onsubstate if onsubstate and onsubstate != 'IDLE' else self.onsubstate

        cmd.inform('metaFSM=%s,%s' % (self.state, self.substate))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.INFO, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default='enu', type=str, nargs='?',
                        help='identity')
    args = parser.parse_args()

    theActor = enuActor(args.name,
                        productName='enuActor',
                        configFile=args.config,
                        logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
