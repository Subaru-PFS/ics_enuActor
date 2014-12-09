#!/usr/bin/env python
# encoding: utf-8


class RuleError(Exception):
    """Define rule and how it is displaied """
    PRIORITY_DEFAULT = 1
    def __init__(self, reason, lvl=PRIORITY_DEFAULT):
        super(RuleError, self).__init__(self)
        self._reason = reason
        self._priority = lvl

    @property
    def strerror(self):
        return self._reason

    @property
    def errno(self):
        return self._priority

    def __str__(self):
        return "{}".format(
                #self.__class__.__name__,
                self.strerror)
                #self.errno


class CfgFileErr(RuleError):

    """ Error related to configuration files.

    .. todo:: Specify file error
    """

    pass


class CommErr(RuleError):

    """CommErr are all the error related to the communication
    between PC and Device. """

    pass


class DeviceErr(RuleError):

    """ DeviceErr are all the error related to the device and controller.
        When a DeviceErr occures the current state of the FSM go to fail."""

    def __init__(self, reason, device = 'device', lvl=RuleError.PRIORITY_DEFAULT):
        RuleError.__init__(self, reason, lvl=RuleError.PRIORITY_DEFAULT)
        self.device = device

    def __str__(self):
        return  "[%s %s] '%s'" % (
                self.device,
                self._priority,
                self._reason)
