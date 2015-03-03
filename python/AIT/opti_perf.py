#!/usr/bin/env python
# encoding: utf-8

import numpy as np
import matplotlib.pyplot as pl
from gaussfitter import *
#from matplotlib.widgets import RectangleSelector

#####################
#  MOUSE CLICK      #
#####################
# N.B not used

def line_select_callback(eclick, erelease):
    'eclick and erelease are the press and release events'
    cadre.append(eclick.xdata)
    cadre.append(eclick.ydata)
    cadre.append(erelease.xdata)
    cadre.append(erelease.ydata)

def toggle_selector(event):
    print (' Key pressed.')
    if event.key in ['enter', 'Q', 'q'] and toggle_selector.RS.active:
        print ('Selection done ')
        toggle_selector.RS.set_active(False)
        pl.close()

###########################
#  Image Processing part  #
###########################

def File2Array(filename):
    """Convert fit file to array like.
    """
    textFile = open(filename, 'r')
    rows = textFile.read().split('\r\n')
    head = rows[:19]
    rows = rows[19:]
    lines = []
    for index, row in enumerate(rows):
        if row != '':
            lines.append(map(float, row.split('\t')))
        else:
            if len(lines) != index:
                raise ValueError(
                        "Erreur syntax dans fichier ligne: %i" % index)
    return lines, head

def autoROI(Image, tolerance = 1.2):
    """Find ROI(s) from binary image. Poor threshold segmentation

    Input Parameters:

        Image: binary Image
        tolerance: ratio de la ROI pour etre sur de prendre les spots

    Outputs:

        ROI(s) list [[xmin, ymin, xmax, ymax],...]
    """
    from scipy.ndimage import label
    from skimage.measure import regionprops
    # It seems dont need to segment
    Labeled, Nfiber = label(Image>0)

    ROI = []
    for i in xrange(Nfiber):
        Obj_i = Labeled == i + 1
        width = max(np.sum(Obj_i, axis = 0)) * tolerance
        height = max(np.sum(Obj_i, axis = 1)) * tolerance
        props = regionprops(Obj_i)
        center = props[0].centroid
        ROI.append([
            np.ceil(center[0] - width / 2.),
            np.ceil(center[1] - height / 2.),
            np.ceil(center[0] + width / 2.),
            np.ceil(center[1] + height /2.)
            ])
        if width > center[0] * 2. or height > center[1] * 2.:
            raise Exception("\
ROI on border of image: Either \
change tolerance (tol = %s) or change Image\n\
ROI = %s" % (tolerance, ROI))
    return ROI


