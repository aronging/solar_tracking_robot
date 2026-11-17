# MXET 345 Solar Tracker — Software Overview and Build Specification

**Audience:** the developer building the software from scratch.
**Owner:** Aron (MXET 345 team, 5 students). **Written:** Nov 16, 2026. **Course deliverables due:** about Nov 24, 2026 [Guessing — the course documents give no date].
**Status of the repo:** `Final Project/Code/` is empty. Nothing is written yet.

---

## 0. How to use this document

Read sections 1–5 fully before writing any code. They define the goal, the physical system and the conventions that every module shares. Sections 6–7 define the algorithms. Sections 8–13 define architecture, interfaces, configuration, logging and the command line. Sections 14–16 define testing, analysis output and build order. Section 17 lists what is unknown and how to fail safe.

**Confidence tags** are used for facts that did not come directly from the team's own documents:

- **[Certain]** hard evidence (datasheet, arithmetic, or a check run while writing this spec)
- **[Likely]** strong inference
- **[Guessing]** filling a gap — make it a config value and flag it, do not bake it in

Anything untagged comes from the team's own plan, build plan, BOM, assembly guide or the course documents.

**Rules for the implementer:**

1. Do not invent hardware facts. Every unknown (channel numbers, wheel-driver mapping, site coordinates) must be a config value that defaults to `None` or a clearly labeled placeholder. The real-hardware backend must refuse to start while a required hardware value is `None` (section 17.2).
2. Follow section 16's build order. The numerics and the simulator come first so everything can be tested on a laptop with no robot.
3. The code must run, import and pass tests on **Windows and Linux without any Raspberry Pi libraries installed**. Hardware libraries are imported lazily, only by the real backend.
4. Do not add features that are not in this document. Section 18 lists what is deliberately out of scope. If something in this spec is ambiguous, pick the simpler reading, write the choice in the README under "Decisions", and continue.
5. Everything the course grades must be easy to find: each graded numerical method needs its own module, its own tests, an analysis script and a docstring tag (section 15).

---

## 1. Mission and desired outcome

### 1.1 One paragraph

