# MXET 345 Final Project: Solar Tracking Robot — Plan

**Updated:** Oct 27, 2026 (rev 2: pan-tilt servos, 4-week low-cost scope, one panel)
**Companion files:** `mxet345-solar-tracker-breakdown.md` (subsystems + team roles) · `mxet345-solar-tracker-build-plan.md` (schedule + procedures) · `mxet345-solar-tracker-BOM.md` / `.xlsx` (parts)
**Confidence tags:** [Certain] hard evidence · [Likely] strong inference · [Guessing] confirm before relying on it. Sun-geometry numbers assume College Station, 30.6°N [Likely].

## Course requirements
- Final project for MXET 345 (Numerical Methods): topic must use substantial (not superficial) numerical methods and include a physical hardware component (lab mobile robot or own hardware)
- Report and demo need a dedicated numerical methods section: explain methods, show where they are in the code, analyze convergence/stability/accuracy, with supporting data/plots/experiments
- Grading: complexity & system design; robustness & accuracy; report/documentation/analysis; creativity & innovation
- Team: 5 students (assigned by the instructor because of class size; the course doc's 3-4 does not apply to us)
- Deliverables: proposal, then report + slides + demo. Proposal covers title/objectives, hardware, numerical methods, expected outcomes and challenges
- Robot rules: don't disassemble, only add parts; give TA a parts list after the proposal
- **Project constraints (team decision):** 4 weeks total, low cost, low hours. Every member has other projects and a heavy course load. Target ~5-6 h per person per week [Guessing]; core purchases ~$30 plus shipping

## Key design decisions
- **Pan-tilt on the robot's two servos.** Tilt servo sets elevation; pan servo (on a turntable bearing) sets azimuth. The wheels only do a coarse alignment: turn the robot to face roughly south at the start of a session, and again only if the pan servo nears its limit
  - Why [Certain, solar geometry]: Nov 3-23, 9 am-3 pm solar time, the sun moves ~100° in azimuth (≈130° → 230°) but only ~17° in elevation (≈23° → 44°). The precise actuator goes on the axis that does most of the tracking; wheel slip and magnetometer error stay out of the fine loop
  - [Certain] A 180° pan servo centred on south covers the whole November day: sunrise azimuth ≈109-114°, sunset ≈246-252°
- **Robot is stationary while tracking.** Fit sample angles are commanded servo angles on both axes, so the fit matrix M is fixed for a given spread (no rebuilding M from IMU angles each cycle)
- **One solar panel:** Voltaic P124, 6 V 1.2 W ETFE (66 × 113 mm, 31.6 g, Imp 220 mA) [Certain, Voltaic spec]
- **Measure short-circuit current (Isc), not power through a load.** [Likely] Isc ∝ irradiance × cos(incidence), the clean objective for the cosine fit. No load resistor
- **Cloud flag from the panel itself:** measured Isc vs the Isc expected for clear sky at the predicted sun position. No extra sensor. The APDS9960 (already in the kit) is an optional cross-check only — [Likely] it saturates in direct sun
- **Connection outdoors:** Ethernet cable laptop ↔ Pi; phone hotspot as fallback
- **All timestamps in UTC.** [Certain] US daylight saving time ends Sun Nov 1, 2026, in the middle of data collection

## Hardware
- **Already have (robot kit):** Raspberry Pi; Adafruit 16-ch PWM/Servo HAT (PCA9685, 0x40) — drives both servos; 2 servos (model TBD) — tilt and pan; 2 REV HD Hex drive motors with encoders and drivers — coarse alignment turn; SparkFun Qwiic Mux (TCA9548A, 0x70); BNO055 IMU — heading for the coarse turn; APDS9960 — optional cross-check; robot battery, switch and DC-DC converter — power the Pi as-is
- **Buy (core):** Voltaic P124 panel, INA219 current sensor, Qwiic/STEMMA QT cable, ~75 mm turntable bearing
- **Buy only if needed:** metal-gear micro servos (if the lab servos are plastic-gear), DS3231 RTC (if the Pi can't get network time), USB-Ethernet adapter, separate servo supply, work light for indoor demo — see the BOM
- **Printed parts (PETG or ASA; [Likely] PLA deforms in a parked Texas sun):** panel frame + tilt yoke, pan plate on the bearing, mast/clamp to the robot (bolt-on, existing holes), tilt calibration protractor
- **Removed from the plan:** power bank (Pi already runs off the robot battery [Certain]); second panel and second INA219; load resistors; ADS1115 + photodiodes; panel-mounted IMU (tilt is calibrated instead; the cosine fit corrects residual tilt error)

## I2C addressing
Two separate address issues; both are about the same bus but need opposite actions:
- **Real conflict — must fix:** [Certain] the TCA9548A connects the selected channel to the upstream bus, so the HAT's PCA9685 (0x40) and the mux itself (0x70) are visible on every channel. Putting a sensor behind the mux does **not** avoid a clash with those two addresses. The INA219 defaults to 0x40 → bridge its A0 jumper to move it to **0x41**
- **Theoretical conflict — do not fix in hardware:** the PCA9685's power-on "all-call" address is 0x70, the same as the mux. The robot already runs the HAT and mux together as shipped, and [Likely] Adafruit's PCA9685 driver clears all-call when it initializes. Do **not** re-address the mux (that means soldering lab equipment). In code, initialize the PCA9685 before touching the mux
- **BNO055 clock stretching:** the lab's provided code already reads it on the Pi's hardware I2C. Only slow the bus if read errors actually appear (that needs config changes on a shared Pi)

| Device | Address | Where |
|---|---|---|
| PCA9685 PWM HAT | 0x40 | Upstream (on the Pi) |
| TCA9548A mux | 0x70 | Upstream |
| INA219 (panel) | **0x41** (A0 bridged) | Mux channel |
| BNO055 | 0x28 | Mux channel (as shipped) |
| APDS9960 | 0x39 | Mux channel (as shipped) |
| VL53L4CD | 0x29 | Mux channel (unused) |
| DS3231 (only if bought) | 0x68 | Mux channel |

## Pointing geometry
- Azimuth A: horizontal angle, 0° = true north, clockwise. Elevation e: angle above the horizon
- Panel tilt from horizontal = 90° − e. In the November window e ≈ 23-44°, so panel tilt ≈ 46-67°: close to vertical. Put the panel's centre of mass on the tilt axis and centre the tilt servo's range around ~60° [Certain, geometry]
- Panel azimuth = robot heading + pan angle. Robot heading = BNO055 heading (magnetic) + magnetic declination + a heading offset estimated by least squares from the sun (Stage 4)

## Algorithm (4 stages)
- **Stage 1 Predict:** sun azimuth/elevation from UTC time and lat/lon. Chain: Julian date → mean anomaly → Kepler's equation (fixed-point vs Newton-Raphson) → true anomaly → declination and equation of time → hour angle → az/el. Check against the NOAA calculator, target < 0.5°. Minor add-on: sunrise/sunset by bisection vs false position
- **Stage 2 Coarse align:** wheels turn the robot in place to face south using BNO055 heading (declination-corrected), PID with a numerically integrated error term (Euler vs trapezoid), heading error wrapped to ±180°. Runs once per session
- **Stage 3 Acquire (startup and after HOLD):** golden-section search + parabolic interpolation on measured Isc, pan axis then tilt axis
- **Stage 4 Track + refine:** point at the prediction; update servos every ~1-2 min. Every 10-15 min scan 5-7 angles per axis at a ±10-20° spread around the prediction, fit Isc(θ) = a·cosθ + b·sinθ + c by least squares, θ* = atan2(b, a). The difference θ* − θ_predicted feeds a running least-squares estimate of the heading offset (pan) and tilt offset
  - Least squares done properly: 5-7 points and 3 unknowns is overdetermined. Solve the normal equations (MᵀM)x = Mᵀy with your own LU decomposition (forward/back substitution) on the 3×3 MᵀM. [Certain] cond(MᵀM) = cond(M)²; cond(M) for a non-square M comes from its singular values
- **Arbitration:** if measured Isc < ~70% of the clear-sky expectation [Guessing threshold] → HOLD: point by prediction only, no scans. Prediction/measurement disagreement over time = running model-error estimate
- **States:** ACQUIRE → TRACK → HOLD → PARK (end of session)

## What Stage 4 is for (why the spread must be wide)
[Certain] Near the peak the cosine curve is flat. Being 2° off the sun reduces Isc by 0.06%; 5° by 0.38%; 10° by 1.5%; 20° by 6%. On this panel (~240 mA Isc [Likely]) with the INA219's 0.1 mA resolution, a ±2° scan changes the reading by about one count. So:
- Narrow spreads (±2°, ±5°) are noise-limited, not just servo-resolution-limited → operate at ±10-20°
- A few degrees of pointing error costs almost no energy, so Stage 4 is not about harvesting more power. Its job is to **measure and correct the system's built-in errors** (true-north/heading offset, mounting offset, servo calibration). That is also the argument that the numerics are essential: without it the prediction points with whatever offsets the robot happens to have

## Numerical methods map
**Core (each gets a full convergence/stability/accuracy analysis):**
| # | Method | Where | Owner |
|---|---|---|---|
| 1 | Fixed-point vs Newton-Raphson (Kepler's equation) | Stage 1 | C |
| 2 | Linear least squares (servo PWM → angle calibration; heading/tilt offset from the sun) | Calibration, Stage 4 | B, D |
| 3 | Golden-section search + parabolic interpolation | Stage 3 | E |
| 4 | Least-squares cosine fit via normal equations + LU, condition number vs spread | Stage 4 | D |
| 5 | PID with numerical integration (Euler vs trapezoid) | Stage 2 | E |

**Optional (cheap, reuse existing data):** bisection vs false position for sunrise/sunset (C); secant method on finite-difference dP/dθ as a comparison to the fit (D) — [Likely] it loses near the flat peak because differencing amplifies noise; say so up front as a planned comparison; QR vs normal equations (D)

**Cut for scope:** full simulator (keep only small synthetic-data scripts for offline method studies), ODE servo/panel model, finite-difference gradient method, joint 2-D quadratic fit, photodiode quadrant sensor, APDS9960 cloud detection, 6-state supervisor

**Superficiality notes:** [Likely] Earth's eccentricity is 0.0167, so Kepler converges in 2-3 iterations and barely changes the answer; standard solar algorithms (NOAA) use a series instead. Keep it, add a synthetic stress test at e = 0.5 and 0.9 to show linear (~factor e per step) vs quadratic convergence, but don't let it carry the "substantial numerics" argument. Same for sunrise/sunset, which doesn't matter in a midday demo. Present LU as the method being demonstrated, not as a speed optimization (a 3×3 solve is trivially cheap)

## Analysis plan
- Kepler error vs iteration, both solvers, including the e = 0.5 / 0.9 stress test
- Solar model vs NOAA over the test days (< 0.5° target)
- Servo calibration: fit residuals; up-sweep vs down-sweep (backlash/hysteresis)
- Golden-section: iterations vs tolerance; sensitivity to Isc noise
- Cosine fit: θ* scatter vs spread (±5°, ±10°, ±15°, ±20°) vs cond(MᵀM)
- Heading offset estimate vs number of scans (convergence of the running least-squares estimate)
- PID coarse turn: step response, Euler vs trapezoid integral term
- Tracking gain vs a fixed panel (one-panel method below)
- Optional: bisection vs false position iterations; secant vs fit on the same scans

## Power gain vs a fixed panel (one panel)
- While tracking, the panel faces the sun, so its Isc ≈ the normal-incidence value I_n
- "Virtual fixed panel": I_fixed(t) = I_n(t) × max(0, cos i_fixed(t)), where i_fixed is the computed angle between the sun vector and a fixed south-facing panel at ~45° tilt (latitude + 15°, a common winter rule of thumb [Likely]). Use an honest reference orientation, not a flat panel, or the gain claim is a strawman
- Validate: every ~15 min, park the panel at the fixed orientation for ~10 s and measure. Measured vs predicted fixed-panel Isc checks both the cosine model and the diffuse-light error
- Gain = ∫I_n dt / ∫I_fixed dt over the session (trapezoid or Simpson)

## Risks
- **Weather:** only ~2 outdoor sessions fit in 4 weeks. Pick days from the forecast, keep a backup day in Week 4
- **Servo model unknown:** if the lab servos are plastic-gear micro servos with bad backlash, buy 2 metal-gear micro servos (~$5 each). Panel + frame is ~60 g [Guessing], so torque is not the issue; backlash is
- **Servo power:** [Guessing] the HAT's servo rail may share the Pi's 5 V converter. Check at the lab; if servo moves cause Pi brownouts, add a separate 5-6 V supply and a 470-1000 µF bulk capacitor on the HAT
- **Indoor demo:** prediction can't be shown with a lamp. Demo Stages 3-4 indoors with a lamp moved by hand; show outdoor data and video for Stages 1-2. Lamp must be bright enough to give tens of mA Isc [Guessing]; test early
- **Backlash:** measure on the actual servos (up vs down sweeps)
- **Shading:** mast height so the robot body never shades the panel; partial shading of a single-string panel collapses Isc
- **Ethernet tether:** strain relief at the robot; leave slack for the coarse turn
- **Light changing during a scan:** keep scans short (5-7 points, < 30 s); skip scans in HOLD

## Next steps (Week 1)
- TA questions (see build plan)
- Order parts by Wed Oct 28
- Submit proposal
- Pick two candidate outdoor days per week from the forecast
