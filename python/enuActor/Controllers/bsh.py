#!/usr/bin/env python

import socket
import datetime as dt
from Controllers.device import Device
from Controllers.Simulator.bsh_simu import BshSimulator


class bsh(Device):
    timeout = 5
    ilock_s_machine = {0: ("close", "off"), 1: ("open", "off"), 2: ("close", "on")}
    shut_stat = [{0: "close", 1: "open"}, {0: "open", 1: "close"}, {0: "ok", 1: "error"}]
    transition = {(("close", "off"), "close"): (False, "shutters already closed"),
                  (("close", "off"), "open"): (True, ""),
                  (("close", "off"), "off"): (False, "bia already off"),
                  (("close", "off"), "on"): (True, ""),
                  (("close", "on"), "close"): (False, "shutters already closed"),
                  (("close", "on"), "open"): (False, "Interlock !"),
                  (("close", "on"), "off"): (True, ""),
                  (("close", "on"), "on"): (False, "bia already on"),
                  (("open", "off"), "close"): (True, ""),
                  (("open", "off"), "open"): (False, "shutters already open"),
                  (("open", "off"), "off"): (False, "bia already off"),
                  (("open", "off"), "on"): (False, "Interlock !")}

    def __init__(self, actor, name):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #

        self.shState = "undef"
        self.biaState = "undef"
        super(bsh, self).__init__(actor, name)

    def loadCfg(self, cmd):

        self.currMode = self.actor.config.get('bsh', 'mode')
        self.host = self.actor.config.get('bsh', 'host')
        self.port = int(self.actor.config.get('bsh', 'port'))
        self.bia_period = float(self.actor.config.get('bsh', 'bia_period'))
        self.bia_duty = float(self.actor.config.get('bsh', 'bia_duty'))
        return True

    def startCommunication(self, cmd):

        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) if self.currMode == 'operation' else BshSimulator()
        self._s.settimeout(bsh.timeout)
        cmd.inform("text='Connecting to intlck in ...%s'" % self.currMode)
        try:
            self._s.connect((self.host, self.port))
        except Exception as inst:
            cmd.fail("text=error : %s " % inst)
            return False

        return True

    def initialise(self, cmd):
        import time
        time.sleep(6)
        if not self.errorChecker(cmd, "set_period%i" % self.bia_period):
            return False
        if not self.errorChecker(cmd, "set_duty%i" % int(self.bia_duty * 1024)):
            return False
        if not self.errorChecker(cmd, "init"):
            return False
        return True

    def getStatus(self, cmd):

        if self.safeSend(cmd, self._s, "%s\r\n" % "status"):
            ok, ret = self.safeRecv(cmd, self._s)
            if ok:
                try:
                    ilock_mode = int(ret)
                    self.shState, self.biaState = \
                        bsh.ilock_s_machine[ilock_mode]
                    return self.getShutstat(cmd)
                except ValueError:
                    self.shState, self.biaState = "undef", "undef"
                    cmd.inform('shutters=%s' % self.actor.shState)
                    cmd.fail('bia=%s' % self.actor.biaState)

        return False

    def getShutstat(self, cmd):

        if self.safeSend(cmd, self._s, "%s\r\n" % "statword"):
            ok, ret = self.safeRecv(cmd, self._s)
            if ok:
                for i, shutter in enumerate(["shb", "shr"]):
                    try:
                        cmd.inform("%s=%s" % (shutter, ','.join([bsh.shut_stat[j%3][int(ret[j])] for j in range(i*3,(i+1)*3)])))
                    except ValueError, KeyError:
                        cmd.fail("text='wrong statword'")
                return self.getBiastat(cmd)
        return False

    def getBiastat(self, cmd):
        list_param = [("period", 1), ("duty", 1024)]
        for param, coeff in list_param:
            if self.safeSend(cmd, self._s, "get_%s\r\n" % param):
                ok, ret = self.safeRecv(cmd, self._s)
                if ok:
                    try:
                        val = float(ret) / coeff
                        setattr(self, "bia%s" % param.capitalize(), val)
                    except ValueError:
                        cmd.fail("text='%s value is wrong'" % param)
                        return False
                else:
                    return False
        return True

    def switch(self, cmd, device, mode):
        if self.getStatus(cmd):
            ok, ret = bsh.transition[(self.shState, self.biaState), mode]
            if ok:
                if self.errorChecker(cmd, "%s_%s" % (device, mode)):
                    return True
            else:
                cmd.warn("text ='%s'" % ret)
                return True
        return False

    def errorChecker(self, cmd, command):
        if self.safeSend(cmd, self._s, "%s\r\n" % command):
            ok, ret = self.safeRecv(cmd, self._s)
            if ok:
                if ret == "n":
                    cmd.fail("text='Command : %s has failed'" % command)
                elif ret == "intlk":
                    cmd.fail("text='Interlock from HARDWARE'")
                elif ret == "":
                    return True
                else:
                    cmd.fail("text='unexpected return values : % s'" % ret[0])
        return False

    def safeSend(self, cmd, socket, message):

        try:
            socket.send(message)
            return True
        except Exception as inst:
            cmd.fail("text='error : %s '" % inst)
            return False

    def safeRecv(self, cmd, socket):
        t0 = dt.datetime.now()
        try:
            ret = [socket.recv(1024)]
        except Exception as inst:
            cmd.fail("text='error : %s '" % inst)
            return False, ''

        while "ok\r\n" not in ret[-1] and (dt.datetime.now() - t0).total_seconds() < bsh.timeout:
            try:
                ret.append(socket.recv(1024))
            except Exception as inst:
                cmd.fail("text='error : %s '" % inst)
                return False, ''

        if (dt.datetime.now() - t0).total_seconds() < bsh.timeout:
            return True, ''.join(ret).split("ok\r\n")[0]
        else:
            return False, 'n'
