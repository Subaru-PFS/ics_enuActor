#!/usr/bin/env python
# encoding: utf-8

import threading
import Queue
import logging
import functools

try:
    from opscore.utility.tback import tback
except Exception, e:
    print e

"""
Description:
   tq = self.actor.devices[deviceName]
   msg = QMsg(tq.pingMsg, cmd=cmd)
   tq.queue.put(msg)

 or:

   tq = self.actor.devices[deviceName]
   tq.putMsg(tq.pingMsg, cmd=cmd)
   tq.callMsgLater(10.0, tq.pingMsg, cmd=cmd)
"""


class QThread(threading.Thread):
    def __init__(self, actor, name, timeout=2, isDaemon=True, queueClass=Queue.PriorityQueue):
        """ A thread with a queue. The thread's .run() method pops items off its public .queue and executes them. """
        super(QThread, self).__init__(name=name)
        self.setDaemon(isDaemon)
        self.actor = actor
        self.timeout = timeout
        self.exitASAP = False
        self.queue = queueClass()
        self.started = False
        self.ret = None

    def _realCmd(self, cmd=None):
        """ Returns a callable cmd instance. If the passed in cmd is None, return the actor's bcast cmd. """

        return cmd if cmd else self.actor.bcast

    def putMsg(self, method, *argl, **argd):
        """ send ourself a new message.

        :param method: a function or bound method to call
        :param \*argl: the arguments to the method.
        :param \*argd: the arguments dict to the method
        """

        qmsg = QMsg(method, *argl, **argd)
        self.queue.put(qmsg)

    def sendLater(self, msg, deltaTime, priority=1):
        """ Send ourself a QMsg after deltaTime seconds. """

        def _push(queue=self.queue, msg=msg):
            queue.put(msg)

        t = threading.Timer(deltaTime, _push)
        t.start()

        return t

    def handleTimeout(self):
        """ Called when the .get() times out. Intended to be overridden. """

        self._realCmd(None).diag('text="%s thread is alive (exiting=%s)"' % (self.name, self.exitASAP))
        if self.exitASAP:
            raise SystemExit()

    def exitMsg(self, cmd=None):
        """ handler for the "exit" message. Spits out a message and arranges for the .run() method to exit.  """

        print('in %s exitMsg' % (self.name))
        raise SystemExit()

    def pingMsg(self, cmd=None):
        """ handler for the 'ping' message. """

        self._realCmd(cmd).inform('text="thread %s is alive!"' % (self.name))

    def run(self):
        """ Main run loop for this thread. """

        while True:
            try:
                msg = self.queue.get(timeout=self.timeout)
                qlen = self.queue.qsize()
                if qlen > 0:
                    self._realCmd(cmd).debug("%s thread has %d items after a .get()" % (self.name, qlen))
                try:
                    method = getattr(msg, 'method')
                except AttributeError as e:
                    raise AttributeError("thread %s received a message without a method to call: %s" % (self.name, msg))
                try:
                    print "performing %s" % method.func_name
                    self.ret = method()
                    self.queue.task_done()
                    print "task done"
                except SystemExit:
                    return
                except Exception as e:
                    self._realCmd().warn('text="%s: uncaught exception running %s: %s"' %
                                            (self.name, method, e))
                    print e
            except Queue.Empty:
                self.handleTimeout()
            except Exception, e:
                try:
                    emsg = 'text="%s thread got unexpected exception: %s"' % (self.name, e)
                    self._realCmd().diag(emsg)
                    tback("DualModeDevice", e)
                except:
                    print emsg
                    tback("DualModeDevice", e)

class QMsg(object):
    DEFAULT_PRIORITY = 5

    def __init__(self, method, *argl, **argd):
        """ Create a new QMsg, which will resolve to method(*argl, **argd).

        d = {}
        qm = QMsg(d.__setitem__, 'abc', 42)

        qt = QThread(....)
        qm = QMsg(qt.pingMsg, cmd)

        """

        priority = None
        self.priority = priority if (priority != None) else QMsg.DEFAULT_PRIORITY
        if priority == None:
            self.priority = priority
        self.method = functools.partial(method, *argl, **argd)

    def __lt__(self, other):
        """ Support sorting of QMsg instances, based on the .priority. Used by PriorityQueue. """

        return self.priority < other.priority