def findCriteria(Image, cadre=None, N=5, with2Dfit = True):
    """Find FWHM, EE, LSF,... of one object

    Input Parameters:

        Image: ROI image composed of one object
        cadre: location of ROI image [xmin,xmax,ymin,ymax]
        N: with of ensquared energy
        with2Dfit: make a fitting or not

    Outputs:
        dict look key 'help' for more details
    """


    help = {
            'FWHM': "[fwhm_x, fwhm_y] Full Width at Half Maximum along x and y",
            'EE': "Ensquared Energy",
            'LSF': "Line Spread Function",
            }
    out = {}

    out['help'] = help

    if cadre is None:
        cadre = [ 0, Image.shape[0], 0, Image.shape[1] ]

    ## Gaussian Fit
    # Recherche des param. initiaux pour l'optimisation de LMEM algo.
    # param.: amplitude, sigma_x, sigma_y, ...
    coeff = gaussfit(Image, vheight=0)
    out['coeff'] = coeff
    coeff = coeff[1:] #remove first value: no offset

    # Algo. LMEM on 2D gaussian
    fittedGauss = twodgaussian(coeff[:-1], rotate=0, vheight=0, shape = Image.shape)

    # 2D gaussian array like
    out['fittedGauss'] = fittedGauss

    # centroid
    out['centroid'] = cadre[0] + coeff[2], cadre[1] + coeff[1]
    centroid_rel = coeff[1:3]

    # centroid relative
    out['centroid_rel'] = centroid_rel

    # FWHM
    out['FWHM']  = (2. * np.sqrt(2. * np.log(2.)) * coeff[3:5])

    # FWHM of LSF
    if with2Dfit != 0:
        lsf_x = np.sum(fittedGauss, axis = 1)
        lsf_y = np.sum(fittedGauss, axis = 0)
    else:
        lsf_x = np.sum(Image, axis = 1)
        lsf_y = np.sum(Image, axis = 0)
    out['lsf_x'] = lsf_x
    out['lsf_y'] = lsf_y

    # LMEM Gaussian on 1D curve
    def gauss1D(x, a, mu, fwhm):
        return a * np.exp(- 4 * np.log(2) * (x - mu) ** 2 / fwhm ** 2)

    # initial parametersi pX = [amplitude, mu, fwhm] estimated
    pX = [1, 1, 1]
    pY = [1, 1, 1]
    pX[0] = max(lsf_x)
    pY[0] = max(lsf_y)
    pX[1] = (cadre[0] + cadre[2]) * .5
    pY[1] = (cadre[1] + cadre[3]) * .5
    pX[2] = sum(lsf_x > pX[0] * 0.5)
    pY[2] = sum(lsf_y > pY[0] * 0.5)

    try:
        # LMEM 1D with scipy
        from scipy.optimize import curve_fit
        poptX, _ = curve_fit(gauss1D, np.arange(cadre[0], cadre[2]), lsf_x, p0=pX)
        poptY, _ = curve_fit(gauss1D, np.arange(cadre[1], cadre[3]), lsf_y, p0=pY)
    except Exception, e:
        print e
        import pdb
        pdb.set_trace()

    out['lsf_x_fitted'] = lambda x: gauss1D(x, poptX[0], poptX[1], poptX[2])
    out['lsf_y_fitted'] = lambda x: gauss1D(x, poptY[0], poptY[1], poptY[2])

    out['c_lsf_x'] = poptX[1]
    out['FWHM_lsf_x'] = poptX[2]
    out['c_lsf_y'] = poptY[1]
    out['FWHM_lsf_y'] = poptY[2]
    out['x_gauss_param'] = poptX
    out['y_gauss_param'] = poptY



    # Ensquared Energy
    minx = centroid_rel[0] - N / 2.
    miny = centroid_rel[1] - N / 2.
    minx = 0 if minx < 0 else minx
    miny = 0 if miny < 0 else miny

    out['EE'] = np.sum(
            Image[
                np.ceil(minx):
                np.ceil(centroid_rel[1] + N / 2.),
                np.ceil(miny):
                np.ceil(centroid_rel[0] + N / 2.)
                ])
    if out['EE'] == 0:
        print [
                minx,
                np.ceil(centroid_rel[1] + N / 2.),
                miny,
                np.ceil(centroid_rel[0] + N / 2.)
                ]
    return out



