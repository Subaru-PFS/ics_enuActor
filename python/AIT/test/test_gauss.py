
import numpy as np
from opti_perf import *


def generateGauss(size, stretchX=1, fwhm=2, center=None):
    x = np.arange(0, size, 1, float)
    y = x[:, np.newaxis]

    if center is None:
        x0 = y0 = size // 2
    else:
        x0 = center[0]
        y0 = center[1]

    return np.exp(-4 * np.log(2) * (stretchX * (x - x0) ** 2 + (y - y0) ** 2) / fwhm ** 2)


def test(size, fwhm = 2, stretch = 1, tolerance = 0.9, noise = 0.):
    I = generateGauss(size, stretchX = stretch, fwhm=fwhm, center=[np.ceil(size/2.)] * 2)
    I = I + I * np.random.uniform(high=noise, size = I.shape)
    cadre = autoROI(I, tolerance = tolerance)[0]
    I = I[cadre[0]: cadre[2], cadre[1]: cadre[3]]
    criteria = findCriteria(I, cadre, N=5)
    display(I, criteria, cadre, N=5)
    pl.show()
    return criteria


test(20, stretch = 0.5)
test(50, stretch = 0.5)
test(20, fwhm = 5, stretch = 0.5)
test(50, fwhm = 5, stretch = 0.5)
test(20, fwhm = 10, stretch = 0.5)
test(50, fwhm = 10, stretch = 0.5)
criteria = test(20, fwhm = 10, stretch = 3, noise =0.1)
test(50, fwhm = 10, stretch = 3)

