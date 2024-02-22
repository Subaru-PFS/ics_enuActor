import numpy as np
from scipy.optimize import minimize


def makeJerkArray(targetAcceleration, jerkTime, step):
    yMax = targetAcceleration * 2 / jerkTime
    a = yMax / (jerkTime / 2)

    x1 = np.arange(0, jerkTime / 2, step)
    y1 = x1 * a

    x2 = np.arange(jerkTime / 2, jerkTime + step, step)
    y2 = -x2 * a + yMax * 2

    x = np.append(x1, x2)
    y = np.append(y1, y2)

    return x, y


def makeFullJerkArray(targetAcceleration, timeAtConstantAcceleration, jerkTime, step):
    x1, y1 = makeJerkArray(targetAcceleration, jerkTime, step)

    if not timeAtConstantAcceleration:
        x2 = y2 = []
        offset = x1.max()
    else:
        x2 = np.arange(0, timeAtConstantAcceleration, step) + step + x1.max()
        y2 = np.zeros(len(x2))
        offset = x2.max()

    x3, y3 = makeJerkArray(targetAcceleration, jerkTime, step)
    y3 *= -1
    x3 += (step + offset)

    x = np.concatenate([x1, x2, x3])
    y = np.concatenate([y1, y2, y3])

    return x, y


def getMaxSpeed(targetAcceleration, timeAtConstantAcceleration, jerkTime, step):
    """Calculate maximum speed given targetAcceleration amd timeAtConstantAcceleration."""
    x, y = makeFullJerkArray(targetAcceleration, timeAtConstantAcceleration, jerkTime=jerkTime, step=step)
    acceleration = np.cumsum(step * y)
    speed = np.cumsum(step * acceleration)
    return np.max(speed)


def makeJerkProfile(targetSpeed, maxAcceleration=5, jerkTime=0.05):
    """Make jerkProfile, acceleration, speed, position profiles can be calculated from this."""
    step = jerkTime / 2000

    def findTargetAcceleration(targetAcceleration):
        return abs(getMaxSpeed(targetAcceleration, 0, jerkTime=jerkTime, step=step) - targetSpeed)

    def findTimeAtConstantAcceleration(timeAtConstantAcceleration):
        return abs(getMaxSpeed(maxAcceleration, timeAtConstantAcceleration, jerkTime=jerkTime, step=step) - targetSpeed)

    timeAtConstantAcceleration = 0
    targetAcceleration = maxAcceleration

    maxSpeed = getMaxSpeed(maxAcceleration, timeAtConstantAcceleration, jerkTime=jerkTime, step=step)

    if maxSpeed > targetSpeed:
        targetAcceleration = minimize(findTargetAcceleration, x0=(maxAcceleration * targetSpeed / maxSpeed)).x[0]
    else:
        timeAtConstantAcceleration = \
            minimize(findTimeAtConstantAcceleration, x0=((targetSpeed - maxSpeed) / maxAcceleration)).x[0]

    return makeFullJerkArray(targetAcceleration, timeAtConstantAcceleration, jerkTime=jerkTime, step=step)
