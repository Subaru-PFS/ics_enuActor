"""
Overview
========

**ENtrance Unit actor package** (*enuActor*)  is composed of 2 directories and 1 main:
 * ``Commands``: Essentialy listener modules and parsers functions.
 * ``Devices``: Package related to device control.
 * ``main.py``: Where the main program is launched at start (defining the session). 
   Here each device class are instantiate.

Each command is received from a ``Commands`` module like ``Commands/XXCmd.py``
and then it is parsed to execute functions from ``Devices/XX.py`` module.

.. topic:: Example:

    if ``enu bia on`` is executed then ``Command/BiaCmd.py`` will parse this command
    and launch ``bia('on')`` from ``Devices/bia.py``.

Class diagram
-------------

.. image:: ../../diagram_class.png
   :alt: diagram class here
   :align: center


Convention naming
-----------------

The aim of this interface is to follow this naming convention at large:

``enu <device> <command> [arguments [= value]]``

Also others convention are defined like those for motorized devices:
 * ``enu <motorized-device> SetHome = [value|CURRENT]``: Set Home position to value or current position
 * ``enu <motorized-device> GetGome``: Get Home position
 * ``enu <motorized-device> GoHome`` : Go to Home

Here are devices classified :

=====    ========     ===========    =======     ====     =====
 NON MOTORIZED                 MOTORIZED
-----------------     -----------------------------------------
BIA      IISOURCE     Environment    Shutter     REXM     FPS
=====    ========     ===========    =======     ====     =====
todo       todo          todo          todo      todo     todo
=====    ========     ===========    =======     ====     =====


.. note:: Shutter is a motorized device but the SW device won't provide motorized features.

"""
