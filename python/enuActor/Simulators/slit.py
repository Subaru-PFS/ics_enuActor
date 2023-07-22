__author__ = 'alefur'

import socket
import time
from random import randint


class SlitSim(object):
    MAX_NB_SOCKETS = 100

    # Global variables
    __sockets = {}
    __usedSockets = {}
    __nbSockets = 0

    def __init__(self):
        """Fake slit hexapod tcp server."""
        object.__init__(self)
        SlitSim.__nbSockets = 0
        for socketId in range(self.MAX_NB_SOCKETS):
            SlitSim.__usedSockets[socketId] = 0

        self.home = [0 for i in range(6)]
        self.tool = [0 for i in range(6)]
        self.pos = [0 for i in range(6)]
        self.base = [0.00000, 0.00000, 25.00000, 0.00000, 0.00000, 0.00000]
        self.intStatus = 7
        self.emergencyStop = False

    def TCP_ConnectToServer(self, IP, port, timeOut):
        """Fake the connection to tcp server."""
        if type(IP) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

        socketId = 0
        if (SlitSim.__nbSockets < self.MAX_NB_SOCKETS):
            while (SlitSim.__usedSockets[socketId] == 1 and socketId < self.MAX_NB_SOCKETS):
                socketId += 1
            if (socketId == self.MAX_NB_SOCKETS):
                return -1
        else:
            return -1

        SlitSim.__usedSockets[socketId] = 1
        SlitSim.__nbSockets += 1
        try:
            pass
            # SlitSim.__sockets[socketId] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # SlitSim.__sockets[socketId].settimeout(timeOut)
            # SlitSim.__sockets[socketId].connect((IP, port))
            # SlitSim.__sockets[socketId].setblocking(1)
        except socket.error:
            return -1

        return socketId

    def TCP_CloseSocket(self, socketId):
        if (socketId >= 0 and socketId < self.MAX_NB_SOCKETS):
            try:
                # SlitSim.__sockets[socketId].close()
                SlitSim.__usedSockets[socketId] = 0
                SlitSim.__nbSockets -= 1
            except socket.error:
                pass

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
        self.intStatus = 11
        return [0, '']

    def GroupMoveAbort(self, socketId, GroupName):
        self.intStatus = 10
        self.emergencyStop = True
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
        self.emergencyStop = False
        self.pos = [X, Y, Z, U, V, W]
        t0 = time.time()

        while not self.emergencyStop and (time.time() - t0) < 2:
            time.sleep(0.1)
            if self.emergencyStop:
                return [-22, 'EMERGENCY STOP']
        return [0, '']

    def HexapodMoveIncremental(self, socketId, GroupName, CoordinateSystem, dX, dY, dZ, dU, dV, dW):
        self.emergencyStop = False
        self.pos = [sum(i) for i in zip(self.pos, [dX, dY, dZ, dU, dV, dW])]
        t0 = time.time()

        while not self.emergencyStop and (time.time() - t0) < 2:
            time.sleep(0.1)
            if self.emergencyStop:
                return [-22, 'EMERGENCY STOP']
        return [0, '']

    def ErrorStringGet(self, socketId, err):
        return [[0, "Search your feelings"], [-42, "mah ! Mistakes happen"]][randint(0, 1)]

    def GroupStatusGet(self, socketId, GroupName):
        return [0, self.intStatus]

    def GroupStatusStringGet(self, socketId, GroupStatusCode):
        enum = {0: 'Not initialized state',
                7: 'Not initialized state due to a GroupKill or KillAll command',
                10: 'Ready state due to an AbortMove command',
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
        if TCLFileName == 'KillWithRegistration.tcl':
            self.intStatus = 7
        elif TCLFileName == 'InitializeFromRegistration.tcl':
            self.intStatus = 12

        return [0, '']

    def HexapodMoveIncrementalControlWithTargetVelocity(self, socketId, GroupName, CoordinateSystem,
                                                        HexapodTrajectoryType, dX, dY, dZ, Velocity):

        waitTime = abs(dZ / Velocity)
        start = time.time()

        while time.time() - start < waitTime:
            time.sleep(0.1)

        return [0, '']
