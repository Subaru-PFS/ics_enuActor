__author__ = 'alefur'
import logging

from actorcore.QThread import QThread


class top(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """__init__.
        This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor
        :param name: controller name
        :type name: str
        """
        self.monitor = 0
        self.currCmd = False
        QThread.__init__(self, actor, name, timeout=15)

    def start(self, cmd=None, doInit=None, mode=None):
        QThread.start(self)

    def stop(self, cmd=None):
        self.exit()

    def handleTimeout(self, cmd=None):
        if self.exitASAP:
            raise SystemExit()
