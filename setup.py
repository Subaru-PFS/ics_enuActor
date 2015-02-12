import distutils
from distutils.core import setup, Extension

import sdss3tools
import os

sdss3tools.setup(
    description = "Toy SDSS-3 actor.",
    version = '0.1',
    name = "ics_enuActor",
    package_data = {'enuActor' : ['Devices/cfg/*.cfg']},
    install_requires=['NumPy', 'PySerial']
)