###############
#  Affichage  #
###############
def display(Image, criteria, cadre, N):
    from matplotlib.patches import Rectangle
    from matplotlib import gridspec

    # Load all parameter
    centroid = criteria['centroid']
    lsf_x = criteria['lsf_x']
    lsf_y = criteria['lsf_y']
    c_lsf_x = criteria['c_lsf_x']
    c_lsf_y = criteria['c_lsf_y']
    FWHM_lsf_x = criteria['FWHM_lsf_x']
    FWHM_lsf_y = criteria['FWHM_lsf_y']
    FWHM_x, FWHM_y = criteria['FWHM']
    EE = criteria['EE']
    fittedGauss = criteria['fittedGauss']
    centroid_rel = criteria['centroid_rel']


    cadre = map(int, cadre)
    ## Orignial image
    fig = pl.figure(figsize = (20, 14))
    gs = gridspec.GridSpec(2, 2, width_ratios = [1,1])
    plt = fig.add_subplot(gs[1])
    plt.imshow(Image,
            extent=(cadre[0], cadre[2], cadre[1], cadre[3]),
            interpolation='none')
    # Draw arrow on center
    plt.annotate('(%.1f, %.1f)' % (centroid[0], centroid[1]),
            fontsize = 12, xy = centroid,
            xycoords = 'data', xytext = centroid_rel,
            textcoords = 'offset points',
            color = 'white',
            arrowprops=dict(arrowstyle='->',
                connectionstyle='arc3',
                color = 'white'))

    pl.title('Original')

    ## LSF around x
    plt = fig.add_subplot(gs[0])
    plt.plot(range(cadre[0], cadre[2]), lsf_x, 'b+')
    x = np.arange(cadre[0], cadre[2], 0.1)
    poptx = criteria["x_gauss_param"]
    plt.plot(x, criteria['lsf_x_fitted'](x), 'g',
            label = r'$f(x) = %.2f \cdot \exp{\left(-4 \cdot ln(2) \cdot \frac{(x-%.2f)^2}{%.2f^2}\right)}$' %
            (poptx[0], poptx[1], poptx[2]))
    # Show bar of FWHM on plot
    pl.axvspan(c_lsf_x - FWHM_lsf_x / 2.,
            c_lsf_x + FWHM_lsf_x / 2.,
            facecolor = 'g', alpha = 0.2,
            label = 'FWHM of LSF = %.1f' % FWHM_lsf_x)
    pl.axvspan(centroid[0] - FWHM_x / 2.,
            centroid[0] + FWHM_x / 2.,
            facecolor = 'r', alpha = 0.1,
            label = 'FWHM = %.1f' % FWHM_x)
    pl.legend(loc=0, fontsize ='small', framealpha=0.6)
    pl.title('LSF profil x')

    ## LSF around y
    plt = fig.add_subplot(gs[3])
    plt.plot(lsf_y, range(cadre[1],cadre[3]), 'b+')
    x = np.arange(cadre[1], cadre[3], 0.1)
    popty = criteria["y_gauss_param"]
    plt.plot(criteria['lsf_y_fitted'](x), x, 'g',
            label = r'$f(y) = %.2f \cdot \exp{\left(-4 \cdot ln(2) \cdot \frac{(y-%.2f)^2}{%.2f^2}\right)}$' %
            (popty[0], popty[1], popty[2]))
    # Show bar of FWHM on plot
    pl.axhspan(c_lsf_y - FWHM_lsf_y / 2.,
            c_lsf_y + FWHM_lsf_y /2.,
            facecolor = 'g', alpha = 0.2,
            label = 'FWHM of LSF = %.1f' % FWHM_lsf_y)
    pl.axhspan(centroid[1] - FWHM_y / 2.,
            centroid[1] + FWHM_y / 2.,
            facecolor = 'r', alpha = 0.1,
            label = 'FWHM = %.1f' % FWHM_y)
    pl.legend()
    ax = pl.gca()
    ax.set_ylim(ax.get_ylim()[::-1])
    pl.title('LSF profil y')

    ## Fitted image
    plt = fig.add_subplot(gs[2])
    # Create a rectangle for Ensquared Energy
    rect = Rectangle((centroid[0] - N / 2.,
            centroid[1] - N / 2.),
            N, N, alpha = 0.5, color = 'k',
            label = "EE = %.2f" % EE)
    plt.imshow(fittedGauss,# aspect = 'auto',
            extent=(cadre[0], cadre[2], cadre[1], cadre[3]),
            interpolation='none')
    plt.add_patch(rect)
    plt.annotate('(%.1f, %.1f)' % (centroid[0], centroid[1]),
            fontsize = 12, xy = centroid,
            xycoords = 'data', xytext = centroid_rel,
            textcoords = 'offset points',
            color = 'white',
            arrowprops=dict(arrowstyle='->',
                connectionstyle='arc3',
                color = 'white'))
    ax = pl.gca()
    ax.set_ylim(ax.get_ylim()[::-1])
    pl.title('Fit gaussian ')
    pl.legend(loc=0, fontsize ='small', framealpha=0.6)



#####################
#  File management  #
#####################
def sortStringListByNumber(StringList):
    """Example:
        ["blaval01", "02dadaz", "12.txt"] => ["blaval01", "12.txt", ..]
    """
    ## Sort filenames by numbers
    def tryint(s):
        # return int if it can
        try:
            return int(s)
        except:
            return s

    def alphanum_key(s):
        # split in string and int if it can
        import re
        return [tryint(c) for c in re.split('([0-9]+)', s)]

    return sorted(StringList, key=alphanum_key)


#import wx, os, sys
import os, sys
import tkMessageBox, tkFileDialog, Tkinter
import csv

