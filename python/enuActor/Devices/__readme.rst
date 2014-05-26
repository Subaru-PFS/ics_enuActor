"""
 :RivCreateContent
* Contents:

  + 1 `Convention naming`_
  + 2 `The State Machine`_
  + 3 `The Devices`_

    + 3.1 Device_
    + 3.2 Error_
    + 3.3 Shutter_
    + 3.4 BIA_
    + 3.5 REXM_
    + 3.6 IISOURCE_
    + 3.7 ENU_
    + 3.8 FPSA_

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

The State Machine
-----------------

.. image:: ../../state_diagram.png
   :alt: FSM should be here
   :align: center

The Devices
-----------

.. inheritance-diagram:: enuActor.Devices.Device enuActor.Devices.shutter enuActor.Devices.rexm enuActor.Devices.Error
    :parts: 1

Device
^^^^^^
.. inheritance-diagram:: enuActor.Devices.Device
    :parts: 1

behaves like an interface for each device such as:

Composed of different common parts for each device:
    * FSM :
        * Here the common state table is defined
        * Start the FSM
        * Diplay rule when state change
        * Each device should implement an ``initialise`` method which correspod to the INITIALISATION state of the FSM.
    * Communication handling :
        * Load communication & parameter config file
        * Send message following protocol

Error
^^^^^

.. inheritance-diagram:: enuActor.Devices.Error

Description:
 * :class:`~.Error.CommErr`: error related to communication between PC and Device
 * :class:`~.Error.DeviceErr`: error returned by controller (device) implying a **FAIL** state in the FSM.
 * :class:`~.Error.CfgFileErr`: error from parsing configuration file


Shutter
^^^^^^^

.. inheritance-diagram:: enuActor.Devices.shutter
    :parts: 1

Shutter is open or close ...

.. todo:: add more details


BIA
^^^


.. todo:: add more details

REXM
^^^^

.. inheritance-diagram:: enuActor.Devices.rexm
    :parts: 1

.. todo:: add more details

IISOURCE
^^^^^^^^

.. todo:: add more details

ENU
^^^

.. todo:: add more details

FPSA
^^^^

.. todo:: add more details

"""
