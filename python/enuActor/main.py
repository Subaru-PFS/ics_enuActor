#!/usr/bin/env python


import argparse
import logging

import actorcore.ICC
import numpy as np


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
        self.logger.setLevel(logLevel)

        self.everConnected = False
        self.onsubstate = 'IDLE'

    @property
    def states(self):
        return [controller.states.current for controller in self.controllers.values()]

    @property
    def substates(self):
        return [controller.substates.current for controller in self.controllers.values()]

    @property
    def state(self):
        if not self.controllers.values():
            return 'OFF'

        minLogic = np.min([enuActor.state2logic[state] for state in self.states])
        return enuActor.logic2state[minLogic]

    @property
    def substate(self):
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
        return dict([(name, controller.monitor) for name, controller in self.controllers.items()])

    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True

    def monitor(self, controller, period, cmd=None):
        cmd = self.bcast if cmd is None else cmd

        if controller not in self.controllers:
            raise ValueError('controller %s is not connected' % controller)

        self.controllers[controller].monitor = period
        cmd.warn('text="setting %s loop to %gs"' % (controller, period))

    def updateStates(self, cmd, onsubstate=False):
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
