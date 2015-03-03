#!/usr/bin/env python
# encoding: utf-8


mydir = 'ZmxImgSimu/Field1/'
filename = "1.TXT"

from opti_perf import *

I, _ = File2Array(mydir + filename)
Image = np.array(I)

cadres = autoROI(Image)
cadre = cadres[0]

ImageROI = Image[cadre[0]: cadre[2], cadre[1]: cadre[3]]
crit = findCriteria(ImageROI, cadre, N=5)
crit_origin = findCriteria(ImageROI, cadre, N=5, with2Dfit=0)

lsf = crit['lsf_x']
fitted = crit['lsf_x_fitted']

lsfOrigin = crit_origin['lsf_x']
fittedOrigin = crit_origin['lsf_x_fitted']
x = range(int(cadre[0]), int(cadre[2]))
xx = np.arange(cadre[0], cadre[2], 0.1)

pl.figure(1)
pl.subplot(211)
pl.plot(x, lsf, 'bD', label= "LSF de la Gaussienne2D")
pl.plot(xx, fitted(xx), 'b', label= "Fit la lsf bleu")

pl.plot(x, lsfOrigin, 'rD', label= "LSF de l'image")
pl.plot(xx, fittedOrigin(xx), 'r', label= "Fit la lsf rouge")
pl.title("LSF around x")
pl.legend(fontsize='small')

pl.subplot(212)
mid = np.ceil(ImageROI.shape[0] / 2.)
profil = ImageROI[:, mid]
pl.plot(x, profil, "rD", label= "Profil de l'image")

fittedGauss2D = crit['fittedGauss']
profilFitted =fittedGauss2D[:, mid]
pl.plot(x, profilFitted, "b-", label="Profil de la Gaussienne 2D")
pl.title("Profil x (vue en coupe au milieu)")

pl.savefig('testLSF.png', format='png')
