"""
#: :RivCreateContent

* Contents:

  + 1 `The Devices`_

    + 1.1 Device_
    + 1.2 Error_
    + 1.3 Shutter_
    + 1.4 BIA_
    + 1.5 REXM_
    + 1.6 IISOURCE_
    + 1.7 ENU_
    + 1.8 FPSA_

The Devices
-----------

Devices package is composed of 1 module/class ``Device`` and 1 module/class per device (Shutter, Bia, Slit, ...).
It also contain an error class.

Device
^^^^^^

.. inheritance-diagram:: enuActor.Devices.Device
    :parts: 1

**Device** class has been created to deal with general behaviour of a device (close to an abstract class).
So each device class (:class:`~.bia.Bia`, :class:`~.shutter.Shutter`, ...) inherit them.
Furthermore, as you can see above :class:`~.Device.Device` inherit from QThread and so possess all its properties
such as a state machine attribute:

.. topic:: State Machine

   .. image:: ../../state_diagram.png
      :alt: FSM should be here
      :align: center

So **Device** class will handle main functions:

- Communication:

    + load communication and parameter config files
    + start a communication (create a socket, start a serial communication, ...)
    + check status (periodically check by sending data)
    + send message following protocol

- State machine:

    + create the common rule of the state machine
    + display state on change
    + callback on specific state

.. todo:: Talk about :class:`~.Device.SimulationDevice` and :class:`~.Device.OperationDevice`

Two different config files are defines in **cfg** directory.

+-----------------------------------------------------------------------+--------------------------------------------------------------------+
| `devices_communication.cfg`                                           | `devices_parameters.cfg`                                           |
+-----------------------------------------------------------------------+--------------------------------------------------------------------+
| .. literalinclude:: ../enuActor/Devices/cfg/devices_communication.cfg | .. literalinclude:: ../enuActor/Devices/cfg/devices_parameters.cfg |
|     :language: sh                                                     |     :language: sh                                                  |
|                                                                       |                                                                    |
+-----------------------------------------------------------------------+--------------------------------------------------------------------+


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

Shutter device has  links ethernet and serial:
- ethernet : connection is made throw arduino (interlock).
- serial: connection is directly made to the shutter (more commands).


.. todo:: ATM the shutter device can't handle 2 connection at a time


BIA
^^^

BIA device has 3 positions on, off and strobe. Position on and strobe are defined respectively by
the parameters (dimmer_duty, dimmer_period) and (strobe_duty, strobe_period).

REXM
^^^^

ReXM is defined by 3 positions medium, low, and parking.

IISOURCE
^^^^^^^^

.. todo:: add more details

ENU
^^^

ENU abstract device permit to see all each devices in one entity. The state of ENU is defined by the lowest state
of all device.
When ENU is initialising it launch a sequence of command to initialise all device safely.

FPSA
^^^^

Slit device is composed of:
  - slit position: position of slit related to upper carriage
  - focus axis: direction of focus
  - dither axis: direction of dither
  - magnification:
  - dither_value, focus_value: step of dither, focus
"""

