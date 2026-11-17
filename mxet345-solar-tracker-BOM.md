# MXET 345 Solar Tracker — Bill of Materials

**Rev 2, Oct 27, 2026.** Matches `mxet345-solar-tracker-BOM.xlsx`. Prices tagged Certain were checked on the vendor page Oct 27, 2026; Guessing = estimate.
Design context: `mxet345-solar-tracker-plan.md`. Order the core items **by Wed Oct 28**.

## Already have — robot kit

| ID | Item | Purpose | Qty | Source / Part # | Unit | Ext. | Conf. | Notes |
|---|---|---|---|---|---|---|---|---|
| H1 | Raspberry Pi (on robot) | Runs all code | 1 | Lab robot | - | - | Certain | Model not stated in lab doc |
| H2 | Adafruit 16-ch PWM/Servo HAT (PCA9685, 0x40) | Drives tilt and pan servos | 1 | Lab robot | - | - | Certain | Initialize before the mux in code (all-call 0x70) |
| H3 | Servo (model TBD) | Tilt axis + pan axis | 2 | Lab robot | - | - | Certain | Ask TA for model; replace with C1 only if plastic-gear / bad backlash |
| H4 | REV HD Hex motor with encoder + motor drivers | Coarse turn to face south, once per session | 2 | Lab robot | - | - | Certain |  |
| H5 | SparkFun Qwiic Mux (TCA9548A, 0x70) | Connects the INA219 | 1 | Lab robot | - | - | Certain | Do not re-address |
| H6 | Adafruit BNO055 IMU (0x28) | Heading for the coarse turn; calibration status | 1 | Lab robot | - | - | Certain | Stays where it is on the robot |
| H7 | Adafruit APDS9960 (0x39) | Optional cloud cross-check only | 1 | Lab robot | - | - | Certain | Likely saturates in direct sun; test once |
| H8 | Adafruit VL53L4CD ToF sensor | Not used | 1 | Lab robot | - | - | Certain |  |
| H9 | Robot battery, rocker switch, CPT DC-DC converter | Powers Pi, motors and servos as shipped | 1 | Lab robot | - | - | Certain | Check whether servo rail shares the Pi 5 V (see C4) |

## Already have — assumed team/lab items (confirm)

| ID | Item | Purpose | Qty | Source / Part # | Unit | Ext. | Conf. | Notes |
|---|---|---|---|---|---|---|---|---|
| T1 | 3D printer + PETG or ASA filament (~100 g) | Panel frame, tilt yoke, pan plate, mast/clamp, tilt protractor | 1 | Team / makerspace | - | - | Guessing | PLA likely deforms in a parked Texas sun |
| T2 | Soldering iron + solder | INA219 A0 jumper, panel leads, INA219 header | 1 | Team / lab | - | - | Guessing |  |
| T3 | Multimeter | Check INA219 current reading | 1 | Team / lab | - | - | Guessing |  |
| T4 | M3 screws and nuts, assorted | Mount assembly | 1 | Team / lab | - | - | Guessing |  |
| T5 | 22 AWG hook-up wire, ~1 m, 2 colours | Panel leads to INA219 | 1 | Team / lab | - | - | Guessing |  |
| T6 | Ethernet cable, ~3 m | Laptop to Pi outdoors | 1 | Team | - | - | Guessing | Leave slack for the coarse turn |
| T7 | Laptop with Ethernet port | SSH, logging | 1 | Team | - | - | Guessing | No port -> C3 |
| T8 | Phone | Inclinometer app for servo calibration; hotspot fallback | 1 | Team | - | - | Guessing |  |

## Buy now (core)

