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

    Errors = {
        1000 : "Device not started yet.",
        1001 : "NotImplemented"
    }


    def __init__(self, reason, code=None, device = 'Device', lvl=RuleError.PRIORITY_DEFAULT):
        RuleError.__init__(self, reason, lvl=RuleError.PRIORITY_DEFAULT)
        self.reason =reason
        self.device = device
        self.code = code

    def __str__(self):
        if self.code ==None:
            return  "Err%s %s: '%s'" % (
                    self.device,
                    self._priority,
                    self._reason)
        else:
            return "Err%s%s: %s. Details: %s" % (
                    self.device,
                    self.code,
                    DeviceErr.Errors[self.code],
                    self.reason)
