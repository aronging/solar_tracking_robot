# MXET 345 Solar Tracker — Project Breakdown

**Updated:** Oct 27, 2026 (rev 2: pan-tilt servos, 4-week low-cost scope, one panel) Companion to `mxet345-solar-tracker-plan.md` (design \+ methods), `mxet345-solar-tracker-build-plan.md` (schedule) and `mxet345-solar-tracker-BOM.md` (parts). 5-person team. Confidence tags: Certain / Likely / Guessing. Hour estimates are Guessing.

## Top risks now

- **Outdoor time:** \~2 outdoor sessions in 4 weeks. Every outdoor minute must log data; nothing gets debugged for the first time outside  
- **Servo quality:** unknown lab servo model; backlash sets the floor on pointing accuracy  
- **Heading offset:** BNO055 heading is magnetic and sits near drive motors. It is only used for the coarse turn; the true heading offset is estimated from the sun by least squares (Stage 4\)

## 1\. Mechanical: pan-tilt mount

- Printed frame holds the Voltaic P124 panel (66 × 113 mm, 31.6 g \[Certain\]; no mounting holes → printed frame with a lip, or VHB tape). Tilt axis through the panel \+ frame centre of mass; tilt servo on one side, printed pin on the other  
- Pan: printed plate on a \~75 mm turntable bearing; pan servo drives the plate through its horn, the bearing takes the load  
- Tilt range: panel 46-67° from horizontal in the November window → centre the tilt servo's range near 60°  
- \[Likely\] torque is not the limit (\~60 g panel \+ frame); backlash and stiffness are  
- Print in PETG or ASA  
- No-disassembly rule: bolt-on clamp or plate using existing holes; short mast so the chassis never shades the panel  
- Hard stops on pan; cable strain relief for the panel leads and the Ethernet cable  
- Test aids: printed tilt protractor (or phone inclinometer app) for servo calibration

## 2\. Electrical: power, wiring, bus

- Pi runs off the robot battery as shipped. Servos plug into the HAT  
- \[Guessing\] Check whether the HAT's servo rail shares the Pi's 5 V converter. If servo moves brown out the Pi: separate 5-6 V supply rated 3 A+, common ground, 470-1000 µF bulk capacitor on the HAT  
- I2C: INA219 must move to 0x41 (bridge A0) because the HAT's 0x40 is visible on every mux channel. Do not re-address the mux; initialize the PCA9685 before the mux in code. Full table in the plan  
- Panel wiring for short-circuit current: Panel+ → INA219 Vin+; Vin− → GND; Panel− → GND. The panel runs into the 0.1 Ω shunt (\~24 mV at 240 mA). Set the INA219 to its 16 V / 400 mA range (0.1 mA resolution \[Certain, Adafruit\])  
- Solder 22 AWG leads to the panel's two solder pads; strain-relieve at the frame  
- Connection: Ethernet cable laptop ↔ Pi. With Windows Internet Connection Sharing on the laptop's Ethernet port, the Pi gets an address and network time \[Likely\]; without it, reach the Pi by its link-local address or hostname.local \[Likely\]. Fallback: phone hotspot

## 3\. Sensing and calibration

- Log BNO055 calibration status; do the coarse turn only when the magnetometer is calibrated  
- Least-squares calibrations: tilt and pan servo PWM vs angle (compare up/down sweeps for hysteresis); INA219 current vs bench multimeter; heading offset (site declination first, then refined from the sun)  
- Clock: network time via the laptop (Internet Connection Sharing) or set over SSH at the start of each session (`sudo date -u -s ...`); \[Likely\] a few seconds of error is fine (1 min ≈ 0.25° of azimuth). DS3231 RTC only if neither works  
- Cloud flag: measured Isc vs clear-sky expectation (no extra sensor)  
- Record 5-10 min of static Isc with the panel fixed on the first outdoor day → noise model for the offline method studies

## 4\. Control and actuation

- Tilt: open-loop from the calibrated PWM → angle map; residual tilt error is corrected by the Stage 4 fit (no panel IMU)  
- Pan: open-loop from the calibrated map; heading offset corrected by Stage 4  
- Coarse turn (wheels): spin in place to face south, once per session; wrap heading error to ±180° (classic bug); PID with anti-windup, comparing Euler vs trapezoid on the integral term  
- Servo update every \~1-2 min (sun moves \~0.25°/min; servo resolution \~1°)

## 5\. Numerical core

- Same four stages and core method list as the plan  
- Implement graded methods from scratch (NumPy arrays only); SciPy/NOAA only as references. \[Likely\] the course wants own implementations

## 6\. Software

- Simple loop with four states: ACQUIRE → TRACK → HOLD → PARK  
- Algorithms as pure functions with no hardware imports, so they can be tested on synthetic data on a laptop; one small hardware module wraps the HAT, INA219 and BNO055 (extend the lab's `Sensor_Thread` for the INA219)  
- Log every cycle to CSV (UTC time, predicted az/el, servo commands, Isc, bus voltage, BNO055 heading \+ calibration status, state)  
- Run the tracker inside `tmux` so a dropped SSH session doesn't stop it

## 7\. Validation

- Offline synthetic-data scripts (no full simulator): Kepler stress test, cosine fit vs spread with recorded noise, golden-section noise sensitivity  
- Test ladder: bench → indoor lamp → outdoor session 1 (static logging \+ calibration \+ first tracking) → outdoor session 2 (full tracking run with parked fixed-panel checks)

## Five-person split (each owns a subsystem \+ at least one graded method; \~20-25 h each over 4 weeks, Guessing)

- **A — Mechanical:** topic 1; CAD, print, assemble, mount on the robot; backlash measurement with B; owns the robot on outdoor days  
- **B — Electronics, calibration, parts & TA liaison:** topics 2 and 3; INA219 wiring and logging; servo least-squares calibration; parts order; Ethernet setup  
- **C — Prediction:** solar model; Kepler fixed-point vs Newton \+ stress test; NOAA validation; optional sunrise/sunset bisection vs false position; UTC handling  
- **D — Estimation:** least-squares cosine fit with own LU; cond vs spread study; running heading/tilt offset estimate; virtual fixed-panel gain calculation; optional secant comparison  
- **E — Control & integration:** coarse-turn PID with integration comparison; golden-section acquisition; main loop and states; pointing geometry (az/el → pan/tilt commands)  
- Everyone writes their own section of the proposal and report and builds their own slides

## Questions for the TA (Week 1\)

- Does the HAT's servo power share the Pi's 5 V converter?  
- Can we buy parts ourselves now, or does the lab order them (and how fast)?  
- Is outdoor operation allowed, and how long does the robot battery last?  
- Can we connect to the Pi over Ethernet from a laptop, and does it use DHCP?