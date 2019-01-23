__author__ = 'alefur'
import time
from random import randint


class SlitSim(object):
    def __init__(self):
        object.__init__(self)

        self.home = [0 for i in range(6)]
        self.tool = [0 for i in range(6)]
        self.pos = [0 for i in range(6)]
        self.base = [0.00000, 0.00000, 25.00000, 0.00000, 0.00000, 0.00000]
        self.intStatus = 12

    def TCP_ConnectToServer(self, host, port, timeout):
        if type(host) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

        return 1

    def GroupPositionCurrentGet(self, socketId, GroupName, nbElement):
        time.sleep(0.5)
        res = [0]
        res.extend(self.pos)
        return res

    def GroupKill(self, socketId, GroupName):
        time.sleep(0.5)
        self.intStatus = 7
        return [0, '']

    def GroupInitialize(self, socketId, GroupName):
        time.sleep(0.5)
        self.intStatus = 42
        return [0, '']

    def GroupHomeSearch(self, socketId, GroupName):
        time.sleep(8.)
        self.intStatus = 12
        return [0, '']

    def HexapodCoordinateSystemGet(self, socketId, GroupName, CoordinateSystem):
        time.sleep(0.5)
        res = [0]
        if CoordinateSystem == "Work":
            res.extend(self.home)
        elif CoordinateSystem == "Tool":
            res.extend(self.tool)
        elif CoordinateSystem == "Base":
            res.extend(self.base)
        return res

    def HexapodCoordinateSystemSet(self, socketId, GroupName, CoordinateSystem, X, Y, Z, U, V, W):
        if CoordinateSystem == "Work":
            self.home = [X, Y, Z, U, V, W]
        elif CoordinateSystem == "Tool":
            self.tool = [X, Y, Z, U, V, W]

        return [0, '']

    def HexapodMoveAbsolute(self, socketId, GroupName, CoordinateSystem, X, Y, Z, U, V, W):
        self.pos = [X, Y, Z, U, V, W]
        time.sleep(1)
        return [0, '']

    def HexapodMoveIncremental(self, socketId, GroupName, CoordinateSystem, dX, dY, dZ, dU, dV, dW):
        self.pos = [sum(i) for i in zip(self.pos, [dX, dY, dZ, dU, dV, dW])]
        time.sleep(1)
        return [0, '']

    def ErrorStringGet(self, socketId, err):
        return [[0, "Search your feelings"], [-42, "mah ! Mistakes happen"]][randint(0, 1)]

    def GroupStatusGet(self, socketId, GroupName):
        return [0, self.intStatus]

    def GroupStatusStringGet(self, socketId, GroupStatusCode):
        enum = {7: 'Not initialized state due to a GroupKill or KillAll command',
                11: "Ready state from homing", 12: "Ready state from motion",
                13: "Ready State due to a MotionEnable command",
                20: "Disabled state", 42: 'Not referenced state'
                }
        return [0, enum[GroupStatusCode]]

    def GroupMotionEnable(self, socketId, GroupName):
        self.intStatus = 13
        return [0, '']

    def GroupMotionDisable(self, socketId, GroupName):
        self.intStatus = 20
        return [0, '']

    def TCLScriptExecuteAndWait(self, socketId, TCLFileName, TaskName, ParametersList):
        if TCLFileName =='KillWithRegistration.tcl':
            self.intStatus = 7
        elif TCLFileName == 'InitializeFromRegistration.tcl':
            self.intStatus = 12

        return [0, '']