| ID | Item | Purpose | Qty | Source / Part # | Unit | Ext. | Conf. | Notes |
|---|---|---|---|---|---|---|---|---|
| B1 | Voltaic P124 6 V 1.2 W ETFE solar panel | The tracked panel; Isc is the measured signal | 1 | [Voltaic Systems P124](https://voltaicsystems.com/1-watt-6-volt-solar-panel-etfe/) | $14.00 | $14.00 | Certain | 66 x 113 mm, 31.6 g, Voc 7.28 V, Imp 220 mA; solder pads, no leads, no mounting holes |
| B2 | Adafruit INA219 current sensor, STEMMA QT (#904) | Measures panel short-circuit current | 1 | [Adafruit 904](https://www.adafruit.com/product/904) | $9.95 | $9.95 | Certain | Bridge A0 -> 0x41; use 16 V / 400 mA range (0.1 mA resolution) |
| B3 | STEMMA QT / Qwiic cable, 100-200 mm | INA219 to mux | 1 | Adafruit or SparkFun | $1.00 | $1.00 | Guessing | Lab may have spares |
| B4 | Turntable (lazy susan) bearing, ~75 mm | Carries the pan plate so the servo doesn't take the load | 1 | Amazon / hardware store | $6.00 | $6.00 | Guessing | Confirm dimensions before A finalizes CAD |
| B5 | Shipping (Voltaic + Adafruit) |  | 1 |  | $15.00 | $15.00 | Guessing | Estimate; combine orders with teammates to cut it |

## Buy only if needed

| ID | Item | Purpose | Qty | Source / Part # | Unit | Ext. | Conf. | Notes |
|---|---|---|---|---|---|---|---|---|
| C1 | Metal-gear micro servo (MG90S class) | Replace lab servos only if plastic-gear or bad backlash | 2 | Amazon | $5.00 | $10.00 | Guessing | Panel + frame ~60 g, so micro size is enough |
| C2 | Adafruit DS3231 RTC STEMMA QT (#5188) + CR1220 cell | Only if the Pi can't get network time and setting it over SSH fails | 1 | [Adafruit 5188](https://www.adafruit.com/product/5188) | $14.90 | $14.90 | Certain | $13.95 + $0.95 cell; address 0x68 |
| C3 | USB-to-Ethernet adapter | Laptop without an Ethernet port | 1 | Amazon | $12.00 | $12.00 | Guessing |  |
| C4 | 5-6 V, 3 A+ buck converter + inline fuse | Only if servo moves brown out the Pi | 1 | Amazon | $10.00 | $10.00 | Guessing | Common ground with the Pi |
| C5 | Electrolytic capacitor 470-1000 uF, 10 V+ | Servo rail bulk capacitor on the HAT | 1 | Lab stock / Amazon | $0.50 | $0.50 | Guessing |  |
| C6 | VHB double-sided tape | Panel to frame, if the frame lip isn't enough | 1 | Hardware store | $5.00 | $5.00 | Guessing |  |
| C7 | Work light (halogen or bright LED flood) | Indoor lamp demo, if the lab has none | 1 | Hardware store | $20.00 | $20.00 | Guessing | Test early that it gives tens of mA of Isc |

## Totals

| | Cost |
|---|---|
| Core purchases (incl. ~$15 shipping estimate) | $45.95 |
| Buy-if-needed, worst case (all of them) | $72.40 |
| Worst-case total | $118.35 |

## Removed from the plan

| Item | Why |
|---|---|
| Second solar panel (fixed reference) | Replaced by a 'virtual fixed panel' computed from tracked Isc, checked by parking the one panel at the fixed orientation every ~15 min |
| Second INA219 | Only one panel |
| Load resistors | Measuring short-circuit current; no load needed |
| USB power bank | Pi already runs off the robot battery |
| ADS1115 ADC + 4 photodiodes/LDRs | Quadrant sensor stretch goal cut for scope |
| Second PCA9685 PWM board | The robot's HAT already has one |
| Panel-mounted IMU / accelerometer | Tilt is calibrated with a protractor/inclinometer; the cosine fit corrects residual tilt error |
| Travel router | Ethernet to laptop, phone hotspot as fallback |
| Separate pan servo purchase | Pan uses the robot's second servo |

## Picking a solar panel (checklist)

- **Short-circuit current under ~350 mA.** Keeps the INA219 on its 400 mA range at 0.1 mA resolution; above that you drop to the 3.2 A range at 0.8 mA (8× coarser). Many listings give only Imp; Isc is typically a little higher [Likely]
- **Voltage under 26 V** (INA219 limit). Any 5-6 V panel is fine
- **Small and light.** ≤ ~120 mm and ≤ ~60 g keeps micro servos, wind load and tipping moment small
- **Monocrystalline, single rigid panel** (not a flexible sheet that bends on the frame)
- **Encapsulation:** ETFE or glass for outdoor UV and scratch resistance; matte reduces glare. [Likely] any encapsulation departs from the cosine law at very steep angles (> ~60°), which a ±10-20° scan window avoids
- **Leads and mounting:** wire leads vs solder pads vs barrel plug; mounting holes or flat back for tape. Decides how you build the frame and wiring
- **No built-in blocking diode preferred.** A series diode barely changes short-circuit current [Likely] but adds a voltage offset to watch for
- **Datasheet with Isc, Voc, Imp, Vmp, size, weight.** You need Isc and dimensions for the design
- **Price, stock and shipping time.** It has to arrive in Week 1

**Voltaic P124 verdict:** works. 1.2-1.35 W, Imp 220 mA → Isc ~240 mA [Likely] fits the 400 mA range; 66 × 113 mm and 31.6 g is light; mono cells, ETFE, in stock at $14 [Certain]. Only gaps: solder pads (solder your own leads) and no mounting holes (printed frame with a lip, or VHB tape).

Sources: [Voltaic P124](https://voltaicsystems.com/1-watt-6-volt-solar-panel-etfe/) · [Adafruit INA219 #904](https://www.adafruit.com/product/904) · [Adafruit DS3231 #5188](https://www.adafruit.com/product/5188)
