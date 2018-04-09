#!/usr/bin/env python


import argparse
import logging
import configparser

from twisted.internet import reactor
import actorcore.ICC
from opscore.utility.qstr import qstr


class enuActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName,
                                   configFile=configFile)
        self.logger.setLevel(logLevel)

        self.everConnected = False

        self.monitors = dict()

        self.statusLoopCB = self.statusLoop

        self.monitor("bsh", 120)
        self.monitor("slit", 120)
        self.monitor("rexm", 120)

    def reloadConfiguration(self, cmd):
        logging.info("reading config file %s", self.configFile)

        try:
            newConfig = configparser.ConfigParser()
            newConfig.read(self.configFile)
        except Exception as e:
            if cmd:
                cmd.fail('text=%s' % (qstr("failed to read the configuration file, old config untouched: %s" % (e))))
            raise

        self.config = newConfig
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching Controllers")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True
            logging.info("All Controllers started")

    def attachController(self, controller, instanceName=None, cmd=None):

        cmd = cmd if cmd is not None else self.bcast
        actorcore.ICC.ICC.attachController(self, controller, instanceName)
        self.controllers[controller].fsm.startLoading(cmd=cmd)

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
        cmd = cmd if cmd is not None else self.bcast

        if controller not in self.monitors:
            self.monitors[controller] = 0

        running = self.monitors[controller] > 0
        self.monitors[controller] = period

        if (not running) and period > 0:

            cmd.warn('text="starting %gs loop for %s"' % (self.monitors[controller], controller))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="adjusted %s loop to %gs"' % (controller, self.monitors[controller]))

    def strTraceback(self, e):

        oneLiner = self.cmdTraceback(e)
        return qstr("command failed: %s" % oneLiner)


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
