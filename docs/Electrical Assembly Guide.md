# MXET 345 solar tracker: electrical assembly guide

**Updated:** Nov 19, 2026
**Basis:** `Hardware & BOM.md`, `Code/config/default.toml`, `Code/config/robot.toml`, the lab scripts in `Code/lab/`, `Code/README.md` and `Design Overview.md`. No one has run this wiring on the robot. The real backend (`hardware/real.py`) is also untested on the robot.
**Confidence tags:** [Certain] / [Likely] / [Guessing].
**Scope:** The panel sensor, the two servos, and their connection to the robot's I2C bus and servo HAT. The wheel drivers are not in scope.

## Read this first

1. WARNING. Do not connect a servo until you measure the HAT V+ voltage (step 5). The SG90 is rated for about 4.8 to 6 V [Likely]. The wheel motors are REV HD Hex motors rated for 12 V [Certain]. The robot's battery voltage and the source of the HAT V+ rail are not recorded [Guessing]. A wrong V+ rail can destroy both servos.
2. Four channel numbers: the mux channel for the INA219 and the BNO055, and the HAT channel for pan and tilt. `Code/config/robot.toml` is prefilled from the lab scripts: BNO055 on mux channel 6 (`Code/lab/test_sensor.py`), pan servo 13 and tilt servo 12 (`Code/lab/test_motor.py`). The INA219 channel is not recorded. Find it with `python lab/sensor_scan.py` (step 6). The software refuses to start while `mux_channel_panel` is unset [Certain].
3. Do steps 1 to 9 before the horn steps of the mechanical assembly guide. Servos must be centred at 1500 µs before you install the horns [Certain, from `Design Overview.md`].
4. Do not change the PCA9685 address, the mux address or the PWM frequency. The lab code (`Code/lab/motor_servo_pwm.py`) sets PCA9685 0x40 to 100 Hz, and the tracker uses that code. The robot's wheels depend on them [Certain].

## Parts and tools

