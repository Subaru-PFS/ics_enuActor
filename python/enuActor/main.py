#!/usr/bin/env python


import argparse
import logging

import actorcore.ICC
import numpy as np
from twisted.internet import reactor


class enuActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName,
                                   configFile=configFile)
        self.logger.setLevel(logLevel)

        self.everConnected = False
        self.onsubstate = 'IDLE'

        self.monitors = dict()

        self.statusLoopCB = self.statusLoop

    @property
    def state(self):
        states = ['OFF', 'LOADED', 'ONLINE']
        state2logic = dict([(state, val) for val, state in enumerate(states)])
        logic2state = dict([(val, state) for val, state in enumerate(states)])
        if self.controllers.values():
            minLogic = np.min([state2logic[ctrl.states.current] for ctrl in self.controllers.values()])
            state = logic2state[minLogic]
        else:
            state = 'OFF'

        return state

    @property
    def substate(self):

        if self.controllers.values():
            if False in [controller.substates.current == 'IDLE' for controller in self.controllers.values()]:
                substate = self.onsubstate
            else:
                substate = 'IDLE'
        else:
            substate = 'IDLE'

        return substate

    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True

            # reactor.callLater(10, self.status_check)

    def statusLoop(self, controller):
        try:
            self.callCommand("%s status" % (controller))
        except:
            pass

        if self.monitors[controller] > 0:
            reactor.callLater(self.monitors[controller],
                              self.statusLoopCB,
                              controller)

    def monitor(self, controller, period, cmd=None):
        if controller not in self.monitors:
            self.monitors[controller] = 0

        running = self.monitors[controller] > 0
        self.monitors[controller] = period

        if (not running) and period > 0:
            cmd.warn('text="starting %gs loop for %s"' % (self.monitors[controller],
                                                          controller))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="adjusted %s loop to %gs"' % (controller, self.monitors[controller]))

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
