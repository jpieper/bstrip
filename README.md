# bstrip - High speed automated wire cutter and stripper #

The bstrip is a brushless motor based automated wire processing tool.
It can cut wires to any length, fully strip one side, and pre-cut the
insulation on the back side.  It is based on the mjbots moteus
controller, raspberry pi and mjbots pi3hat, 5208 brushless motors, and
a converted hand v-cut tool.

License: Apache 2.0

This repository contains the bill of materials, models to be printed
on a 3D printer, and python source code for driving the machine.

* [Bill of Materials](BOM.md)
* [Fusion 360 Source CAD](https://a360.co/3fsq1WW)
* [3D printer models](hw/)
* [Source Code](src/cutwire.py)

Overview video: https://www.youtube.com/watch?v=_LFLcuUfIaE

# Build instructions #

TODO

## Raspberry Pi ##

Install a 32 bit Raspberry Pi OS.  A GUI is not required.

Then install the moteus python packages:

```
sudo pip3 install moteus moteus-pi3hat
```

## Setting Motor IDs ##

First, *never* hot plug the power cables, although it is OK to do so
with CAN.

Second, to set the ID for the cutter motor, connect the cutter motor
alone to JC1 on the pi3hat.  Then run:

```
sudo python3 -m moteus.moteus_tool -t 1 --console
conf set id.id 2
<CTRL-D>
sudo python3 -m moteus.moteus_tool -t 2 --console
conf write
<CTRL-D>
```

You should see an `OK` from the `conf write`.  Now both servos can be
daisy chained together on JC1.

## Motor calibration ##

The two motors should then be calibrated, with no load attached:

```
sudo python3 -m moteus.moteus_tool -t 1 --calibrate --cal-invert
sudo python3 -m moteus.moteus_tool -t 2 --calibrate --cal-bw-hz 400
```


## Motor Configuration ##

After setting IDs and calibrating motors, the following configuration files need to be installed on each controller.

```
sudo python3 -m moteus.moteus_tool -t 1 --write-config servo_1.cfg
sudo python3 -m moteus.moteus_tool -t 1 --write-config servo_2.cfg
```