| Qty | Item | Note |
|--|------------|------------|
| 1 | Voltaic P124 panel, 6 V, 66 x 113 mm | Voc 7.28 V, Isc about 240 mA [Likely]. Two solder pads, no leads |
| 1 | Adafruit INA219 breakout (#904) | Has a STEMMA QT port, a 6-pin header and a 3.5 mm terminal plug [Certain] |
| 1 | STEMMA QT / Qwiic cable, 100 to 200 mm | The lab may have spares |
| 2 | SG90 micro servo | Wire colours: brown = ground, red = V+, orange = signal [Certain] |
| 1 m | 22 AWG hook-up wire, red and black | Panel leads and the Vin- link |
| - | Heat-shrink, 2.5 mm zip ties, kapton tape or hot glue | Insulation and strain relief |
| - | Soldering iron, multimeter, small flat screwdriver, flush cutters | |

Buy only if a check fails (`Hardware & BOM.md` section 5). Examples are a 5 to 6 V, 3 A buck converter with an inline fuse, and a 470 to 1000 µF capacitor.

## Wiring summary

| Signal | From | To |
|---|---|---|
| Panel positive | Panel + pad | INA219 Vin+ terminal |
| Panel negative | Panel - pad | INA219 GND pad |
| Shunt return | INA219 Vin- terminal | INA219 GND pad |
| INA219 I2C and power | INA219 STEMMA QT port | Free channel N on the Qwiic mux |
| Pan servo | Brown / red / orange | HAT channel P, pins G / V+ / S |
| Tilt servo | Brown / red / orange | HAT channel T, pins G / V+ / S |

The panel current flows through the 0.1 ohm shunt and returns to ground. The INA219 reads the panel near short circuit [Certain]. Do not add a load resistor.

| Device | I2C address | Location |
|---|---|---|
| PCA9685 servo HAT | 0x40 | Upstream, on the Pi |
| TCA9548A Qwiic mux | 0x70 | Upstream |
| INA219 (panel) | 0x41 (A0 bridged) | Mux channel N |
| BNO055 IMU | 0x28 | Mux channel (already on the robot) |

## Procedure

### Step 1. Record the robot's channels

1. Remove power from the robot. Put the robot on a stand with the wheels off the ground.
2. Examine the Qwiic mux. Record the channel that the BNO055 uses. `Code/lab/test_sensor.py` uses channel 6.
3. Choose a free mux channel for the INA219. Record it as N.
4. Examine the servo HAT. Find the headers that the wheel drivers use. `Code/lab/test_motor.py` drives the wheels as FWD/RV pairs on channels 0/1 and 2/3.
5. Choose two unused servo headers. Record them as P (pan) and T (tilt). `Code/lab/test_motor.py` uses servo channels 13 and 12, and `robot.toml` defaults to pan 13, tilt 12.
6. Never write to a wheel-driver channel [Certain].

### Step 2. Set the INA219 to address 0x41

1. Bridge the A0 solder jumper on the INA219 with a small blob of solder.
2. Measure continuity across the two A0 pads. The meter must beep.
3. Reason: the PCA9685 already uses 0x40, and the INA219 default is also 0x40 [Certain].

### Step 3. Solder the panel leads

1. Cut one red and one black 22 AWG lead, 250 mm each. The length covers the path through the tilt pivot [Guessing].
2. Strip 3 mm. Tin the ends of the wire and the two panel pads.
3. Identify the panel polarity from the marks on the pads. If no marks exist, expose the panel to light and measure. The positive pad reads positive voltage.
4. Solder each lead with a short iron contact. The ETFE surface can melt if the iron stays too long [Likely].
5. Add a dab of hot glue or kapton tape over each joint. This is the strain relief at the panel edge.
6. Slide heat-shrink over each exposed joint.

### Step 4. Connect the panel to the INA219

1. Insert the red lead in the Vin+ position of the 3.5 mm terminal plug. Tighten the screw.
2. Insert a short black link wire in the Vin- position. Tighten the screw.
3. Solder the other end of the link wire to the GND pad. Check the silkscreen for the pad.
4. Solder the black panel lead to the same GND pad.
5. Push the terminal plug onto the INA219. Do not connect the Qwiic cable yet.

### Step 5. Measure the HAT V+ voltage

1. Keep the servos disconnected.
2. Apply power to the robot. Set the multimeter to DC volts.
3. Measure between V+ and G on a free servo header.
4. Compare the reading with the table.

| Reading | Action |
|---|---|
| 4.8 to 6.0 V | Continue to step 6 |
| Above 6.0 V | Stop. Do not connect the SG90 servos. Use a separate 5 to 6 V supply with a common ground |
| Below 4.5 V | Stop. Find the cause before you continue. A low rail resets the Pi under servo load [Likely] |

5. Remove power from the robot.

### Step 6. Connect the INA219 to the mux

1. Connect the STEMMA QT cable between the INA219 and mux channel N.
2. Apply power. Wait for the Pi to boot.
3. Run `i2cdetect -y 1`. Expect 0x40 and 0x70 only. The mux hides downstream devices until a channel is selected [Certain].
4. Select channel N. Run `i2cset -y 1 0x70 <mask>`. The mask is 1 shifted left N places (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80 for channels 0 to 7) [Certain].
5. Run `i2cdetect -y 1` again. Expect 0x41 in addition to 0x40 and 0x70.
6. Clear the mux. Run `i2cset -y 1 0x70 0x00`.
7. If 0x41 does not appear, check the A0 bridge, the cable and the channel number.
8. Shortcut for steps 3 to 6: from `Code/`, run `python lab/sensor_scan.py` (VS Code task "5 Scan mux channels (lab)"). It prints the addresses on each mux channel. The channel with 0x41 is N. The channel with 0x28 is the BNO055.

### Step 7. Connect the servos

1. Remove power from the robot.
2. Connect the pan servo to header P. Connect the tilt servo to header T. Use the silkscreen: brown to G, red to V+, orange to S. [Likely] Check the orientation twice. The HAT headers are not keyed.
3. Do not install the horns. The mechanical guide gives that step.

### Step 8. Configure the robot file

1. Edit `Code/config/robot.toml`. The tracker loads it automatically after `default.toml`. No `--config` option is necessary.
2. Set `mux_channel_panel = N`. Check `mux_channel_imu` (default 6), `servo_channel_pan = P` (default 13) and `servo_channel_tilt = T` (default 12).
3. Look up the magnetic declination for the test site and date at NOAA. Set `declination_deg`. Record the source in the file.
4. Do not change `drive.*` now. Only the turn needs it. `--skip-turn` works without it [Certain].

### Step 9. Run preflight and centre the servos

1. Log in to the Pi. Run `source ~/env/bin/activate`. Start `tmux`. Or use the VS Code tasks in `Code/` ("7 Preflight", "8 Park (centre servos)").
2. Run `python -m solar_tracker preflight`.
3. Fix each item that preflight flags.
4. Run `python -m solar_tracker park`. This drives both servos to 1500 µs [Likely, with no calibration file].
5. Install the horns as the mechanical guide states, with the servos in this centred state.

### Step 10. Check the panel reading

1. Put the panel under a lamp or in sun.
2. Compare the `preflight` Isc with a multimeter. Set the multimeter to DC mA. Insert it in series between the panel + lead and Vin+.
3. The two readings must agree within a few percent [Guessing]. The INA219 has 0.5 to 1 % error by chip version [Certain].
4. Check the sign. Reversed panel polarity gives negative current [Certain].
5. Check the bus voltage. With the panel shorted it must read near 0 V [Certain].
6. Keep Isc below 350 mA. The code warns above 380 mA [Certain]. Move the lamp back if it does.
7. Cover the panel fully. Run `static-log --minutes 1`. Take the mean current from `static.csv`. Put the value in `panel.zero_offset_mA`.
8. Remove the multimeter.

### Step 11. Check servo direction

1. Mount the servos and panel as the mechanical guide states.
2. Run `calibrate-servo --servo pan --check-sign`. Positive pan must turn the panel clockwise, seen from above.
3. Run `calibrate-servo --servo tilt --check-sign`. Positive tilt must lift the panel normal.
4. If a direction is wrong, set `servo.pan_sign = -1` or `servo.tilt_sign = -1`. Do not swap the wires.
5. Run the full servo calibration (`Code/README.md`, step 10).

### Step 12. Route and secure the cables

1. Leave a slack loop of at least 60 mm in the tilt servo wire. The turntable pans plus or minus 90° (assembly guide step 8).
2. Leave a slack loop in the panel leads across the tilt pivot. The panel rotates relative to the upright.
3. Fasten the wires with 2.5 mm zip ties at the base plate, at the upright and at the panel holder edge.
4. Keep the Qwiic cable and the panel leads clear of the lazy susan and the wheels.
5. Pan the turntable by hand through its full range. Tilt the panel through its full range. No wire may pull tight or catch.

## Final checks before the first lamp run

- `i2cdetect` shows 0x40 and 0x70 upstream, and 0x41 and 0x28 on their channels.
- HAT V+ was measured and is 4.8 to 6.0 V.
- Preflight passes with no warning that you cannot explain.
- INA219 and multimeter agree. Sign is positive.
- Both servos centre, and both directions are correct.
- No wire is under tension at either axis limit (plus or minus 85°).

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Isc reads 0.0 mA under light | Vin- link missing, or an open panel lead | Check the black link wire and the terminal screws |
| Isc is negative | Panel polarity reversed | Swap the panel leads at the terminal plug |
| Bus voltage reads several volts | Vin- not tied to GND, so the loop is open | Solder the Vin- link to the GND pad |
| 0x41 missing | A0 not bridged, wrong channel, or loose Qwiic cable | Repeat step 2 and step 6 |
| Servos twitch when the INA219 is read | The INA219 is still at 0x40 | Bridge A0 (step 2) |
| Pi resets when a servo moves | The servo rail shares the Pi 5 V converter [Guessing] | Add a separate 5 to 6 V, 3 A supply with a fuse, a common ground and a 470 to 1000 µF capacitor. Do not hide it with software retries |
| `OSError` from the BNO055 | I2C clock stretching [Likely] | The code retries 3 times. Slow the bus only if errors persist |
| Servo hums at a limit | Horn indexing error, up to about 8° [Likely] | Trim the zero in software. Check the limit is plus or minus 85° |

## Open items

- The HAT V+ source and voltage. Measure in step 5.
- The INA219 mux channel. Find it in step 6. Confirm the BNO055 channel (6) and the servo channels (13, 12) from the lab scripts.
- Whether the Pi needs the INA219 Python package. It is probably missing and needs internet once [Guessing].
- Which wheel pair is left. `robot.toml` uses `left_motor_channels = [0, 1]` and `right_motor_channels = [2, 3]` from `Code/lab/test_motor.py`. Verify at the bench turn. Only needed for the coarse turn.