A small solar panel sits on a two-servo pan-tilt mount bolted to the lab's wheeled robot. The software on the robot's Raspberry Pi predicts where the sun is from the clock (a solar-position model that uses Kepler's equation), points the panel at it, searches for the exact power peak using the panel's own short-circuit current, and every 10–15 minutes scans around the prediction and fits a cosine curve to the measured current. The fit reveals the system's built-in pointing errors (compass heading offset, mounting offset, servo calibration error), and the software learns and corrects them. The wheels are used once per session: to turn the robot to face roughly south using IMU heading feedback with a PID controller.

### 1.2 Why this exists (the course constraint that shapes everything)

This is the final project for **MXET 345, Numerical Methods in Robotics Applications** (Texas A&M). The course requires:

- A topic that uses numerical methods **substantially, not superficially**, with a physical hardware component.
- A dedicated numerical-methods section in the **report and the demo**: explain each method, show where it lives in the code, analyze **convergence, stability and accuracy**, and back it with data, plots or experiments.
- Grading on: complexity and system design; robustness and accuracy; report, documentation and analysis; creativity.

So the software has two jobs of equal weight: **(a)** make the tracker work, and **(b)** produce clean, loggable, comparable numerical results that the team can turn into plots. A tracker that works but cannot show convergence plots scores badly. Design every numerical routine so it can report its iteration history.

### 1.3 Definition of done

The project is done when all of these are true:

1. `python -m solar_tracker track` runs a full outdoor session on the robot: preflight → coarse turn → acquire → track with periodic refinement scans → park, without operator input, and writes complete logs.
2. The same code runs unchanged against a simulated rig on a laptop (`--hardware sim`), including a full simulated day in under a minute.
3. The five core numerical methods (section 7) are implemented from scratch, unit-tested, and each has an analysis script that produces the figures listed in section 15.
4. An indoor mode (`lamp`) lets the team demo acquire and refine live with a lamp moved by hand.
5. A README explains setup on the Pi, the run procedure, the log formats and a method-to-code map.

### 1.4 The numerical argument (so the design stays honest)

[Certain] Near the peak, the cosine response is flat: a 2° pointing error costs 0.06% of the current, 5° costs 0.4%, 10° costs 1.5%, 20° costs 6%. The tracker's purpose is therefore **not** to harvest much more energy than a well-aimed fixed panel. Its purpose is to **measure and remove the system's built-in angular errors** (true-north heading error, mounting offset, servo calibration) using least-squares fits to real measurements. Without Stage 4 the prediction points wherever those offsets happen to push it. This is the argument the report will make that the numerics are essential. Do not weaken it by shortcutting the fit (for example by replacing it with "move toward the higher of two readings").

---

## 2. Superseded ideas (do not implement)

Older planning notes mention wheel-driven azimuth tracking, a four-photodiode quadrant sensor with an ADS1115, a second reference panel and a power bank, a panel-mounted IMU, a full physics simulator, a five-stage design with joint 2-D quadratic fits, and ODE servo models. All of these were cut for scope. The current design is the pan-tilt servo mount with one panel, one INA219 and the stages in section 6. If another file in the `Final Project` folder disagrees with this document, this document wins, except for the physical facts in `Hardware List & Assembly Guide.pdf` (Nov 10), which win over everything for mechanical details.

---

## 3. The physical system (what the software talks to)

### 3.1 Mechanical (from the Nov 10 assembly guide)

- **Pan axis:** vertical, through the lazy-susan bearing's centre. SG90 servo under the base plate drives a 4-arm horn captured in the turntable. **Range ±90°**.
- **Tilt axis:** horizontal, 75 mm above the turntable top. SG90 in the +X upright drives a single-arm horn in the panel holder; the −X side pivots on a 3×8×4 mm ball bearing. **Range ±90° from vertical.**
- **Servo centre:** both servos are centred at **90° = 1500 µs** during assembly. At tilt = 0 the panel stands **vertical**.
- **Pan zero:** the turntable's long dovetail arms point across the robot rails. With the robot viewed from its front (the cable-ear end of the base plate), the panel faces the viewer at pan 0, tilt 0.
- **Software limits:** about ±85° on both axes, so neither servo stalls on its end stop.
- **Servo offsets from horn indexing:** up to about ±8° may remain after assembly. They must be measured and trimmed in software (section 6.0, calibration).
- The tilt-servo wire needs ≥60 mm of slack to permit full pan travel; the code does not care, but never command beyond the limits.
- The base is bolted to the robot's frame rails. **The robot does not move while tracking.** The wheels only run during the coarse turn.

### 3.2 Electronics

| Item | Facts the software needs |
|---|---|
| Raspberry Pi | Model not stated in the lab docs [Guessing: Pi 4 or 5, Raspberry Pi OS]. SSH from a laptop. User `pi`, venv `~/env`, project folder `/home/pi/mxet345_project`, interpreter `/home/pi/env/bin/python`. |
| Adafruit 16-ch PWM/Servo HAT (PCA9685) | I2C **0x40**. Drives both tilt/pan servos **and** the wheel motor drivers. The two SG90 servos sit on two free channels (**numbers not recorded**). |
| SparkFun Qwiic Mux (TCA9548A) | I2C **0x70**, 8 channels. Sensors sit behind it. |
| Adafruit INA219 (STEMMA QT #904) | The panel sensor. **A0 jumper bridged → address 0x41** (the default 0x40 collides with the HAT). Sits on a mux channel (**number not recorded**). |
| BNO055 IMU | Address 0x28 behind the mux. Used **only** for robot heading during the coarse turn and for monitoring. Calibration status (0–3 each for sys/gyro/accel/mag) must be checked before the turn. |
| APDS9960 (0x39), VL53L4CD (0x29) | Present in the kit. **Not used.** |
| REV HD Hex motors with encoders, 2 | Differential drive, driven through three small green driver boards (channel mapping unknown). Encoders are not required by this design. Used only for the coarse turn. |
| Solar panel | Voltaic P124, 6 V, 1.2 W, ETFE, 66×113 mm, 31.6 g. [Certain, vendor spec] Imp 220 mA, Voc 7.28 V. Isc ≈ 240 mA [Likely]. |

**I2C rules that bite [Certain unless noted]:**

1. The mux connects the selected channel onto the upstream bus, so the HAT (0x40) and the mux (0x70) are visible on every channel. The INA219 must not be at 0x40 (it is at 0x41).
2. The PCA9685's power-on "all-call" address is 0x70, the same as the mux. [Likely] Adafruit's PCA9685 driver disables all-call when it initialises. **Initialise the PCA9685 object before touching the mux.** Never re-address the mux.
3. The mux holds state ("which channel is open"). **All mux-using reads must go through one lock** (section 8.3). The lab's `Sensor_Thread` runs in the background; do not read the INA219 or BNO055 from a second thread without that lock.
4. **The PCA9685 has one PWM frequency for all 16 channels.** The lab's `motor_servo_pwm.py` already sets it for both motors and servos. **Do not change `pca.frequency`.** Read it back, assert it is about 50 Hz (a servo-compatible value) and log it. If it is not 50 Hz, stop and report: changing it would alter wheel-motor behaviour. [Likely: the lab's setup runs at 50 Hz because the same HAT drives servos.]
5. [Likely] The BNO055 clock-stretches, which can cause occasional `OSError` on the Pi's hardware I2C. Retry up to 3 times with a short sleep before declaring a fault.

### 3.3 Measurement principle

The INA219 is wired across the panel as a near-short-circuit: Panel+ → Vin+, Vin− → GND, Panel− → GND. The 0.1 Ω shunt in the INA219 carries the panel's **short-circuit current Isc**.

- [Likely] Isc ∝ irradiance × cos(incidence angle). This is the objective function for everything (acquire, refine, cloud flag).
- Use the INA219's **16 V bus range and 400 mA current range** (gain /1, ±40 mV shunt → 0.1 mA per count). Isc ≈ 240 mA fits. Warn if a reading exceeds 380 mA (near range limit).
- Average samples: set the ADC to 12-bit with hardware averaging if the library supports it (about 68 ms per 128-sample average) and/or average several reads in software. Every reading the software uses must carry its mean, its sample standard deviation and its sample count.
- Library names (verify against the installed version before relying on them) [Likely]: `adafruit_ina219` with `INA219(i2c, addr=0x41)`, `.set_calibration_16V_400mA()` or `.gain = Gain.DIV_1_40MV` with `.bus_adc_resolution` / `.shunt_adc_resolution`, `.current` (mA), `.bus_voltage` (V), `.shunt_voltage` (V).
- The bus-voltage reading with the panel shorted should be near 0 V. Use it as a wiring sanity check (reversed polarity gives negative current).
- Measured power through a load is **not** used. There is no load resistor.

---

## 4. Conventions (every module must follow these)

### 4.1 Angles and frames

| Quantity | Definition |
|---|---|
| **Azimuth A** | Horizontal angle, **0° = true north, increasing clockwise** (90° = east, 180° = south). Range [0, 360). |
| **Elevation e** | Angle above the horizon, degrees. |
| **Heading (robot)** | True-north azimuth of the robot's reference axis. `heading_true = wrap360(imu_heading + declination)`. The BNO055 gives **magnetic** heading; add magnetic declination (east positive) to get true. Declination is a config value (`site.declination_deg`). [Likely] about +2° (east) for central Texas in 2026 — look up the exact value for the site and date from NOAA's magnetic-field calculator and record the source in the README. |
| **Pan angle** `pan_deg` | Signed, 0 at servo centre (1500 µs), range ±90°, soft limit ±85°. Panel normal azimuth `A_n = heading_true + az_offset + pan_sign · pan_deg`. |
| **Tilt angle** `tilt_deg` | Signed, **measured from vertical**, 0 at servo centre (panel vertical), range ±90°, soft limit ±85°. Panel normal elevation `e_n = el_offset + tilt_sign · tilt_deg`. |
| **`pan_sign`, `tilt_sign`** | Each ±1. Defaults +1 [Guessing]: positive pan turns the normal clockwise seen from above; positive tilt lifts the normal toward the zenith. **Must be verified on first power-up** and stored in config. |
| `az_offset`, `el_offset` | Learned corrections in degrees. They absorb heading error, mounting error and servo zero error. Starting values come from config (default 0). |

**Tilt convention warning.** Earlier planning documents describe tilt "from horizontal" (panel tilt = 90° − elevation, with the servo centred near 60°). The Nov 10 assembly guide measures tilt **from vertical**. This spec follows the assembly guide. With `tilt_sign = +1` the tilt command equals the sun's elevation: in the November window (e ≈ 23–44°), `tilt_deg ≈ +23…+44`. The fixed-panel comparison in section 6.7 states its tilt "from horizontal"; convert with `e_n = 90° − tilt_from_horizontal`.

**Angle hygiene:**

- All public function arguments and config values are in **degrees**. Radians appear only inside math functions. Name variables with units: `pan_deg`, `isc_mA`, `t_s`, `bus_V`, `pulse_us`.
- Provide `wrap180(x)`, `wrap360(x)` and `angdiff(a, b) = wrap180(a − b)` in `geometry.py`. Every azimuth or heading subtraction goes through `angdiff`. (Forgetting the wrap on heading error is the classic bug: 359° → 1° must be a +2° error, not −358°.)

### 4.2 Time

- All timestamps are **UTC**, timezone-aware (`datetime.now(timezone.utc)`). Never use local time anywhere. [Certain] US daylight saving ended Sunday Nov 1, 2026; local-time logic would put the sun model off by 15° in hour angle.
- Intervals and scheduling use `time.monotonic()`, never wall time.
- All code takes an injectable `Clock` (section 8.4), so the simulator can run a whole day in seconds.
- The Pi has no battery-backed clock (no RTC in the plan). Preflight must report the Pi's UTC time and whether the system clock is NTP-synchronised (`timedatectl show -p NTPSynchronized --value`, fall back to `chronyc tracking`). [Likely] with the Pi connected only to the laptop by Ethernet, the clock can be wrong. A clock error of 1 minute equals 0.25° of pointing; 1 hour equals 15°. In sun mode, refuse to start unless the clock is synchronised or the operator passes `--ack-clock` after checking it.

### 4.3 Units and ranges

Currents mA, voltages V, time s, angles degrees, pulses µs. Servo pulse range default 500–2500 µs (0.09°/µs, 1500 µs = centre) [Guessing — replaced by the calibration fit].

[Certain, arithmetic] PCA9685 resolution at 50 Hz is 20 ms / 4096 = 4.88 µs per count, which is about 0.44° per count at 0.09°/µs. The SG90's own deadband and plastic-gear backlash are larger [Likely]; expect about 1° effective resolution.

### 4.4 Code style

- Python 3.9+ compatible [Guessing: the Pi's Python is not recorded; Bookworm ships 3.11]. Type hints and dataclasses. Standard-library `logging` for diagnostics.
- **Numerical routines are pure functions** with no hardware imports, no globals, no sleeping. They take plain floats and lists and return dataclasses that include an iteration history.
- **Numerics use only the standard library (`math`, plain lists).** `numpy` is allowed in `analysis/`, `tests/` and the simulator only, as a reference to check the from-scratch code. Do not call `numpy.linalg`, `scipy` or `pvlib` inside the graded modules (`solar_tracker/numerics`, `solar_tracker/solar`, `solar_tracker/control`). [Likely] the course rewards own implementations; the libraries serve as accuracy references.
- Docstring tag for the method-to-code map: every graded function carries a line `NM-METHOD: <name> | STAGE: <n>` so a small script can list them (section 14.3).

---

## 5. System architecture

```
                  Laptop (SSH over Ethernet; tmux on the Pi)
                                   │
┌───────────────────────── Raspberry Pi ──────────────────────────────┐
│                                                                     │
│  cli.py ──► supervisor.py (state machine, scheduling, safety)       │
│                 │                                                   │
│     ┌───────────┼─────────────────────────────┐                     │
│     ▼           ▼                             ▼                     │
│  solar/      control/                     logging_.py               │
│  position    heading (PID)                (CSV + JSONL)             │
│  clearsky    acquire (golden+parabolic)                             │
│              refine  (cosine LS fit)                                │
│              offsets (running LS)                                   │
│                 │  all use  ▼                                       │
│            numerics/  roots, linalg(LU), leastsq, optimize,         │
│                       integrate                (pure Python)        │
│                 │                                                   │
│                 ▼  only through the HAL interfaces (hardware/base)  │
│     ┌──────────────────┬───────────────────────┐                    │
│     │ real.py (Pi)     │ sim.py (laptop, tests)│                    │
│     └─────┬────────────┴──────────┬────────────┘                    │
│           │                       │ virtual clock, virtual sun,     │
│  PCA9685 ─┴─► pan/tilt servos     │ cosine panel, noise, backlash   │
│          └──► wheel drivers       │                                 │
│  Mux ─► INA219 (panel Isc), BNO055 (heading)                        │
└─────────────────────────────────────────────────────────────────────┘
```

Core design rule: **algorithms never touch hardware**. They receive an `f(angle) -> reading` callback or a plain list of numbers. The supervisor wires callbacks to the HAL. That is what lets the same code run on the robot, in the simulator and in unit tests.

---

## 6. The algorithm, stage by stage

The session pipeline is: **Preflight → Coarse align → Acquire → Track (with periodic Refine) → Park**, with **Hold** entered when cloud cover is detected, and a **Fault** handler that parks safely.

### 6.0 Preflight and calibration inputs

**Preflight** (`preflight` command, also run at the start of every session):

1. Initialise the I2C bus, then the PCA9685, then the mux (that order). Run an I2C scan (`i2cdetect -y 1` equivalent) and log which addresses answer. Expect 0x40, 0x70 upstream.
2. Read back the PCA9685 frequency; assert about 50 Hz (section 3.2, rule 4).
3. Open the INA219 at 0x41 on the configured mux channel; read current and bus voltage; warn on negative current (polarity), on bus voltage above 1 V (not shorted) and on current above 380 mA.
4. Read the BNO055 heading and calibration status. Require `mag ≥ 3` before the coarse turn (configurable). Print the status and tell the operator how to calibrate (move through figure-eights, hold still on each face) if it is lower.
5. Clock check (section 4.2).
6. Compute the sun position now and log it. If the sun is below `min_elevation_deg`, say so.
7. Slowly sweep each servo ±20° and back (slew-limited) to confirm motion without a Pi reset.

**Servo calibration** (`calibrate-servo` command + `analysis/fit_servo_cal.py`) — this is **graded method #2 (linear least squares)**:

1. For each servo, step the pulse width through its usable range in about 10 µs-multiples in an *up* sweep and then a *down* sweep. After each step the operator reads the actual angle from a protractor or a phone inclinometer and types it in (the command shows a prompt and appends to `servo_cal.csv`).
2. Fit `angle_deg = m · (pulse_us − 1500) + c` separately for up and down sweeps with the own least-squares routine. Report residual RMS, the fitted slope and the **hysteresis** (mean gap between the up and down lines).
3. Write `config/servo_cal.json` (per servo: `m`, `c`, `hysteresis_deg`, `pulse_min_us`, `pulse_max_us`, `rms_deg`). The HAL converts commanded angle → pulse with the inverse of the *mean* of the two lines.
4. Until a calibration file exists, use the defaults of section 4.3 and log a warning.

### 6.1 Stage 1 — Predict the sun (graded methods #1 and optional #6)

`solar/position.py: sun_position(t_utc, lat_deg, lon_deg) -> SunPosition(az_deg, el_deg, decl_deg, ra_deg, hour_angle_deg, kepler_iterations)`.

The chain (formulas verified against the NOAA general-solar-position equations while writing this spec; they agree within 0.02° [Certain, see appendix A]):

1. `JD` from the UTC time (Gregorian calendar conversion). `n = JD − 2451545.0` (days from J2000.0). Ignore ΔT (a 69 s error moves the Sun's ecliptic longitude by under 0.001°).
2. Mean anomaly `M = wrap360(357.5291° + 0.98560028°·n)`, in radians for the solver.
3. Eccentricity `e = 0.016709 − 1.151e-9·n`.
4. **Solve Kepler's equation** `E − e·sin E = M` with **two interchangeable solvers**: fixed-point iteration `E_{k+1} = M + e·sin E_k` and Newton-Raphson `E_{k+1} = E_k − (E_k − e·sin E_k − M)/(1 − e·cos E_k)`. Both must return the iteration count and a residual history.
5. True anomaly `ν = 2·atan2(√(1+e)·sin(E/2), √(1−e)·cos(E/2))`.
6. Ecliptic longitude `λ = ν + ϖ`, with the longitude of perihelion `ϖ = 282.9373° + 4.70684e-5°·n`.
7. Obliquity `ε = 23.4393° − 3.563e-7°·n`.
8. Declination `δ = asin(sin ε · sin λ)`. Right ascension `α = atan2(cos ε · sin λ, cos λ)`.
9. Greenwich mean sidereal time `GMST = wrap360(280.46061837° + 360.98564736629°·n)`.
10. Local hour angle `H = GMST + lon_east − α`.
11. Elevation: `sin e = sin φ · sin δ + cos φ · cos δ · cos H`.
12. Azimuth (from north, clockwise): `A = atan2(−cos δ · sin H, sin δ · cos φ − cos δ · sin φ · cos H)`, wrapped to [0, 360). (Sanity: at solar noon in the northern hemisphere, A ≈ 180°; in the afternoon, A is greater than 180°.)

Do not apply atmospheric refraction to the pointing (about 0.02° at 23–44°); mention it in the README.

**Why two solvers and a stress test.** [Certain] Earth's eccentricity is 0.0167, so both solvers converge in a handful of iterations and the answer barely changes. That is the "superficial" risk the report must address. Required behaviour: the analysis script runs both solvers at the real e and at **synthetic stress eccentricities 0.5 and 0.9**, plots error versus iteration, and shows fixed-point convergence is linear (error shrinks roughly by a factor `e·cos E` per step) while Newton-Raphson is quadratic. Reference iteration counts measured while writing this spec (tolerance 1e-12, starting from E = M, or E = π for e ≥ 0.8): Earth's e takes 3 Newton / 6–7 fixed-point; e = 0.5 takes 5 Newton / 25–27 fixed-point; e = 0.9 takes 5–6 Newton / 18–89 fixed-point depending on M. Use these only as rough expectations; do not assert exact counts in tests.

**Sunrise/sunset (optional, Tier 2).** `sunrise_sunset(date_utc, lat, lon)` finds the two roots of `elevation(t) = −0.833°` by **bisection** and by **false position** (regula falsi), each on a bracket (local-midnight-ish time with el < threshold to solar noon with el > threshold). Report iterations to the same tolerance for both. Used in the supervisor to decide when to start and park, and as a second root-finding comparison for the report.

### 6.2 Stage 2 — Coarse align (graded method #5: PID with numerical integration)

Purpose: before tracking, turn the robot in place so the pan servo's range is centred on south. This runs **once per session** (and again only if the sun's pan angle approaches the limit).

- Input: `heading_true` from the BNO055 (section 4.1). Target: `target_heading_deg = 180 − az_offset_init_deg` so that the panel's pan-zero direction faces south. Default `az_offset_init_deg = 0` (the panel faces the IMU's reference axis at pan 0 [Guessing — measure and record it]).
- Error `e = angdiff(target, heading)` — always through `angdiff`.
- **PID**: `u = Kp·e + Ki·∫e dt + Kd·(de/dt)`. The integral term is **selectable** between Euler (`I += e·dt`) and trapezoid (`I += 0.5·(e + e_prev)·dt`), optionally Simpson over the last three samples. The derivative is a backward difference on the *measurement* with a first-order low-pass filter (config `d_filter_tau_s`). The class holds anti-windup (clamp the integral so the output does not exceed saturation, or use back-calculation) and an integral-reset on large error.
- Output `u ∈ [−1, 1]` maps to a turn-in-place wheel command: left wheel `−u`, right wheel `+u` (sign configurable). A **minimum effective duty** (config `min_turn_duty`) compensates the motors' deadband: if `0 < |u| < min` → use `±min`. [Guessing] value ~0.25; measure it.
- Termination: |error| < `tol_deg` (default 2°) for `hold_s` (default 1.0 s) → stop wheels, record the final heading (average 20 IMU samples), report success. Timeout `max_turn_s` (default 40 s) → stop wheels, mark `coarse_align_failed`, continue with a warning (the operator can place the robot by hand using a compass instead).
- Loop rate 20 Hz. Log every sample to `turn.csv` (section 11).
- **Safety:** wheel outputs are zeroed in a `finally` block, on `KeyboardInterrupt`, on any exception, and by a watchdog if the loop stalls longer than 1 s. The command refuses to run unless `--robot-on-ground` is given (this prevents spinning on a bench) or `--bench` is given (wheels disabled, controller still runs on IMU readings with a virtual plant).
- **Manual alternative:** `--skip-turn` skips the wheels; the operator aligns the robot by hand and the code simply reads and records the heading.
- **Analysis experiment** (required for the report): the same step response in the **simulator plant** with Euler and with trapezoid integration, and at least one hardware run with each. Report rise time, overshoot, settling time and steady-state error, and a gain-versus-stability sweep (section 15).

### 6.3 Stage 3 — Acquire (graded method #3: golden-section search + parabolic interpolation)

Runs at session start, after Hold ends, and when a refine scan fails its quality gates repeatedly. It finds the pan angle then the tilt angle that maximise Isc.

`control/acquire.py: acquire_axis(f, center_deg, half_width_deg, limits_deg, ...) -> AcquireResult`, where `f(angle_deg) -> isc_mA` is a callback that moves the servo, waits for it to settle, and returns an averaged reading.

1. **Coarse bracket:** evaluate `f` at `n_coarse` (default 9) evenly spaced angles over `[center − half_width, center + half_width]` clipped to `limits_deg`. Take the best point `i`. The bracket is `[x_{i−1}, x_{i+1}]`. If the best point is at an edge, shift the window by `half_width` toward that edge (once), re-run the coarse pass, and flag `edge_peak` if it is still at the edge.
2. **Golden-section search** on the bracket (maximising `f`) with golden ratio `φ = (√5 − 1)/2`. Reuse one evaluation per iteration. Stop when the interval width falls below `tol_deg` (default 1.5°) or after `max_evals` (default 24).
3. **Parabolic interpolation:** fit a parabola through the best point and its two nearest evaluated neighbours; take the vertex if it lies inside the bracket and the parabola opens downward; otherwise fall back to the golden-section best point. Return both estimates.
4. The result carries the full history: every `(phase, iteration, x, f, interval_width)` for convergence plots, plus `evals`, `x_golden`, `x_parabolic`, `x_best`.
5. **Axis order in a full acquire:** pan search (tilt held at its predicted value), then tilt search (pan at the pan result), then one more pan pass (`n_passes = 2`).
6. **Sun mode window:** first acquire after a coarse turn uses a **wide** window (`acquire_half_width_deg`, default 40°) because the initial offsets are unknown. Later acquires use ±15° about the prediction plus the learned offsets.
7. **Bootstrap:** after the first successful sun-mode acquire, set `az_offset = x_pan_peak_in_azimuth − predicted azimuth` and `el_offset = x_tilt_peak − predicted tilt` (i.e., the difference between where the sun is and where the maximum was found), subject to `max_bootstrap_offset_deg` (default 40°). If larger, raise a Fault with a clear message ("is the panel facing the sun? is the clock right?").
8. **No-signal guard:** if the best `f` is below `min_signal_mA` (default 5 mA [Guessing]) the search is meaningless (night, heavy cloud, panel covered). Return `no_signal` and let the supervisor go to Hold or Park.
9. **Noise:** the supervisor's callback averages enough samples per point that the noise on `f` is well below the coarse variation; the analysis script studies sensitivity to noise (section 15).

**Lamp mode** has no sun model: the window centre is the current pointing, the half-width is large (default 60°), and Acquire is the whole job. After acquire, the supervisor monitors Isc and re-acquires with a smaller window when Isc drops by more than `lamp_reacquire_drop_frac` (default 10%) from the peak value — this lets the team move the lamp by hand during the demo.

### 6.4 Stage 4 — Track and refine (graded method #4: least-squares cosine fit via normal equations and LU, plus condition number)

**Tracking:** every `predict_update_s` (default 60 s) compute the sun position, convert it to `(pan_deg, tilt_deg)` using the current offsets (pointing maths in appendix B), slew-limit, and command the servos. If the commanded pan or tilt falls outside the soft limits, clamp and set the flag `LIMIT_PAN` or `LIMIT_TILT`. If `LIMIT_PAN` persists for more than `limit_replan_s` (default 300 s), log an event suggesting a new coarse turn.

**Refine scan** every `scan_interval_s` (default 720 s [Guessing 10–15 min]), not during Hold, not within `scan_guard_s` of a fixed-panel check:

For each axis (pan first, then tilt) with the other axis held at its predicted position:

1. Choose `K` scan points (default 7; allowed 5–7) evenly spaced at `δ_k ∈ [−S, +S]` around the predicted command, with spread `S` (default **15°**; allowed 10–20°). Operating at ±2° or ±5° is deliberately avoided: [Certain] at ±2° the signal changes by about one INA219 count (0.1 mA) out of 240 mA, so the fit is noise-limited; the analysis script demonstrates this by including the small spreads in the offline study.
2. Move to the **centre** and take a reading (`center_start`). Visit the K points in a randomised or alternating order (config `scan_order`: `sweep` or `shuffled`; default `shuffled` to decorrelate drift from angle). Take a second centre reading (`center_end`). The whole scan must finish in under `max_scan_s` (default 30 s); otherwise discard it.
3. Fit the model `Isc(δ) = a·cos δ + b·sin δ + c` by **linear least squares** where the data are `(δ_k, y_k)`. This is the overdetermined K×3 system `M x = y` with rows `[cos δ_k, sin δ_k, 1]`. Solve the **normal equations** `(MᵀM) x = Mᵀ y` with the own **LU decomposition (partial pivoting) and forward/back substitution** on the 3×3 `MᵀM`. Do not use a library solver in the graded code.
4. The peak offset is `δ* = atan2(b, a)` (degrees). The peak amplitude is `R = √(a² + b²)`. [Certain] `a·cos δ + b·sin δ = R·cos(δ − δ*)`, so `δ*` is always a maximum.
5. Compute: residual RMS; the fit covariance `s²·(MᵀM)⁻¹` with `s² = RSS/(K − 3)` (inverse via the same LU, column by column); `σ_δ*` by propagating the covariance through `δ* = atan2(b, a)` using `∂δ*/∂a = −b/R²` and `∂δ*/∂b = a/R²`; and the **condition number** of `MᵀM` (2-norm, by own power iteration for λmax and inverse iteration through the LU for λmin; a 1-norm estimate through the LU inverse is also acceptable). [Certain] `cond₂(MᵀM) = cond₂(M)²`; `cond₂(M)` for the non-square `M` comes from its singular values, so the analysis script cross-checks against `numpy.linalg.svd`.
6. **Quality gates.** Accept the scan only if all hold; otherwise log `accepted = false` with the first failing reason:
   - mean Isc ≥ `min_signal_mA`;
   - `K ≥ 5` valid points and no sample flagged as over-range;
   - residual RMS ≤ `max_rms_frac × mean Isc` (default 0.03 [Guessing]);
   - `|δ*| ≤ gate_peak_in_window_frac × S` (default 1.0, i.e., the peak must lie inside the window);
   - `|center_end − center_start| / mean ≤ max_drift_frac` (default 0.03; light changed during the scan);
   - `cond₂(MᵀM) ≤ max_cond` (default 1e4 [Guessing]);
   - `σ_δ* ≤ max_sigma_deg` (default 3°).
7. **Learning the offsets (running least squares).** An accepted scan yields a *total* offset measurement `o_i = offset_used_in_the_command + δ*_i` for that axis. Keep the list of accepted `o_i` per axis and estimate the constant offset as their **weighted mean** (weights `1/σ_i²`, with a floor), optionally with an exponential forgetting factor (`offset_forget`, default 1.0 = none). The estimator also exposes its standard error. The next predictions use the new estimate. The bootstrap value from acquire is the first sample. The estimator-versus-number-of-scans curve is a required convergence plot.
8. **Disagreement monitor.** Log `|δ*|` for every accepted scan. Persistent disagreement larger than 3σ of the estimate flags `MODEL_DRIFT` in the log (heading drift, bumped mount) and widens the next window; two consecutive rejected scans trigger a re-acquire.

**Optional comparison (Tier 2): secant method.** Estimate `dP/dθ` by finite differences of the same scan data and find its root with the secant method. [Likely] this loses to the fit near the flat peak because differencing amplifies noise. The report plans to say so up front; implement it only after Tier 1 is done. A **QR (Householder) vs normal-equations** comparison on the same data is another optional Tier-2 study.

### 6.5 Stage 5 — Cloud flag and Hold

- Expected clear-sky normal-incidence current: `I_clear(e) = k · 0.7^(AM^0.678)` with air mass `AM = 1/sin(e)` (the Meinel/Laue-type attenuation form; the constants are approximate [Likely]). `k` (mA) is estimated from the first successful acquire/scan of a session assumed to be under clear sky (config `assume_clear_start = true`) as `k = Isc_peak / 0.7^(AM^0.678)`, and logged. Unless the operator passes `--k-mA`, use the estimate.
- Cloud ratio `ρ = Isc_measured / (I_clear(e) · max(0, cos i_pred))` where `cos i_pred` is the predicted incidence cosine at the current commanded pointing (it is about 1 when tracking well).
- Enter **Hold** when `ρ < hold_enter_ratio` (default 0.70 [Guessing]) for `hold_enter_samples` consecutive ticks (default 5). In Hold, keep pointing by prediction only; **no scans**; do not change offsets. Leave Hold when `ρ > hold_exit_ratio` (default 0.80) for `hold_exit_samples` ticks (default 10) and go to Acquire (narrow window) if Hold lasted longer than `reacquire_after_hold_s` (default 300 s), otherwise straight to Track.
- Do not let a cloud ever contaminate the offset estimate: any scan whose centre readings differ by more than the drift gate is discarded, and no scan starts while `ρ` is below the enter threshold.

### 6.6 Park

When the sun's predicted elevation falls below `min_elevation_deg` (default 10°, configurable), or the operator stops the session, or a Fault occurs: slew to the park pose (`park_pan_deg = 0`, `park_tilt_deg = 0` by default), stop the wheels, flush and close the logs, write the final `session.json`. Wheel outputs are never active outside the coarse turn.

### 6.7 Fixed-panel reference and tracking gain (supports the "gain vs fixed panel" claim)

With one panel there is no physical reference, so the report uses a **virtual fixed panel**:

- While tracking, the panel faces the sun, so its Isc is about the normal-incidence value `I_n`. [Likely] For a more honest `I_n`, divide the measured Isc by the cosine of the model's estimated residual pointing error when that error is known to be more than 1°.
- The virtual fixed panel faces south at tilt **45° from horizontal** (config `fixed_panel_tilt_from_horizontal_deg`, so normal elevation `e_n = 45°`, azimuth `fixed_panel_az_deg = 180°`). `I_fixed(t) = I_n(t) · max(0, cos i_fixed(t))`, with `cos i_fixed = sin e·sin e_n + cos e·cos e_n·cos(A − A_n)`. Use an honest reference orientation, not a flat panel, or the gain claim is a strawman.
- **Validation:** every `fixed_check_interval_s` (default 900 s) the supervisor parks the panel at the fixed orientation for `fixed_check_duration_s` (default 10 s), logs the measured Isc, and compares with the predicted `I_fixed` using `I_n` from the readings just before and just after. These rows go to `fixed_check.csv`. They check both the cosine model and the diffuse-light error.
- **Gain** = `∫ I_n dt / ∫ I_fixed dt` over the session, computed with the trapezoid rule and again with Simpson's rule (`analysis/tracking_gain.py`).
- Fixed checks run only in the Track state and never inside a scan or Hold; schedule them at least `scan_guard_s` away from scans.

---

## 7. Numerical methods catalogue (what must exist, with the public API)

| # | Method | Module | Required API | Stage |
|---|---|---|---|---|
| 1 | Fixed-point and Newton-Raphson for Kepler's equation | `numerics/roots.py` and `solar/position.py` | `fixed_point(g, x0, tol, max_iter) -> RootResult`, `newton(f, df, x0, tol, max_iter) -> RootResult`, `solve_kepler(M_rad, e, method, tol) -> RootResult` | 1 |
| 2 | Linear least squares (servo PWM→angle calibration; offsets from the sun) | `numerics/leastsq.py` | `fit_line(x, y) -> LineFit`, `weighted_mean_offset(values, sigmas, forget) -> OffsetEstimate` | 0, 4 |
| 3 | Golden-section search + parabolic interpolation | `numerics/optimize.py`, `control/acquire.py` | `golden_section_max(f, a, b, tol, max_evals) -> SearchResult`, `parabolic_vertex(x3, f3) -> float` | 3 |
| 4 | Cosine least-squares fit via normal equations + LU, with condition number | `numerics/linalg.py`, `numerics/leastsq.py`, `control/refine.py` | `lu_decompose(A) -> (LU, perm, sign)`, `lu_solve(LU, perm, b)`, `solve(A, b)`, `inverse(A)`, `cond1(A)`, `cond2_spd(A)`, `fit_cosine(deltas_deg, y) -> CosineFit` | 4 |
| 5 | PID with numerical integration (Euler vs trapezoid; optional Simpson) | `numerics/integrate.py`, `control/pid.py`, `control/heading.py` | `class Integrator(mode)`, `class PID(kp, ki, kd, integral_mode, ...)` with `update(error, dt) -> u`, `reset()` | 2 |
| 6 (optional) | Bisection vs false position | `numerics/roots.py` | `bisection(f, a, b, tol, max_iter) -> RootResult`, `false_position(...)` | 1 |
| 7 (optional) | Secant on finite-difference derivative of the scan; QR vs normal equations | `numerics/roots.py`, `numerics/linalg.py` | `secant(f, x0, x1, ...) -> RootResult`, `qr_householder_solve(A, b)` | 4 |

**Result containers.** Every iterative routine returns a dataclass with at least: `value`, `converged` (bool), `iterations`, `history` (list of per-iteration dicts, e.g. `{"k":…, "x":…, "residual":…}`), and `reason`. No routine prints; no routine raises on non-convergence unless the input is invalid (return `converged=False` instead).

**LU details.** Partial (row) pivoting; raise `SingularMatrixError` when a pivot magnitude is below `1e-12 × max|A|`; store the permutation and the sign of the determinant. `solve` = decompose + solve. `inverse` solves against the identity columns. These are exercised on 3×3 systems at runtime and on larger random systems in tests so they are not accidentally special-cased to 3×3.

**Required analysis questions per method** are in section 15.

---
## 8. Hardware abstraction layer (HAL)

All hardware access goes through four small interfaces plus a clock. There are two implementations: `real.py` (Raspberry Pi) and `sim.py` (laptop and tests). Both live in `solar_tracker/hardware/`; `base.py` holds the interfaces and data classes.

### 8.1 Interfaces (`hardware/base.py`)

Use `typing.Protocol` or abstract base classes. Signatures:

```python
@dataclass(frozen=True)
class PanelReading:
    isc_mA: float        # mean over n samples
    isc_std_mA: float    # sample standard deviation
    n: int
    bus_V: float
    overrange: bool      # True if any sample > overrange_mA (default 380)

@dataclass(frozen=True)
class ImuCal:            # BNO055 calibration status, each 0..3
    sys: int; gyro: int; accel: int; mag: int

class Clock(Protocol):
    def now_utc(self) -> datetime: ...          # timezone-aware UTC
    def monotonic(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...

class PanelServos(Protocol):
    limits_deg: tuple[float, float]             # soft limits, e.g. (-85, 85), same for both axes
    def move_to(self, pan_deg: float, tilt_deg: float, settle_s: float = 0.0) -> tuple[float, float]:
        """Clamp to limits, slew-limit, command, wait settle_s. Return the clamped (pan, tilt) actually commanded."""
    def commanded(self) -> tuple[float, float]: ...
    def pulses_us(self) -> tuple[float, float]: ...

class PanelSensor(Protocol):
    def read(self, n_samples: int = 8) -> PanelReading: ...

class Imu(Protocol):
    def heading_deg(self) -> float: ...         # MAGNETIC heading, [0, 360)
    def calibration(self) -> ImuCal: ...

class DriveBase(Protocol):
    def set_turn(self, u: float) -> None: ...   # u in [-1, 1]; +u increases heading (clockwise from above)
    def stop(self) -> None: ...                 # must be idempotent and never raise

@dataclass
class Rig:
    clock: Clock; servos: PanelServos; panel: PanelSensor; imu: Imu; drive: DriveBase
    def close(self) -> None: ...                # stop wheels, park or release servos, release I2C
```

**Rules for implementations:**

- The HAL enforces limits and slew rate. The supervisor and algorithms must not be the only line of defence.
- `move_to` converts angle to pulse with the servo calibration (section 6.0) and **never** writes a pulse outside `[pulse_min_us, pulse_max_us]`.
- Slew limit default 60°/s (`servo.slew_deg_per_s`) implemented as small steps (about 20 ms) so a 90° move does not slam the servo and brown out the Pi.
- `DriveBase.stop()` is called from `finally`, signal handlers and the watchdog. It must work even if the I2C bus has errored (retry once, then raise nothing).

### 8.2 Real backend (`hardware/real.py`)

- Imports `board`, `busio`, `adafruit_pca9685`, `adafruit_motor.servo` (or direct PCA9685 duty-cycle writes), `adafruit_tca9548a`, `adafruit_ina219`, `adafruit_bno055` **inside the constructor**, never at module level, so the module is importable on a laptop.
- **Look first for the lab's code.** The course provides `motor_servo_pwm.py` (a PCA9685 wrapper that creates `PCA9685(i2c_bus, address=0x40)` and exposes motor and servo helpers), `sensor_module.py` (`Sensor_Thread`, which reads the mux sensors in a background thread), `test_motor.py`, `test_sensor.py` and `test_encoder.py`. **They are not in the `Final Project` folder.** If Aron has copied them into `Code/lab_provided/`, reuse the PCA9685 object and the motor-drive conventions from them (do not re-implement the wheel mapping). If they are absent, the real backend must still construct the PCA9685 and sensors directly from the Adafruit libraries as above, and the **wheel drive must raise `ConfigError`** until `drive.*` config values are filled in (section 17.2).
- Servo drive: 50 Hz frequency stays as the lab set it (section 3.2 rule 4). Write the duty cycle as `duty16 = round(pulse_us / 20000 × 65535)` (PCA9685 `duty_cycle` is 16-bit in the Adafruit library) or use `adafruit_motor.servo.Servo` with `set_pulse_width_range(min_pulse, max_pulse)`; either is fine.
- Panel sensor: INA219 at 0x41 on `mux.channel_panel`; apply the 16 V / 400 mA configuration in section 3.3. `read(n)` collects `n` conversions and returns mean and std. Apply the dark offset from config (`panel.zero_offset_mA`, default 0) before returning.
- IMU: BNO055 at 0x28 on `mux.channel_imu`, NDOF mode so the heading is fused. Use the Euler heading (index 0 of `sensor.euler`). Return `None`-safe: if the library returns `None` (it does before the fusion settles) retry up to 3 times. `calibration()` returns `sensor.calibration_status`. Convert to magnetic heading in [0, 360).
- Drive: `set_turn(u)` maps to the left/right PWM channels according to config (`drive.*`). Direction pins vs two PWMs per motor, polarity, and gear ratio are **unknown**; follow the lab's `test_motor.py`. Provide `drive.max_duty` (default 0.5) as a hard cap on turn authority.
- Reuse nothing from `Sensor_Thread` unless the lock (section 8.3) is respected. [Likely] the simplest correct design is to read sensors synchronously from the main thread and ignore `Sensor_Thread`.

### 8.3 Bus lock

One `threading.RLock` (the `BusLock`) wraps every mux channel selection plus the read that follows. If any lab thread also touches the mux, import the same lock into it. This prevents the main loop's INA219 read from landing on the BNO055's channel.

### 8.4 Clocks

`SystemClock` uses `datetime.now(timezone.utc)`, `time.monotonic()` and `time.sleep()`. `SimClock` holds a virtual start time and a virtual elapsed seconds counter; `sleep(s)` advances the counter and calls `rig.step(dt)` in sub-steps of at most 0.05 s so the simulated servo, yaw plant and clouds evolve. A 6-hour simulated session must complete in well under a minute on a laptop (nothing in the supervisor may use real time).

### 8.5 Simulator (`hardware/sim.py`) — a lightweight one, not a full physics model

The earlier plan cut a "full simulator". This spec keeps a small one, for three reasons: the team cannot test outdoors often (two days of good weather), most code must be developed away from the robot, and **the simulator is the only place with ground truth** (known injected offsets), which is what makes the offset-estimation accuracy claim testable. Target size: a few hundred lines.

Model:

| Piece | Behaviour |
|---|---|
| Sun | The production `sun_position` plus a **truth** choice: `solar/reference_noaa.py` (an independent NOAA-series implementation, appendix A.3) gives the "real" sun, so prediction error is part of the test. Configurable site. |
| Robot heading | Starts at a random heading; `heading_true_actual` evolves under the yaw plant. The IMU returns `heading_true_actual − declination` plus `imu_bias_deg` and Gaussian noise. |
| Yaw plant | `yaw_rate = K · deadband(u, d) ` through a first-order lag τ (defaults K = 60°/s at u = 1, d = 0.2, τ = 0.3 s [Guessing]); used for the PID experiments. |
| Servos | True angle = `cal_gain · commanded + cal_zero` (injected calibration error), quantised to the PCA9685 step (4.88 µs), with **backlash** (a dead-zone of `backlash_deg`, default 1.5°, reset on direction reversal) and the slew limit. |
| True offsets | Injected `true_az_offset_deg` and `true_el_offset_deg` (mounting and heading errors) that the learner must discover. |
| Sky | `Isc = I_n(e) · max(0, cos i) · cloud(t) + diffuse + noise`, with `I_n(e) = k_sim · 0.7^(AM^0.678)` (k_sim default 260 mA [Guessing]), diffuse = `diffuse_frac × I_n` (default 0.04 [Guessing]), noise `N(0, σ_noise)` (default 0.4 mA [Guessing]) quantised to 0.1 mA and clipped to [0, 400]. A cloud list `(t_start_s, t_end_s, factor)` scales the whole signal. |
| Lamp mode | A point source at a movable `(az, el)`: `Isc = I_lamp · max(0, cos i) + ambient`. The test or demo script moves the lamp by calling `rig.move_lamp(az, el)`. |
| Determinism | Everything uses one seeded `random.Random`. The same seed must reproduce the same log. |

---

## 9. Supervisor and state machine (`supervisor.py`)

```
PREFLIGHT ─► COARSE_ALIGN ─► ACQUIRE ─► TRACK ◄──► HOLD
                                         │  ▲        (cloud)
                          (refine scan,  │  │
                           fixed check   │  └─ REACQUIRE (a narrow ACQUIRE after HOLD
                           happen inside ▼       or repeated scan failures)
                           TRACK)       PARK ─► DONE
   any state ── exception / watchdog / SIGINT / SIGTERM ──► FAULT ─► park, stop wheels, close logs
```

| State | Entry | Does | Exit |
|---|---|---|---|
| PREFLIGHT | session start | section 6.0 | all checks pass or operator-acknowledged warnings → COARSE_ALIGN (or ACQUIRE with `--skip-turn`) |
| COARSE_ALIGN | after preflight | section 6.2 | success/timeout → ACQUIRE |
| ACQUIRE | after align, after HOLD ended, after two failed scans | section 6.3 | peak found → TRACK; `no_signal` → HOLD (daytime) or PARK (sun below horizon) |
| TRACK | acquire success | every `tick_s` (default 1 s): read Isc, log a `cycle.csv` row, evaluate the cloud flag. Every `predict_update_s` re-point. On schedule: refine scan, fixed-panel check | cloud → HOLD; sun below `min_elevation_deg` → PARK |
| HOLD | cloud flag | keep pointing by prediction; no scans | cloud cleared → TRACK or ACQUIRE |
| PARK | end of session | section 6.6 | → DONE |
| FAULT | any unrecoverable error | stop wheels, park servos, write `events.jsonl` entry with the traceback, close logs | process exits non-zero |

**Scheduling rules inside TRACK** (use `monotonic`): never run a refine scan and a fixed-panel check within `scan_guard_s` (default 120 s) of each other; never during HOLD; a scan or check in progress is aborted (and its servo position restored to the predicted pointing) if the cloud flag trips mid-way.

**Sun-mode start gating:** if the sun's elevation at start is below `min_elevation_deg`, the supervisor waits (sleeping in 30 s steps, logging a heartbeat) up to `wait_for_sun_max_s` (default 1800 s), then parks and exits.

**Signals and watchdog:** register `SIGINT` and `SIGTERM` handlers that set a `stop_requested` flag; the loop checks it every tick and does a clean PARK. A watchdog thread (or timer) stops the wheels and logs a Fault if the main loop has not ticked for `watchdog_s` (default 10 s) while in COARSE_ALIGN (1 s for the turn loop itself). In `finally`: `rig.close()`.

**I2C error policy:** wrap hardware calls with a `retry(n=3, delay=0.05)` helper that catches `OSError` and `RuntimeError`. After retries fail, log an event and raise `HardwareError`. Three `HardwareError`s within 60 s → FAULT.

---

## 10. Configuration (`config/default.toml`)

Use TOML (`tomllib` on Python ≥ 3.11, `tomli` otherwise) loaded into nested dataclasses (`config.py`) with validation and units in names. A site file (`config/site_<name>.toml`) overrides `default.toml`; command-line `--set section.key=value` overrides both. Save the fully resolved config into every session folder. Every value in square brackets is [Guessing] unless marked otherwise.

```toml
[site]                      # where the tests happen
name = "College Station"
lat_deg = 30.6280           # [Likely] Texas A&M campus; CHANGE if testing elsewhere
lon_deg = -96.3344          # east positive
declination_deg = 2.0       # [Likely] magnetic declination, east positive — look up and record the source

[hardware]
backend = "real"            # "real" | "sim"
i2c_bus = 1
pca9685_address = 0x40
mux_address = 0x70
ina219_address = 0x41
imu_address = 0x28
mux_channel_panel = null    # REQUIRED for real hardware
mux_channel_imu = null      # REQUIRED for real hardware
servo_channel_pan = null    # REQUIRED for real hardware
servo_channel_tilt = null   # REQUIRED for real hardware
pca9685_expected_hz = 50
overrange_mA = 380

[servo]
pan_sign = 1                # verify at first power-up
tilt_sign = 1               # verify at first power-up
limit_deg = 85
slew_deg_per_s = 60
settle_s = 0.6
pulse_min_us = 500
pulse_max_us = 2500
center_us = 1500
deg_per_us = 0.09
calibration_file = "config/servo_cal.json"   # generated; used if it exists

[drive]                     # wheels, coarse turn only. All REQUIRED for the real turn.
left_channel = null
right_channel = null
direction_scheme = null     # e.g. "pwm_per_motor" | "pwm_plus_dir_pin" — copy from lab test_motor.py
turn_sign = 1
max_duty = 0.5
min_turn_duty = 0.25

[panel]
n_samples_default = 8
zero_offset_mA = 0.0
min_signal_mA = 5.0
k_clear_mA = 0.0            # 0 = estimate from the first clear-sky acquire

[pointing]
az_offset_init_deg = 0.0
el_offset_init_deg = 0.0
min_elevation_deg = 10.0
park_pan_deg = 0.0
park_tilt_deg = 0.0
max_bootstrap_offset_deg = 40.0

[align]                     # coarse turn
target_heading_true_deg = 180.0
tol_deg = 2.0
hold_s = 1.0
max_turn_s = 40.0
loop_hz = 20
kp = 0.02                   # per degree of error; tune on the robot/sim
ki = 0.002
kd = 0.004
d_filter_tau_s = 0.15
integral_mode = "trapezoid" # "euler" | "trapezoid" | "simpson"
imu_mag_cal_min = 3

[acquire]
n_coarse = 9
first_half_width_deg = 40.0
later_half_width_deg = 15.0
tol_deg = 1.5
max_evals = 24
n_passes = 2
samples_per_point = 8
lamp_half_width_deg = 60.0
lamp_reacquire_drop_frac = 0.10

[track]
tick_s = 1.0
predict_update_s = 60
scan_interval_s = 720
scan_guard_s = 120
limit_replan_s = 300
fixed_check_interval_s = 900
fixed_check_duration_s = 10
fixed_panel_az_deg = 180.0
fixed_panel_tilt_from_horizontal_deg = 45.0

[refine]
spread_deg = 15.0           # allowed 10..20
n_points = 7                # allowed 5..7
scan_order = "shuffled"     # "sweep" | "shuffled"
samples_per_point = 8
max_scan_s = 30
max_rms_frac = 0.03
max_drift_frac = 0.03
max_cond = 1.0e4
max_sigma_deg = 3.0
offset_forget = 1.0

[cloud]
hold_enter_ratio = 0.70
hold_exit_ratio = 0.80
hold_enter_samples = 5
hold_exit_samples = 10
reacquire_after_hold_s = 300
assume_clear_start = true

[runtime]
watchdog_s = 10
wait_for_sun_max_s = 1800
log_dir = "logs"
```

---

## 11. Logging and data formats

Each run creates `logs/YYYYMMDD_HHMMSSZ_<command>/`. Every CSV row is written, flushed and `os.fsync`'d immediately (the Pi may lose power; a lost row is a lost data point). Files:

| File | Columns (header row required) |
|---|---|
| `session.json` | start/end UTC, command, argv, git commit (if available), Python and library versions, resolved config, I2C scan result, PCA9685 frequency, NTP-sync status, IMU calibration at start, `k_clear_mA`, final offsets, exit reason |
| `cycle.csv` (every `tick_s`) | `t_utc, t_mono_s, state, sun_az_deg, sun_el_deg, heading_true_deg, az_offset_deg, el_offset_deg, pan_cmd_deg, tilt_cmd_deg, pan_pulse_us, tilt_pulse_us, isc_mA, isc_std_mA, bus_V, clear_isc_mA, cloud_ratio, imu_cal_sys, imu_cal_mag, flags` (`flags` is a `|`-joined list such as `LIMIT_PAN|CLOUD|OVERRANGE`) |
| `scan.csv` (raw points) | `scan_id, t_utc, axis, k, role, cmd_deg, delta_deg, isc_mA, isc_std_mA, n` (`role` is `point`, `center_start`, `center_end`) |
| `scan_fit.csv` (one row per scan per axis) | `scan_id, t_utc, axis, spread_deg, n_points, a, b, c, delta_star_deg, amp_mA, rms_resid_mA, cond2_MtM, sigma_delta_deg, accepted, reject_reason, offset_used_deg, offset_total_deg, offset_est_after_deg, offset_est_se_deg` |
| `acquire.csv` | `acq_id, t_utc, axis, phase, iter, x_deg, f_mA, interval_width_deg, x_golden_deg, x_parabolic_deg, x_best_deg` (`phase` is `coarse`, `golden`, `parabolic`, `result`) |
| `turn.csv` (20 Hz) | `t_s, heading_true_deg, target_deg, err_deg, u, p_term, i_term, d_term, integral_mode, left_cmd, right_cmd` |
| `fixed_check.csv` | `t_utc, isc_fixed_meas_mA, isc_in_before_mA, isc_in_after_mA, isc_fixed_pred_mA, cos_i_fixed` |
| `static.csv` | `t_utc, isc_mA, bus_V` |
| `servo_cal.csv` | `servo, direction, pulse_us, measured_deg` |
| `events.jsonl` | one JSON object per line: `{"t_utc":…, "level":…, "event":…, …}`: state changes, rejected scans, limit hits, Hold enter/exit, hardware errors, faults with tracebacks |

Also keep the standard `logging` output on the console and in `run.log`.

---

## 12. Command line (`python -m solar_tracker <command>`)

| Command | Purpose | Key options |
|---|---|---|
| `preflight` | Section 6.0 checks only | `--hardware real\|sim` |
| `calibrate-servo` | Interactive servo calibration; writes `servo_cal.csv`, then fit with `analysis/fit_servo_cal.py` | `--servo pan\|tilt` |
| `static-log` | Hold a fixed pose and log Isc at 10 Hz for N minutes (noise model) | `--minutes 10`, `--pan`, `--tilt` |
| `coarse-turn` | Section 6.2 on its own | `--robot-on-ground`, `--bench`, `--integral euler\|trapezoid\|simpson`, `--target` |
| `acquire` | Section 6.3 only, sun or lamp | `--mode sun\|lamp` |
| `lamp` | Indoor demo: acquire then monitor/re-acquire/refine on a lamp moved by hand | `--seconds` |
| `track` | The full session (section 9) | `--mode sun`, `--skip-turn`, `--ack-clock`, `--k-mA`, `--duration-min`, `--spread` |
| `park` | Move the servos to the park pose and stop | |
| `analyze` | Run analysis scripts on a log folder (section 15) | `<log_dir>` |
| `sim-day` | Simulated full session: injects offsets, clouds, noise | `--seed`, `--true-az-offset`, `--true-el-offset`, `--clouds`, `--hours` |

Global options: `--config PATH`, `--set key=value`, `--hardware real|sim`, `--log-dir`, `-v`. `Ctrl-C` always parks cleanly. Commands must work inside `tmux` over SSH.

---

## 13. Repository layout (under `Final Project/Code/`)

```
Code/
  README.md                   setup on laptop and Pi, run procedure, decisions, method-to-code map
  pyproject.toml              package metadata; optional extras: [pi] and [analysis] and [dev]
  requirements-pi.txt         Pi runtime only (see appendix C)
  requirements-dev.txt        pytest, numpy, matplotlib (laptop)
  config/
    default.toml
    site_example.toml
    servo_cal.json            generated by the calibration fit (not committed with defaults)
  lab_provided/               (Aron copies the course's .py files here; read-only reference)
  solar_tracker/
    __init__.py  __main__.py  cli.py  config.py  clock.py
    geometry.py               wrap180/360, angdiff, sun vector, incidence_cos, pointing <-> pan/tilt
    supervisor.py
    logging_.py
    numerics/
      roots.py  linalg.py  leastsq.py  optimize.py  integrate.py
    solar/
      position.py             Kepler chain, sun_position, sunrise_sunset
      clearsky.py             clear_isc_mA(e, k), cloud ratio, k estimation
      reference_noaa.py       independent NOAA-series sun position (reference only; used by sim and tests)
    control/
      pid.py  heading.py      PID and the coarse-turn loop
      acquire.py  refine.py   golden+parabolic; scan + cosine fit + quality gates
      offsets.py              running weighted-mean offset estimator
    hardware/
      base.py  real.py  sim.py
  analysis/
    fit_servo_cal.py  kepler_convergence.py  sunrise_roots.py  golden_convergence.py
    cosine_fit_study.py  offset_convergence.py  pid_study.py  tracking_gain.py
    noise_model.py  prediction_vs_measured.py  plot_session.py  method_code_map.py
  tests/
    test_geometry.py  test_roots.py  test_linalg.py  test_leastsq.py  test_optimize.py
    test_integrate_pid.py  test_solar_position.py  test_acquire.py  test_refine.py
    test_offsets.py  test_supervisor_sim.py  test_logging.py  test_config.py
  logs/                       created at run time; ignored by git
  .gitignore
```

If a file is not needed yet, create it when its phase starts (section 16). Do not create empty placeholder modules.

---

## 14. Testing, documentation and the method-to-code map

### 14.1 Unit tests (pytest, no hardware, no network)

| Test file | What must be shown |
|---|---|
| `test_geometry` | `wrap180/360` at edges; `angdiff(1, 359) == 2`; `angdiff(359, 1) == −2`; round trip `pointing_to_servo ∘ servo_to_pointing` for random inputs; `incidence_cos` = 1 when the normal points at the sun, 0 at 90°, matches an explicit vector dot product |
| `test_roots` | Newton, fixed-point, bisection, false position and secant on known functions (`cos x − x`, `x² − 2`); iteration counts recorded; non-convergence returns `converged=False` instead of raising |
| `test_linalg` | LU with pivoting on random 3×3 and 8×8 systems vs `numpy.linalg.solve` (relative error < 1e-10); a matrix needing pivoting (zero in the (0,0) place); a singular matrix raises `SingularMatrixError`; `inverse(A)·A ≈ I`; `cond2_spd` vs `numpy.linalg.cond` within 1% on 3×3 SPD matrices |
| `test_leastsq` | `fit_line` recovers slope and intercept from noisy synthetic data; `fit_cosine` recovers `(a, b, c)` and `δ*` within `3σ` from synthetic data with known noise, K = 5, 6, 7 and S = 5°…20°; the covariance-based `σ_δ*` matches a 2000-trial Monte Carlo scatter within 20%; `fit_cosine` result equals `numpy.linalg.lstsq` on the same data within 1e-8 |
| `test_optimize` | Golden-section finds the maximum of a unimodal function; the interval shrinks by about 0.618 per iteration; exactly one new evaluation per iteration; a parabola is recovered exactly by one `parabolic_vertex` step; behaviour with noise |
| `test_integrate_pid` | Euler and trapezoid integrators on `∫ sin` and `∫ e^t` with known errors (trapezoid second order, Euler first order); PID step response on a first-order simulated plant; anti-windup under saturation; heading wrap (359° → 1°) |
| `test_solar_position` | Compare with the NOAA-series reference (`reference_noaa.py`) every 10 minutes across Nov 1–30 at the site: max error < **0.1°** in azimuth and elevation (hard requirement 0.5°). Check the anchor table in appendix A. Check solar noon azimuth is within 0.5° of 180° at the site's solar-noon time; the elevation at noon equals `90° − lat + decl`; the sun is below the horizon at local midnight; both Kepler solvers agree to 1e-9 |
| `test_acquire` | On a synthetic Isc(angle) curve (cosine bump, noise 0.4 mA): finds the true peak within `2×tol` in 99% of 500 seeded trials; reports `edge_peak` when the peak is outside the window; `no_signal` when all values are below the threshold |
| `test_refine` | Gates reject: too few points, high drift between `center_start`/`center_end`, peak outside the window, `cond` too high, low amplitude; accepts clean data and returns the right `δ*` |
| `test_offsets` | The weighted mean converges to the injected constant as scans accumulate; one outlier is down-weighted; forgetting factor behaves as documented |
| `test_supervisor_sim` | See 14.2 |
| `test_config` / `test_logging` | Missing-required-hardware-value raises `ConfigError` on the real backend and not on the sim; logs flush every row and the CSV headers match section 11 |

### 14.2 Closed-loop simulation tests (the integration tests that matter)

Run through `SimClock`; each completes in seconds.

1. **Clear day, known offsets.** Inject `true_az_offset = +7°`, `true_el_offset = −3°`, servo calibration gain error 2%, backlash 1.5°, noise 0.4 mA. Run `sim-day` for 6 simulated hours (15:00–21:00 UTC on a November date). Assert: the learned `az_offset` and `el_offset` end within **1°** of the truth; tracking pointing error (from the simulator's ground truth) has RMS < 2° after the first scan; no wheel command is issued after COARSE_ALIGN; every scan row is logged.
2. **Clouds.** Add a 20-minute cloud with factor 0.3 in the middle. Assert HOLD is entered and left, no scan is accepted during it, and the offsets are not corrupted (change < 1° across the cloud).
3. **Bad start.** Heading error of 25° at start: assert the first acquire's wide window finds the peak and `bootstrap` sets the offsets; with a 60° bootstrap error assert the supervisor goes to FAULT with the documented message.
4. **Lamp mode.** Lamp at a random `(az, el)`; assert acquire pointing error < 3°; move the lamp by 25° mid-run and assert re-acquire follows within 60 simulated seconds.
5. **Coarse turn.** PID turn from random headings (including across the 0°/360° boundary) reaches `tol_deg` within `max_turn_s` with Euler and with trapezoid integration.
6. **Faults.** Raise `OSError` from the simulated INA219 three times in 60 s → FAULT, wheels stopped, logs closed. A `SIGINT` mid-session → PARK and exit code 0.
7. **Determinism.** The same seed gives byte-identical `cycle.csv`.

### 14.3 Documentation and the method-to-code map

- Every module has a top docstring stating purpose and units. Every public function has a docstring with arguments, units and a one-line statement of the numerical idea.
- Tag graded functions with `NM-METHOD: <name> | STAGE: <n>` in the docstring. `analysis/method_code_map.py` scans the package and writes `docs/method_code_map.md`: a table of method → file → function → line numbers → test file → analysis script. The report needs exactly this ("show where the methods are in the code").
- `README.md` (written last, but the structure exists from phase 1): install on laptop; install on Pi; first power-up checklist (section 17.1); how to run each command; the log folder layout; how to regenerate every figure; the **Decisions** list for every place this spec was ambiguous; known limitations.

---

## 15. Analysis scripts and report figures

Each script reads logs (or runs its own sim/synthetic study), writes PNG (and CSV where tabular) into `analysis_out/<name>/`, prints a short numeric summary, and has a `--seed` option so it is reproducible. Use matplotlib (laptop only). Label axes with units. These map straight onto the course's "convergence, stability, accuracy" requirement.

| Script | Method | Figures / tables (file names) | Question answered |
|---|---|---|---|
| `kepler_convergence.py` | #1 | `kepler_error_vs_iter.png` (semilog, fixed-point vs Newton at e = 0.0167, 0.5, 0.9, several M), `kepler_iter_table.csv` | **Convergence:** linear vs quadratic; how many iterations at Earth's e; behaviour at high e |
| `prediction_vs_measured.py` | #1 | `sun_model_vs_noaa.png` (az/el error over the test days), `pointing_error_vs_time.png` (learned vs predicted offset), `solar_error_stats.csv` | **Accuracy** of the prediction vs the NOAA reference (<0.5° target) and vs the measured power peak on hardware |
| `sunrise_roots.py` (Tier 2) | #6 | `sunrise_iterations.png`, table | Bisection vs false position: iterations to the same tolerance |
| `fit_servo_cal.py` | #2 | `servo_cal_fit_<servo>.png` (up and down data, fits, residuals), `servo_cal_summary.csv` (slope, intercept, RMS, **hysteresis**) | **Accuracy** of the PWM→angle map; backlash estimate |
| `golden_convergence.py` | #3 | `golden_interval_vs_iter.png` (width vs iteration with the 0.618ᵏ line), `golden_error_vs_noise.png` (peak error vs noise level, golden only vs golden+parabolic), `acquire_hw_run.png` from a real `acquire.csv` | **Convergence** rate; **stability** under noise; value of the parabolic step |
| `cosine_fit_study.py` | #4 | `cond_vs_spread.png` (cond₂(MᵀM) for S = 2, 5, 10, 15, 20° and K = 5, 6, 7), `theta_scatter_vs_spread.png` (Monte Carlo scatter in δ* vs S with theory σ from the covariance, hardware scans overlaid), `fit_examples.png` | **Stability** (conditioning vs spread); **accuracy** (scatter of δ*); why the operating spread is ±10–20° |
| `offset_convergence.py` | #2/#4 | `offset_estimate_vs_scans.png` (with truth in sim), `offset_error_stats.csv` | Convergence of the running least-squares offset estimate; accuracy against injected truth |
| `pid_study.py` | #5 | `pid_step_euler_vs_trapezoid.png`, `pid_metrics.csv` (rise, overshoot, settling, steady-state error), `pid_gain_sweep.png` (stability map over Kp/Ki), `pid_hw_runs.png` | **Stability** vs gains; effect of the integration scheme; sim vs hardware |
| `tracking_gain.py` | trapezoid/Simpson | `isc_tracked_vs_fixed.png`, `gain_summary.csv` (trapezoid and Simpson, difference between them), `fixed_check_validation.png` | System-level result: gain over a fixed panel; model validation |
| `noise_model.py` | — | `static_noise_hist.png`, `noise_stats.csv` | The measured noise that sets the simulator parameters |
| `plot_session.py` | — | `session_overview.png` (elevation, commands, Isc, state timeline, cloud ratio) | Demo and report overview figure |
| `method_code_map.py` | — | `docs/method_code_map.md` | "Where in the code" |

---

## 16. Build order (follow it; each phase ends with a green test run)

The team has about 7 days from today (Nov 16) to the ~Nov 24 deliverables, and outdoor sessions depend on weather. Phases 1–3 need no hardware; do them first and fast.

| Phase | Build | Acceptance gate |
|---|---|---|
| **0. Skeleton** | `pyproject.toml`, package, `config.py`, `clock.py`, `geometry.py`, `logging_.py`, `.gitignore`, pytest runs | `pytest` passes on an empty-ish suite on Windows and Linux |
| **1. Numerics (Tier 1)** | `numerics/*`, `solar/position.py`, `solar/reference_noaa.py`, `solar/clearsky.py`, tests for all of them | all section 14.1 numerics tests pass; solar error < 0.1° vs the NOAA reference |
| **2. Control and algorithms** | `control/pid.py`, `heading.py`, `acquire.py`, `refine.py`, `offsets.py` | `test_acquire`, `test_refine`, `test_offsets`, PID tests pass |
| **3. Simulator and supervisor** | `hardware/base.py`, `hardware/sim.py`, `supervisor.py`, `cli.py` (`sim-day`, `lamp`, `coarse-turn --bench`) | all section 14.2 scenarios pass; `sim-day` learns injected offsets to < 1° |
| **4. Real backend** | `hardware/real.py`, `preflight`, `calibrate-servo`, `static-log`, `park` | on the Pi: preflight passes; servos move to commanded angles; INA219 reads match a multimeter within a few percent; **no wheel command until `drive.*` is configured** |
| **5. Bench and lamp on hardware** | `lamp`, `acquire`, a full `track` with the panel under a lamp; `coarse-turn --robot-on-ground` | lamp acquire finds the lamp within a few degrees; full cycle logs correctly |
| **6. Analysis** | the scripts in section 15, `method_code_map.py`, README | every figure in section 15 regenerates from the logs and sim with one command each |
| **7. Tier 2 (only if time)** | sunrise/sunset roots, secant comparison, QR vs normal equations, parameter uncertainty weighting extras | not required for the demo |

**Priority if time runs out:** Tier 1 numerics + simulator + supervisor + analysis figures (phases 0–3, 6) are worth more to the grade than polish on the real backend. Phases 4–5 are what make the demo real. Do not skip the simulator: it is how the code is verified before the weather allows an outdoor test.

**Parallelisation:** after phase 0, the five numerics modules (`roots`, `linalg`+`leastsq`, `optimize`, `integrate`+`pid`, `solar`) are independent and can be built and tested in parallel by separate team members; everything from phase 2 depends on them.

---

## 17. Unknowns, risks and fail-safe rules

### 17.1 First power-up checklist (written into the README)

1. Robot on a stand, wheels off the ground. Ethernet to the laptop; `source ~/env/bin/activate`; start `tmux`.
2. `python -m solar_tracker preflight`. Fix anything flagged.
3. Move each servo to −20°, 0°, +20° with `calibrate-servo` and confirm the direction: if positive pan does not turn the normal clockwise from above, set `pan_sign = −1`; if positive tilt does not lift the normal upward, set `tilt_sign = −1`.
4. Run the servo calibration (section 6.0) and the fit.
5. Confirm the INA219 current sign and size with the panel under a lamp and a multimeter.
6. Only then fill in `drive.*` and test the coarse turn with the robot off the ground and `--bench`, then on the ground.

### 17.2 Fail-safe rules the code must implement

- A required hardware config value that is `None` makes the real backend raise `ConfigError` with the exact key name. **Never guess a channel.** [Likely] sending a servo pulse to a wheel-driver channel can spin a wheel; sending motor PWM to a servo can damage it.
- Wheels are driven only inside COARSE_ALIGN and only with `--robot-on-ground`/`--bench` consent; `stop()` runs in every exit path.
- Servo commands are clamped to ±85° (HAL level) and slew-limited. Never write a pulse outside the calibrated range.
- A corrupted or low-quality scan never moves the offsets. A scan rejected twice in a row triggers re-acquire, not an arbitrary jump.
- If any estimated offset exceeds `max_bootstrap_offset_deg`, go to FAULT with a message, not a silent clamp.
- Never run the sun mode with an unsynchronised clock unless `--ack-clock`.

### 17.3 Known unknowns

| Unknown | Where it matters | Default / action |
|---|---|---|
| Servo channels on the HAT | real backend | `None` → refuse; read from the wiring |
| Mux channel for INA219 and BNO055 | real backend | `None` → refuse; `i2cdetect` after setting each |
| Wheel-driver wiring (three green boards), PWM channels, direction scheme, gear ratio | coarse turn | Follow the lab `test_motor.py`; ask Aron/TA; keep `--skip-turn` working |
| The lab's `motor_servo_pwm.py` and `sensor_module.py` APIs | real backend | Not in the folder; ask Aron to copy them to `Code/lab_provided/`; do not guess their function names |
| Pi model, Python version, whether `numpy`, `adafruit-circuitpython-ina219` and `tomli` are installed in `~/env`, whether the Pi has internet | deployment | Core runtime must need only the standard library plus the Adafruit packages; [Guessing] installing the INA219 library needs internet — use the lab Wi-Fi or a phone hotspot, or `pip download` on the laptop |
| Test site coordinates and magnetic declination | sun model, heading | Config; College Station placeholder |
| Pan-zero direction relative to the IMU's reference axis | initial `az_offset` | `0` by default; absorbed by acquire bootstrap |
| `pan_sign`, `tilt_sign` | pointing | Verify at first power-up (17.1) |
| SG90 true range, deadband, backlash | calibration, sim | Measured by servo calibration |
| Clear-sky constants and thresholds | cloud flag | [Guessing]; tune on the first outdoor session |
| Whether the robot may be run outdoors and where | demo | Team has already planned outdoor sessions |
| Due dates and report format | planning | [Guessing] ~Nov 24 |

### 17.4 Risks to design around

- [Likely] **Azimuth is the weak axis.** Heading from a magnetometer near motors and servos can be off by several degrees. That is the reason for learning the offset from the sun. Do not remove it.
- **Scans are corrupted by changing light.** Short scans, drift gate, `center_start`/`center_end`, shuffled order.
- **Servo hysteresis (plastic gears).** Approach each scan point from the same direction when `scan_order = sweep`; log up/down; the calibration measures hysteresis.
- **Only about two outdoor sessions.** Log everything; the analysis must work from logs alone.
- **Servo brown-outs.** Slew limit, no simultaneous moves of both axes at full speed, and a bulk capacitor on the servo rail are in the BOM. If the Pi resets when a servo moves, stop and report; do not hide it with retries.
- **Panel shading** by the robot body at low sun: log `sun_el_deg`; flag samples under 25° in the analysis as potentially shaded.

---

## 18. Out of scope (do not build)

Wheel-driven azimuth tracking; a quadrant photodiode or any extra sensor; a second panel or load resistor; a GUI, web dashboard or ROS; machine learning; ODE servo models; joint two-axis quadratic fits; battery management; a full physics or rendering simulator; encoder odometry; automatic internet time setup; cloud detection with the APDS9960 (an optional manual cross-check only if Aron asks).

---

## Appendix A — Validated reference data and prototype code

### A.1 Sun-position anchors

Site 30.6280° N, −96.3344° E (College Station [Likely] campus), date **2026-11-16**, UTC times. Computed with the NOAA general solar position equations (the series in the spreadsheet formulas) implemented independently in Python during this spec's preparation; the Kepler-chain implementation of section 6.1 agreed within 0.02° at every row. They have **not** been checked against the NOAA web calculator [Likely accurate]; check once at the start. Use a tolerance of 0.1° in tests.

| UTC | Local (CST) | Azimuth ° | Elevation ° | Declination ° |
|---|---|---|---|---|
| 15:00 | 09:00 | 130.84 | 22.67 | −18.84 |
| 16:00 | 10:00 | 143.37 | 31.47 | −18.85 |
| 17:00 | 11:00 | 158.88 | 37.72 | −18.86 |
| 18:10 | 12:10 | 179.96 | 40.50 | −18.87 |
| 19:00 | 13:00 | 195.25 | 39.06 | −18.88 |
| 20:00 | 14:00 | 211.71 | 33.88 | −18.89 |
| 21:00 | 15:00 | 225.20 | 25.82 | −18.90 |

Consequences for the design: in the 9:00–15:00 CST window the azimuth sweeps about 94° (131° → 225°) and the elevation stays between 22° and 41°. With the robot facing south (pan zero at 180°), the required pan is about −49° to +45°, well inside ±85°, and tilt (from vertical) equals the elevation, 22–41°.

### A.2 Kepler chain prototype (validated; use as a starting point, rewrite with the required result containers)

```python
import math, datetime as dt

def wrap360(x): return x % 360.0

def jd_from_utc(t):                       # Gregorian UTC datetime -> Julian date
    y, m = t.year, t.month
    d = t.day + (t.hour + (t.minute + t.second / 60) / 60) / 24
    if m <= 2: y -= 1; m += 12
    A = y // 100; B = 2 - A + A // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5

def kepler_newton(M, e, tol=1e-12):
    E = M if e < 0.8 else math.pi
    for k in range(50):
        E2 = E - (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        if abs(E2 - E) < tol: return E2, k + 1
        E = E2
    return E, 50

def kepler_fixed_point(M, e, tol=1e-12):
    E = M
    for k in range(200):
        E2 = M + e * math.sin(E)
        if abs(E2 - E) < tol: return E2, k + 1
        E = E2
    return E, 200

def sun_azel(t, lat, lon, solver=kepler_newton):
    n = jd_from_utc(t) - 2451545.0
    M = math.radians(wrap360(357.5291 + 0.98560028 * n))
    e = 0.016709 - 1.151e-9 * n
    E, _ = solver(M, e)
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2), math.sqrt(1 - e) * math.cos(E / 2))
    lam = nu + math.radians(282.9373 + 4.70684e-5 * n)
    eps = math.radians(23.4393 - 3.563e-7 * n)
    dec = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = math.radians(wrap360(280.46061837 + 360.98564736629 * n))
    H = gmst + math.radians(lon) - ra
    phi = math.radians(lat)
    el = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H))
    az = math.atan2(-math.cos(dec) * math.sin(H),
                    math.sin(dec) * math.cos(phi) - math.cos(dec) * math.sin(phi) * math.cos(H))
    return wrap360(math.degrees(az)), math.degrees(el), math.degrees(dec)
```

Note: `t` must be a naive UTC datetime here or a timezone-aware UTC one (the arithmetic uses only the calendar fields). Production code must reject non-UTC input.

### A.3 NOAA-series reference (for `solar/reference_noaa.py` and tests only; not a graded method)

```python
def noaa_azel(t, lat, lon):               # t: UTC datetime. Returns az, el, decl in degrees.
    jc = (jd_from_utc(t) - 2451545.0) / 36525
    L0 = wrap360(280.46646 + jc * (36000.76983 + jc * 0.0003032))
    M = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    Mr = math.radians(M)
    C = (math.sin(Mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
         + math.sin(2 * Mr) * (0.019993 - 0.000101 * jc) + math.sin(3 * Mr) * 0.000289)
    omega = 125.04 - 1934.136 * jc
    app = L0 + C - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    dec = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app))))
    y = math.tan(math.radians(eps / 2)) ** 2
    L0r = math.radians(L0)
    eot = 4 * math.degrees(y * math.sin(2 * L0r) - 2 * e * math.sin(Mr)
          + 4 * e * y * math.sin(Mr) * math.cos(2 * L0r) - 0.5 * y * y * math.sin(4 * L0r)
          - 1.25 * e * e * math.sin(2 * Mr))
    minutes = t.hour * 60 + t.minute + t.second / 60
    tst = (minutes + eot + 4 * lon) % 1440
    ha = tst / 4 - 180
    phi, d, h = map(math.radians, (lat, dec, ha))
    cz = math.sin(phi) * math.sin(d) + math.cos(phi) * math.cos(d) * math.cos(h)
    z = math.degrees(math.acos(cz))
    az = math.degrees(math.acos((math.sin(phi) * cz - math.sin(d)) / (math.cos(phi) * math.sin(math.radians(z)))))
    az = (az + 180) % 360 if ha > 0 else (540 - az) % 360
    return az, 90 - z, dec
```

---

## Appendix B — Pointing mathematics

Let the sun be `(A_s, e_s)` and the panel normal `(A_n, e_n)`.

**Incidence cosine:** `cos i = sin e_s · sin e_n + cos e_s · cos e_n · cos(A_s − A_n)`. Model Isc as `I_n · max(0, cos i) + diffuse`.

**Sun → servo commands** (ideal normal = sun direction):

```
pan_deg  = pan_sign  · angdiff(A_s, heading_true + az_offset)
tilt_deg = tilt_sign · (e_s − el_offset)
```

then clamp to the soft limits and set `LIMIT_PAN` / `LIMIT_TILT` if clamped.

**Servo commands → normal:**

```
A_n = wrap360(heading_true + az_offset + pan_sign  · pan_deg)
e_n = el_offset + tilt_sign · tilt_deg
```

**Why the scans have the cosine form.** With the normal near the sun, scanning the pan angle at fixed tilt gives `cos i = cos e_s · cos e_n · cos(Δpan) + sin e_s · sin e_n`, which is exactly `A·cos(Δpan) + C`. Scanning tilt at fixed pan gives `α·cos(t) + β·sin(t)` plus a small diffuse offset. Both match the model `a·cos δ + b·sin δ + c` with `c` free. The cosine form breaks down when `cos i` approaches 0 (it is clipped at 0) and for ETFE encapsulation at steep angles above about 60° [Likely], so scan windows stay within ±20°.

**Heading offset interpretation.** The pan-axis offset `az_offset` combines: the BNO055's magnetic error and declination error, the angle between the IMU reference axis and the panel's pan-zero direction, the pan servo's zero error, and clock error (0.25° per minute). Only the sum is observable. The tilt-axis `el_offset` combines the tilt servo's zero error and any mounting tilt of the base.

---

## Appendix C — Libraries and installation

Pi runtime [Likely names; verify with `pip index versions` or the Adafruit docs]: `adafruit-blinka`, `adafruit-circuitpython-pca9685`, `adafruit-circuitpython-motor` (if used), `adafruit-circuitpython-tca9548a`, `adafruit-circuitpython-ina219`, `adafruit-circuitpython-bno055`. The lab's `~/env` already has the PCA9685, mux, BNO055, VL53L4CD, APDS9960 and `gpiozero` packages; **the INA219 package may be missing**. `tomli` only if Python < 3.11. No `numpy` is needed on the Pi.

Laptop (analysis, tests): `numpy`, `matplotlib`, `pytest`, `pyyaml` not required. Optional reference: `pvlib` or `astral` for an additional solar check (not installed in the build environment where this spec was written, so it is optional).

Deployment: copy `Code/` to `/home/pi/mxet345_project` (VS Code Remote-SSH drag-and-drop, or `git` if Aron uses it). The course requires backing files up after every lab: copy `logs/` and `analysis_out/` off the Pi after every session.

---

## Appendix D — Source documents (in `Final Project/`)

`MXET 345 Final Project Overview.md` (course requirements, robot platform, gotchas) · `MXET 345_Final Project_V1.md` (official requirements) · `Lab Ex - Robot Introduction.md` and `Lab Ex - PreLab.md` · `mxet345-solar-tracker-plan.md` (design and methods, rev 2) · `mxet345-solar-tracker-build-plan.md` (schedule and procedures) · `mxet345-solar-tracker-breakdown.md` (subsystems and team split) · `mxet345-solar-tracker-BOM.md/.xlsx` (parts) · `Hardware List & Assembly Guide.pdf` (Nov 10; mechanical truth) · `CAD/` (STEP files; not needed for the software).
