#!/usr/bin/env python


import argparse
import logging

import ics.utils.fsm.fsmActor as fsmActor
import ics.utils.tcp.utils as tcpUtils


class enuActor(fsmActor.FsmActor):
    knownControllers = ['biasha', 'iis', 'pdu', 'rexm', 'slit', 'temps']
    # we dont start the hexapod by default.
    startingControllers = list(set(knownControllers) - {'slit'})

    outletConfig = dict(slit='slit', biasha='ctrl,pows', rexm='ctrl,pows', temps='temps', iis=None, pdu=None)

    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        fsmActor.FsmActor.__init__(self, name,
                                   productName=productName,
                                   configFile=configFile,
                                   logLevel=logLevel)

        self.addModels([name])

    def letsGetReadyToRumble(self):
        """ Just startup nicely."""

        toStart = list(set(enuActor.startingControllers) - set(self.ignoreControllers))

        if 'pdu' not in toStart:
            # thats weird but devices could be powered by something else so just force simulation and proceed.
            pduMode = 'simulation'
        else:
            pduMode = None

        self.connect('pdu', mode=pduMode)

        for controller in toStart:
            if controller == 'pdu':
                continue
            self.startController(controller, fromThread=False)

        self.callCommand('slit status')

    def startController(self, controller, cmd=None, mode=None, fromThread=True):
        """power up device if not on the network, wait and connect"""

        def getConfig(field):
            """ Retrieve host and port from config file. """
            return self.config.get(controller, field).strip()

        cmd = self.bcast if cmd is None else cmd
        mode = getConfig('mode') if mode is None else mode
        host, port = getConfig('host'), int(getConfig('port'))

        # for iis and pdu there is no outlet per se, actually it might change for iis.
        outlet = enuActor.outletConfig[controller]

        if mode == 'operation' and not tcpUtils.serverIsUp(host, port) and outlet is not None:
            # most devices can be power cycled, so try it.
            self.powerSwitch(outlet, 'on', cmd=cmd, fromThread=fromThread)
            tcpUtils.waitForTcpServer(host, port, cmd=cmd)

        self.connect(controller, cmd=cmd, mode=mode)

    def powerSwitch(self, outlet, state, cmd=None, fromThread=True):
        """power up/down pdu outlet from main thread or controller thread."""
        cmd = self.bcast if cmd is None else cmd
        cmdStr = f'power {state}={outlet}'
        cmd.inform(f'text="{cmdStr} outlet ..."')

        if fromThread:
            cmdVar = self.cmdr.call(actor=self.name, cmdStr=cmdStr, forUserCmd=cmd, timeLim=60)

            if cmdVar.didFail:
                cmd.warn(cmdVar.replyList[-1].keywords.canonical(delimiter=';'))
                raise ValueError(f'failed to {cmdStr} outlet ...')

        else:
            self.callCommand(cmdStr)


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
