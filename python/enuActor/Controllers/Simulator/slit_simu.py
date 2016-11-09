__author__ = 'alefur'
import time
from random import randint


class SlitSimulator(object):
    def __init__(self, home):
        super(SlitSimulator, self).__init__()
        self.home = home
        self.pos = [0 for i in range(6)]
        self.tool = [0 for i in range(6)]

    def GroupPositionCurrentGet(self, socketId, GroupName, nbElement):
        time.sleep(0.5)
        res = [0]
        res.extend(self.pos)
        return res

    def GroupKill(self, socketId, GroupName):
        time.sleep(0.5)
        return [0]

    def GroupInitialize(self, socketId, GroupName):
        time.sleep(0.5)
        return [0]

    def GroupHomeSearch(self, socketId, GroupName):
        time.sleep(2.)
        return [0]

    def HexapodCoordinateSystemGet(self, socketId, GroupName, CoordinateSystem):
        time.sleep(0.5)
        res = [0]
        if CoordinateSystem == "Work":
            res.extend(self.home)
        elif CoordinateSystem == "Tool":
            res.extend(self.tool)
        return res

    def HexapodCoordinateSystemSet(self, socketId, GroupName, CoordinateSystem, X, Y, Z, U, V, W):
        if CoordinateSystem == "Work":
            self.home = [X, Y, Z, U, V, W]
        elif CoordinateSystem == "Tool":
            self.tool = [X, Y, Z, U, V, W]

        return [0]

    def HexapodMoveAbsolute(self, socketId, GroupName, CoordinateSystem, X, Y, Z, U, V, W):
        self.pos = [X, Y, Z, U, V, W]
        time.sleep(1)
        return [0]

    def HexapodMoveIncremental(self, socketId, GroupName, CoordinateSystem, dX, dY, dZ, dU, dV, dW):
        self.pos = [sum(i) for i in zip(self.pos, [dX, dY, dZ, dU, dV, dW])]
        time.sleep(1)
        return [0]

    def ErrorStringGet(self, socketId, err):
        return [[0, "Search your feelings"], [-42, "mah ! Mistakes happen"]][randint(0, 1)]

    def GroupStatusGet(self, socketId, GroupName):
        return [0, 12]

    def GroupStatusStringGet(self, socketId, GroupStatusCode):
        enum = {12: "Ready state from motion", 11: "Ready state from homing"}
        return [0, enum[GroupStatusCode]]
