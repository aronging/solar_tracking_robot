# MXET 345 Solar Tracker: Hardware, Wiring and Parts

**Updated:** Nov 17, 2026. Mechanical facts match `Hardware List & Assembly Guide.pdf` (re-exported Nov 17) and the STEP files in `CAD/`. Electronics facts match `Code/config/default.toml` and the code.
**Replaces:** `mxet345-solar-tracker-BOM.md` / `.xlsx` and the hardware parts of the old plan and breakdown. The originals are in git history (commit `30ef60b`).
**Confidence tags:** [Certain] / [Likely] / [Guessing]. Prices tagged Certain were checked on the vendor page on Oct 27, 2026.
**Not recorded anywhere:** whether each part has arrived, and the INA219 mux channel. Channels go in `Code/config/robot.toml` (auto-loaded). It is prefilled from the lab scripts in `Code/lab/`: BNO055 on mux channel 6 (`test_sensor.py`), pan servo 13 and tilt servo 12, wheels on FWD/RV pairs [0, 1] and [2, 3] (`test_motor.py`). Find the mux channels with `python lab/sensor_scan.py`.

## 1. Hardware at a glance

| Item | Role | Status |
|---|---|---|
| Raspberry Pi, PCA9685 PWM HAT (0x40), TCA9548A mux (0x70), robot battery and DC-DC converter | Computer, servo PWM, I2C fan-out, power | Lab robot, used as shipped |
| 2x REV HD Hex motors with encoders and drivers | Coarse turn to face south, once per session | Lab robot. Encoders are not used |
| BNO055 IMU (0x28) | Heading for the coarse turn and calibration status | Lab robot |
| APDS9960, VL53L4CD | Not used | Lab robot |
| 2x SG90 micro servo | Pan and tilt | In the assembly guide's parts list |
| Voltaic P124 panel | The tracked panel; its Isc is the measured signal | Buy list |
| Adafruit INA219 (#904) | Measures panel short-circuit current | Buy list |
| 5 printed parts, bearings, M3 hardware | Pan-tilt mount | Print and buy list (section 4) |

## 2. Wiring

**Panel measurement.** The INA219 reads the panel as a near-short-circuit:
- Panel+ → INA219 Vin+; INA219 Vin− → GND; Panel− → GND. The 0.1 Ω shunt carries Isc (about 24 mV at 240 mA). No load resistor.
- Use the INA219's **16 V / 400 mA range** (0.1 mA per count). Above about 350 mA it drops to the 3.2 A range at 0.8 mA per count (8x coarser). The code warns above 380 mA.
- Solder 22 AWG leads to the panel's two pads. The panel has no leads and no mounting holes. Strain-relieve the leads at the frame.
- Sanity check: bus voltage with the panel shorted should be near 0 V. Reversed polarity gives negative current.
- INA219 goes on a free mux channel through a Qwiic/STEMMA QT cable. Servos go on two free HAT channels (S/V+/G): 13 (pan) and 12 (tilt), as in `lab/test_motor.py`.
- Tilt-servo wire needs a slack loop of at least 60 mm so the turntable can pan ±90° (assembly guide, step 8).

**I2C address map**

| Device | Address | Where |
|---|---|---|
| PCA9685 PWM HAT | 0x40 | Upstream (on the Pi) |
| TCA9548A mux | 0x70 | Upstream |
| INA219 (panel) | **0x41** (A0 jumper bridged) | Mux channel |
| BNO055 | 0x28 | Mux channel 6 (`lab/test_sensor.py`) |
| APDS9960 / VL53L4CD | 0x39 / 0x29 | Mux channel (unused) |
| DS3231 RTC (only if bought) | 0x68 | Mux channel |

**I2C rules** [Certain unless noted]
1. The mux connects the selected channel to the upstream bus, so 0x40 and 0x70 are visible on every channel. The INA219 must not stay at its default 0x40, so bridge its A0 jumper (0x41).
2. The PCA9685's power-on "all-call" address is 0x70, the same as the mux. [Likely] Adafruit's driver clears all-call when it initialises, and the robot already runs both as shipped. **Do not re-address the mux** (that means soldering lab equipment). In code, initialise the PCA9685 before touching the mux. The code does this.
3. One lock covers every mux channel selection and read (`hardware.real.BUS_LOCK`). Do not read the INA219 or BNO055 from a second thread without it.
4. The PCA9685 has one PWM frequency for all channels. The lab's `Code/lab/motor_servo_pwm.py` sets it to **100 Hz** for the motors and servos, and the tracker drives the PCA9685 through that file. Do not change the frequency (it would alter wheel-motor behaviour).
5. Run `i2cdetect -y 1` on the Pi to see what is on the bus. To see what is on each mux channel, run `python lab/sensor_scan.py` from `Code/`.

**Servo power.** [Guessing] The HAT's servo rail may share the Pi's 5 V converter. If servo moves reset the Pi: use a separate 5-6 V supply rated 3 A or more (common ground, inline fuse) and a 470-1000 µF capacitor on the HAT. The software slew limit (60°/s) already avoids slamming a servo.

**Clock.** The Pi has no RTC. It needs network time (Windows Internet Connection Sharing on the laptop's Ethernet port [Likely]) or a manual `sudo date -u -s ...` over SSH at the start of each session. A DS3231 is only for the case where neither works.

## 3. Panel

Voltaic P124, 6 V, 1.2 W, ETFE, monocrystalline, 66 × 113 mm, 31.6 g [Certain, vendor spec]. Voc 7.28 V, Imp 220 mA, Isc about 240 mA [Likely]. That fits the INA219's 400 mA range. Panel thickness is 2.6 mm. **The holder does not fit this panel** [Certain, measured in CAD Nov 17]: its slot is 112 × 140 × 3 mm, so a 66 × 113 mm panel is loose in it. Until the holder is resized, fix the panel to the holder back with VHB tape. The panel has solder pads and no mounting holes.

## 4. Mechanical parts

Step-by-step assembly, the servo-caliper check ("before you print") and the pictures are in `Hardware List & Assembly Guide.pdf` (re-exported Nov 17 from the live guide). This section keeps the lists.

**Printed parts (STEPs in `CAD/`, saved in print orientation, no supports). Current as of Nov 17.**

| Qty | Part (STEP file) | Function |
|---|---|---|
| 1 | Base Mount Plate - V2 (276 × 100 mm) | Bridges the rails, carries the lazy susan, holds the pan servo underneath |
| 1 | Turn Table Base - V4 | Rotating platform; captures the pan horn; dovetail slots (open both ends, friction fit) for the uprights |
| 1 | Upright - Servo Side (+X) | Holds the tilt servo |
| 1 | Upright - Bearing Side (−X) | Holds the 693 ball bearing |
| 1 | Solar Panel Holder - Final | Panel tray with the horn hub (+X) and bearing nose (−X) |

`CAD/Solar Tracker Assembly.step` (rebuilt Nov 17) shows these parts, the purchased parts and the M3 hardware in position at pan 0, tilt 0. Purchased-part models are in `CAD/Purchased Parts`. Earlier revisions (Nov 10 assembly, plate V1, turntable Final/V3, the 128.8 mm round lazy susan) are in `CAD/_superseded`; old test prints are in `CAD/Test Prints/_superseded`.

**Print settings (assembly guide):** 0.4 mm nozzle, 0.2 mm layers, 4 walls, 30-40% gyroid, brims on the uprights, bearing nose at 100% infill. The guide allows PLA or PETG. [Likely] Use **PETG or ASA** for a mount that sits in a parked Texas sun, because PLA deforms.

**Purchased hardware**

| Qty | Item | Used in |
|---|---|---|
| 2 | SG90 micro servo with horn kit and M2 screws | Pan (4-arm cross horn), tilt (single-arm horn) |
| 1 | Lazy susan bearing, 94 × 94 × 9 mm square, Ø54 bore, four Ø4.25 holes on an 80.95 mm square in each plate | Pan bearing |
| 1 | 693ZZ ball bearing, 3 × 8 × 4 mm (McMaster 7804K126) | Tilt pivot, bearing side |
| 8 | M3 brass heat-set insert (Ø4.0-4.2 hole, ≤5.5 mm long) | Plate ×4, turntable arms ×4 |
| 12 | M3 × 6 SHCS | Turntable to lazy susan ×4, lazy susan to plate ×4, plate to rails ×4 |
| 1 | M3 × 14 SHCS | Tilt pivot |
| 5 | M3 hex nut (5.5 mm AF) | Rail T-slots ×4, panel holder nut trap ×1 |
| 8 | M3 flat washer | Under the lazy susan screws |
| As needed | Zip tie, 2.5 mm | Servo wires (the CAD has no tie points since Nov 17) |

Use **M3 × 6 at the rails**, not longer: the T-slot cavity bottoms out about 6.8 mm below the counterbore floor. The SG90 and horn dimensions in the CAD are datasheet values; caliper one servo before printing parts that depend on them. [Likely] At pan ±45° the 8 lazy susan screw heads meet on the same 57.25 mm radius between the two bearing plates; if they touch, use M3 × 6 button heads and no washers.

## 5. Electronics purchases and cost

| Item | Part | Cost | Conf. |
|---|---|---|---|
| Solar panel | [Voltaic P124](https://voltaicsystems.com/1-watt-6-volt-solar-panel-etfe/) | $14.00 | Certain |
| Current sensor | [Adafruit INA219 #904](https://www.adafruit.com/product/904) | $9.95 | Certain |
| STEMMA QT / Qwiic cable, 100-200 mm (lab may have spares) | Adafruit or SparkFun | $1.00 | Guessing |
| Shipping (Voltaic + Adafruit) | | $15.00 | Guessing |
| Turntable bearing | Old estimate $6 for a ~75 mm part. The CAD uses a 94 × 94 mm square lazy susan; price not recorded | n/a | n/a |

Original core total (with the old bearing estimate): **$45.95**. The costs of the SG90s, heat-set inserts, screws and filament were not recorded.

**Buy only if a check fails**

| Item | Buy if | Cost |
|---|---|---|
| Metal-gear micro servos (MG90S class), 2 | SG90 backlash or hysteresis is too large (panel plus holder is about 60 g, so torque is not the issue) | $10.00 |
| Adafruit DS3231 RTC #5188 + CR1220 | Pi cannot get network time and setting it over SSH fails | $14.90 |
| USB-to-Ethernet adapter | Laptop has no Ethernet port | $12.00 |
| 5-6 V, 3 A+ buck converter + inline fuse | Servo moves reset the Pi | $10.00 |
| Capacitor 470-1000 µF, 10 V+ | Same | $0.50 |
| VHB double-sided tape | Holder lip is not enough to hold the panel | $5.00 |
| Work light (halogen or bright LED flood) | Lab has no lamp for the indoor demo; it must give tens of mA of Isc | $20.00 |

Worst case if every item is bought: $72.40 extra.

**Assumed team or lab items:** 3D printer and filament (about 100 g), soldering iron, multimeter, M3 assortment, 22 AWG hook-up wire, about 3 m Ethernet cable, laptop with an Ethernet port, phone (inclinometer app for servo calibration; hotspot fallback).

**Removed from the plan:** second panel and second INA219 (replaced by the "virtual fixed panel", `Design Overview.md` section 5.6); load resistors; power bank (the Pi runs from the robot battery); ADS1115 and photodiode quadrant sensor; second PCA9685; panel-mounted IMU (tilt is calibrated instead and the cosine fit corrects residual error); travel router; separate pan servo purchase.