if __name__ == '__main__':
    ## UI open a directory
    root = Tkinter.Tk()
    directory = tkFileDialog.askdirectory(initialdir = os.getcwd(),
                                          title = "Choose a Directory",
                                          parent = root)
    root.iconify()

    if 'directory' not in locals():
        sys.exit()
    filenames = sortStringListByNumber(os.listdir(directory))

    ## Handle directory
    # rm and create a directory
    mydirectoryname = 'SoftAIT'
    try:
        os.mkdir('%s/%s' % (directory, mydirectoryname))
    except OSError, e:
        if e.errno == 17:
            print e.strerror
            y = raw_input("Do you want to overwrite old one? (y/N) [default: y]")
            if y in ['y', '']:
                import shutil
                shutil.rmtree(directory + '/' + mydirectoryname)
                os.mkdir('%s/%s' % (directory, mydirectoryname))
            else:
                print("Bye Bye o/ !!")
                root.destroy()
                sys.exit(0)
        else:
            raise e

    ## setup toolbar
    toolbar_width = len(filenames) + 4
    sys.stdout.write("[%s]" % (" " * toolbar_width))
    sys.stdout.flush()
    sys.stdout.write('\b' * (toolbar_width + 1))
    sys.stderr = open(os.devnull, 'w')

    ## Create csv file to save important data
    mycsvFile = open("%s/%s/%s_data.csv" %
            (directory, mydirectoryname,mydirectoryname),
            "wb")
    mycsv = csv.writer(mycsvFile)

    EE = {'0': [], '1' : [], '2' : [], '3' : []}
    FWHM_y = {'0': [], '1' : [], '2' : [], '3' : []}
    FWHM_x = {'0': [], '1' : [], '2' : [], '3' : []}

    cmpt = 0
    ## Compute sequence over all fiber
    for filename in filenames:
        cmpt += 1
        if filename == mydirectoryname:
            continue
        Image, _ = File2Array(directory + '/' + filename)
        Image = np.array(Image)

        filename = filename.split('.')[0]

        # Recherche auto des fibres
        l_cadre = autoROI(Image)

        # labelisation ordonnee suivant la position le long de x
        from operator import itemgetter
        l_cadre.sort(key = itemgetter(1))  # trie suivant x croissant

        # Pour chaque fibre de l'image
        for i, cadre in enumerate(l_cadre):
            # Image d'une fibre
            ImageROI = Image[cadre[0]: cadre[2], cadre[1]: cadre[3]]

            criteria = findCriteria(ImageROI, cadre)
            display(ImageROI, criteria, cadre, N=5)
            pl.savefig('%s/%s/%s_fiber_%s.png' %
                    (directory, mydirectoryname, filename, i),
                    format = 'png')
            pl.close(1)

            # energy encadree de la fibre i
            EE['%s' % i].append(criteria['EE'])

            # FWHM de la fibre i
            FWHM_x['%s' % i].append(criteria['FWHM'][0])
            FWHM_y['%s' % i].append(criteria['FWHM'][1])

            mycsv.writerow(["fiber=%s" % i, "filename=%s" % filename])
            for it in criteria.items():
                if it[0] != 'fittedGauss':
                    mycsv.writerow(it)

        # update the bar
        disp = "=<%s%%>" % int(100 * cmpt / len(filenames))
        sys.stdout.write(disp)
        sys.stdout.write('\b' * (len(disp) - 1))
        sys.stdout.flush()
    mycsvFile.close()
    sys.stdout.write("=\n")

    #Affichage des critères
    pl.figure(1)
    pl.subplot(221)
    for i in range(len(l_cadre)):
        pl.plot(FWHM_x['%s' % i],
                label="fiber %s" %i)
    pl.title("FWHM along x")

    pl.subplot(222)
    for i in range(len(l_cadre)):
        pl.plot(np.array(FWHM_x['%s' % i]) **2 + np.array(FWHM_y['%s' % i]) **2 ,
                label="fiber %s" %i)
    pl.title("FWHM squared")

    pl.subplot(223)
    for i in range(len(l_cadre)):
        pl.plot(EE['%s' % i],
                label="fiber %s" %i)
    pl.title("Ensquared Energy")
    pl.savefig('%s/%s/criterion_curve.png' %
                    (directory, mydirectoryname),
                    format = 'png')

    tkMessageBox.showinfo(title="Opération réussie",
                          message="les données ont été enregistrés à \
%s/%s" % (directory, mydirectoryname))

    root.destroy()
