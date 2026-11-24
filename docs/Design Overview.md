# MXET 345 Solar Tracker: Design Overview

**Updated:** Nov 17, 2026. Matches the code in `Code/`, `Hardware List & Assembly Guide.pdf` (re-exported Nov 17) and `CAD/Solar Tracker Assembly.step` (rebuilt Nov 17).
**Replaces:** the plan, build plan, breakdown and software-specification files. The originals are in git history (commit `30ef60b`). The "Decisions" list in `Code/docs/decisions.md` records where the code departs from that specification.
**Companion files:** `Hardware & BOM.md` (parts, wiring, I2C) · `Course Requirements.md` (grading, deliverables, lab robot) · `Code/README.md` (install, commands, logs, figures) · `Code/docs/method_code_map.md` (method to code).
**Confidence tags:** [Certain] / [Likely] / [Guessing]. Untagged text comes from the team's documents or the code.

## 1. What it is

A 6 V solar panel sits on a two-servo pan-tilt mount bolted to the MXET 345 lab robot. The Raspberry Pi:
1. predicts the sun's position from the clock (Kepler's equation);
2. points the panel there;
3. finds the exact power peak from the panel's short-circuit current (Isc);
4. every ~12 minutes scans around the prediction and fits a cosine to the Isc readings. The fit exposes the rig's built-in pointing errors (heading, mounting, servo calibration), and the software learns and removes them.

The wheels run once per session: a PID turns the robot to face roughly south. The robot does not move while it tracks.

**Why the numerics are essential.** [Certain] Near the peak the cosine response is flat. A pointing error of 2° costs 0.06% of the current, 5° costs 0.4%, 10° costs 1.5%, 20° costs 6%. So the tracker is **not** about harvesting much more energy than a well-aimed fixed panel. Its job is to **measure and remove the system's built-in angular errors** with least-squares fits to real data. Without the fit, the prediction points wherever those errors push it. Do not replace the fit with "move toward the higher of two readings".

## 2. Status

- All software runs and is tested against the built-in simulator on a laptop (test suite and counts: `Code/README.md`).
- `hardware/real.py` has **not been run on the robot**. Follow the step-by-step guide in `Code/README.md` (steps 5 to 12).
- No hardware logs are in this folder. The figures in `Code/analysis_out/` come from the simulator and synthetic data.
- The wheels are driven as FWD/RV channel pairs through the lab's `PWM_Motor` (`Code/lab/motor_servo_pwm.py`): `drive.left_motor_channels = [0, 1]`, `drive.right_motor_channels = [2, 3]` in `Code/config/robot.toml`, from `Code/lab/test_motor.py`. Which pair is left is verified at the bench turn; `--skip-turn` always works.

## 3. Physical system (from the Nov 10 assembly guide)

- **Pan axis:** vertical, through the lazy-susan bearing centre. An SG90 under the base plate drives a 4-arm horn captured in the turntable. Range ±90°.
- **Tilt axis:** horizontal, 75 mm above the turntable top. An SG90 in the +X upright drives a single-arm horn in the panel holder. The −X side pivots on a 3×8×4 mm ball bearing. Range ±90° from vertical.
- **Centre:** both servos are centred at 90° = 1500 µs during assembly. At tilt 0 the panel stands **vertical**.
- **Pan zero:** the turntable's long dovetail arms run across the robot rails. Seen from the front (the cable-ear end of the base plate), the panel faces the viewer at pan 0, tilt 0.
- **Limits:** software limits at ±85° on both axes so neither servo stalls on its end stop.
- **Offsets:** horn indexing can leave up to about ±8° of zero error. Measure it and trim it in software (servo calibration, section 5.0).
- **Mounting:** the base plate bolts to the robot's frame rails. Nothing is removed from the robot.
- **Panel:** Voltaic P124, 6 V, 1.2 W, ETFE, 66 × 113 mm, 31.6 g [Certain, vendor spec]. Imp 220 mA, Voc 7.28 V. Isc is about 240 mA [Likely].
- **Sun geometry** [Certain, Nov 16, College Station]: from 09:00 to 15:00 CST the azimuth sweeps about 131° to 225° and the elevation stays between 22° and 41° (peak 40.5° at solar noon, about 12:10 CST). With the robot facing south, the required pan is about −49° to +45° and the tilt equals the sun elevation.

## 4. Conventions (every module follows these)

| Quantity | Definition |
|---|---|
| Azimuth | 0° = true north, clockwise. 90° = east, 180° = south |
| Elevation | Degrees above the horizon |
| Robot heading | `heading_true = wrap360(imu_heading + declination)`. The BNO055 gives **magnetic** heading; declination is east-positive (`site.declination_deg`) |
| Pan | Signed, 0 at servo centre. Panel azimuth = `heading_true + az_offset + pan_sign · pan` |
| Tilt | Signed, measured **from vertical**, 0 = panel vertical. Panel elevation = `el_offset + tilt_sign · tilt`. With `tilt_sign = +1` the tilt command equals the sun elevation |
| `pan_sign`, `tilt_sign` | ±1. Defaults +1 [Guessing]; verify at first power-up with `calibrate-servo --check-sign` |
| `az_offset`, `el_offset` | Learned corrections. They absorb heading, mounting and servo-zero error |

- **Tilt convention warning.** The earlier plan described tilt "from horizontal" (panel tilt = 90° − elevation). The assembly guide and the code use **from vertical**. Convert with `e_n = 90° − tilt_from_horizontal`.
- **Units:** degrees at every public interface, mA, V, s, µs. Use `angdiff(a, b)` for every azimuth or heading subtraction (359° to 1° is +2°, not −358°).
- **Time:** all timestamps are UTC. [Certain] US daylight saving ended Nov 1, 2026, so local-time logic would put the sun model off by 15°. Intervals use `monotonic()`. A clock error of 1 minute is 0.25° of pointing. In sun mode the code refuses to start unless the clock is NTP-synchronised or the operator passes `--ack-clock`.

## 5. Algorithm

Session pipeline: **Preflight → Coarse align → Acquire → Track (with periodic Refine) → Park.** Hold is entered on cloud cover. Any fault parks safely.

### 5.0 Preflight and calibration
- **Preflight:** I2C scan (the PCA9685 runs at 100 Hz, set by the lab's `Code/lab/motor_servo_pwm.py`), panel Isc and bus-voltage sanity check, IMU heading and calibration status (magnetometer must be calibrated for the turn), clock sync, sun position now, a short servo wiggle.
- **Servo calibration (graded method 2, linear least squares).** Step each servo up then down its pulse range. Type in the protractor or phone-inclinometer angle at each step. Fit `angle = m·(pulse − 1500) + c` per direction. Report residual RMS and **hysteresis** (up/down gap). The result goes to `config/servo_cal.json`. Defaults before calibration: 500–2500 µs, 0.09°/µs [Guessing]. Simulated demo data gives about 0.092°/µs and 1.4–1.6° hysteresis.

### 5.1 Stage 1: predict the sun (method 1)
Julian date → mean anomaly → **Kepler's equation** (two interchangeable solvers: fixed-point and Newton-Raphson) → true anomaly → ecliptic longitude → declination and right ascension → sidereal time → hour angle → azimuth and elevation. No refraction (about 0.02° at these elevations). Target: within 0.5° of the NOAA calculator. The independent NOAA-series reference in `solar/reference_noaa.py` agrees within 0.024° in the simulated comparison.

[Certain] Earth's eccentricity is 0.0167, so both solvers converge in a handful of iterations and the answer barely changes. That is the "superficial" risk. The required analysis runs both solvers at the real e and at stress values 0.5 and 0.9: fixed-point converges linearly (factor `e·|cos E|` per step), Newton quadratically. Present Kepler as a comparison study, not as the main argument for "substantial numerics".

Optional: sunrise and sunset by bisection vs false position (method 6). Both are implemented and give the same times; false position needs far fewer iterations than bisection. Their stopping rules differ, so the counts are not strictly like-for-like. Say so in the report.

### 5.2 Stage 2: coarse align (method 5)
- **PID** on heading error `angdiff(target, heading)`, target 180° (south). The integral term is selectable: Euler, trapezoid or Simpson. The derivative is filtered. Anti-windup is built in.
- Output turns the wheels in place. A minimum duty offsets the motor deadband; inside the tolerance the command is 0.
- Done when the error stays under 2° for 1 s. Timeout 40 s: continue with a warning. The turn is skipped (with a warning) if the magnetometer is not calibrated. The heading is frozen after the turn and used for all pointing.
- **Safety:** wheels need `--robot-on-ground` (or `--bench`, which simulates the plant). Wheel outputs go to zero in every exit path.

### 5.3 Stage 3: acquire (method 3)
Run at session start, after Hold, and after repeated scan failures. For each axis: a coarse pass of 9 points, then **golden-section search** on the bracket, then a **parabolic-interpolation** vertex. The parabola uses the bracket ends plus the best golden point, because points 1° apart on a flat cosine peak differ by less than the sensor noise. Order: pan, tilt, pan again.
- First acquire uses ±40° (offsets unknown). Later acquires use ±15° around the prediction plus learned offsets.
- **Bootstrap:** the first sun-mode acquire sets the initial offsets from where the peak was found. If an offset exceeds 40°, the session faults with a message ("is the panel facing the sun? is the clock right?").
- Below 5 mA the search is meaningless: `no_signal` sends the supervisor to Hold or Park.
- **Lamp mode** has no sun model. Acquire is the whole job (±60° window), followed by a cosine-fit polish. It re-acquires (±30° window) when Isc drops 5% from the peak, so the lamp can be moved by hand.

### 5.4 Stage 4: track and refine (methods 2 and 4)
- **Track:** every 60 s, compute the sun position, convert to pan/tilt with the current offsets, slew-limit (60°/s) and command the servos. Limit flags (`LIMIT_PAN`, `LIMIT_TILT`) are logged. If a limit persists 300 s, the log suggests a new coarse turn.
- **Refine scan** every 720 s (about 12 min) per axis, never during Hold:
  1. Visit the centre, 7 points spread over ±15° in shuffled order, then the centre again. The scan must finish within 30 s.
  2. Fit `Isc(δ) = a·cos δ + b·sin δ + c` by linear least squares: form the K×3 system, solve the **normal equations** `(MᵀM)x = Mᵀy` with the **own LU decomposition** (partial pivoting, forward/back substitution). The peak offset is `δ* = atan2(b, a)`.
  3. Compute the residual RMS, the covariance-based `σ_δ*` and the **condition number** of `MᵀM`. [Certain] `cond(MᵀM) = cond(M)²`. The analysis script cross-checks against an SVD (relative difference below 1e-9 in the study).
  4. **Quality gates** accept or reject the scan: enough signal, at least 5 valid points, no over-range sample, residual RMS ≤ 3% of mean, peak inside the window, centre-to-centre drift ≤ 3%, `cond ≤ 2e5`, `σ_δ* ≤ 3°`. The first failing reason is logged.
  5. An accepted scan gives a total offset measurement. The **running weighted least-squares mean** of all accepted measurements is the offset estimate (forgetting factor 1.0 = none), with a standard error. Two rejected scans in a row trigger a re-acquire.
- **Why ±15°:** with a ±2° or ±5° spread the signal change is about one INA219 count (0.1 mA of about 240 mA) and `cond(MᵀM)` is large (about 1e6 at ±5°). The simulated study shows `δ*` scatter of about 0.4° at ±10° and 0.26° at ±15° versus tens of degrees at ±5°. Keep small spreads in the offline study to show exactly this.
- **Optional comparisons not built:** secant on the finite-difference derivative of the scan (expected to lose near the flat peak because differencing amplifies noise), and QR vs normal equations. The secant root finder itself exists and is tested but is not applied to scan data.

### 5.5 Stage 5: cloud flag and Hold
Expected clear-sky current: `I_clear(e) = k · 0.7^(AM^0.678)` with `AM = 1/sin(e)`. [Likely] The constants are approximate. `k` is estimated from the first clear-sky peak of the session (assumed clear) unless `--k-mA` is given. Cloud ratio `ρ = measured / (I_clear · cos i_pred)`.
- Enter Hold when `ρ < 0.70` for 5 ticks. Hold points by prediction only, with no scans and no offset changes.
- Leave Hold when `ρ > 0.80` for 10 ticks, then re-acquire (narrow) if Hold lasted over 300 s, otherwise resume Track.
- A cloud never reaches the offset estimate: scans with centre-to-centre drift above 3% are discarded, and no scan starts while `ρ` is below the enter threshold.

### 5.6 Park, and gain versus a fixed panel
- **Park** when the sun drops below 10° elevation, on operator stop (Ctrl-C), or on a fault: servos to the park pose (0, 0), wheels stopped, logs closed.
- **Virtual fixed panel** (one panel only): the tracked Isc is about the normal-incidence value `I_n`. `I_fixed = I_n · max(0, cos i_fixed)` for a south-facing panel at **45° from horizontal** (an honest winter reference, not a flat panel). Every 15 min the panel parks at that orientation for 10 s and the measured Isc is compared with the prediction (`fixed_check.csv`). Gain = `∫I_n dt / ∫I_fixed dt` by trapezoid and by Simpson. A simulated day gives about 1.10.

## 6. Software architecture

```
cli.py → supervisor.py (state machine, scheduling, safety)
            ├─ solar/    position, clearsky, reference_noaa
            ├─ control/  pid, heading, acquire, refine, offsets
            ├─ numerics/ roots, linalg (LU), leastsq, optimize, integrate   (pure Python)
            ├─ logging_.py (CSV + JSONL)
            └─ hardware/ base (interfaces) · real.py (Pi) · sim.py (laptop, tests)
```

- **Algorithms never touch hardware.** They take callbacks or plain lists. The same code runs on the robot, in the simulator and in unit tests.
- **Numerics use only the standard library.** NumPy appears in tests, analysis and the simulator as a reference. Hardware libraries are imported lazily, so everything imports on Windows and Linux without Pi packages. On the robot, `hardware/real.py` drives the servos and wheels through the lab's `Code/lab/motor_servo_pwm.py` and selects mux channels through `Code/lab/sensor_module.py`.
- **States:** `PREFLIGHT → COARSE_ALIGN → ACQUIRE → TRACK ⇄ HOLD → PARK → DONE`, and `FAULT` from anywhere.
- **Simulator:** virtual clock (a 6-hour day runs in about 6 s), NOAA-series "true" sun, cosine panel with noise, servo backlash and calibration error, injected true offsets, clouds, a movable lamp, a yaw plant. It is the only place with ground truth, so it is where the offset-estimation accuracy claim is tested. Same seed gives the same log.
- **Fail-safe rules:**
  - A required hardware value that is unset (`mux_channel_panel`, `mux_channel_imu`, `servo_channel_pan`, `servo_channel_tilt`, and `drive.left_motor_channels` / `drive.right_motor_channels` for the wheels) stops the real backend. It never guesses a channel.
  - Wheels run only in COARSE_ALIGN with explicit consent.
  - Servo commands are clamped to ±85° and slew-limited. Pulses stay inside the calibrated range.
  - A bad scan never moves the offsets.
  - An offset above the bootstrap limit is a fault, not a silent clamp.
  - Three I2C errors in 60 s cause a fault. A watchdog stops the wheels if the loop stalls.
  - Do not hide servo-caused Pi resets with retries; fix the power (`Hardware & BOM.md`).

## 7. Numerical methods and what to show for each

| # | Method | Code | Required analysis (script) |
|---|---|---|---|
| 1 | Fixed-point vs Newton-Raphson on Kepler's equation | `numerics/roots.py`, `solar/position.py` | Error vs iteration at e = 0.0167, 0.5, 0.9, linear vs quadratic (`kepler_convergence.py`); model vs NOAA (`prediction_vs_measured.py`) |
| 2 | Linear least squares (servo calibration; offset estimate) | `numerics/leastsq.py`, `control/offsets.py` | Fit, residuals, hysteresis (`fit_servo_cal.py`); estimate vs number of scans against truth (`offset_convergence.py`) |
| 3 | Golden-section search + parabolic interpolation | `numerics/optimize.py`, `control/acquire.py` | Interval shrink 0.618 per step; error vs noise with and without the parabola (`golden_convergence.py`) |
| 4 | Cosine least squares via normal equations + LU, condition number | `numerics/linalg.py`, `numerics/leastsq.py`, `control/refine.py` | Condition number and `δ*` scatter vs spread (`cosine_fit_study.py`) |
| 5 | PID with numerical integration (Euler, trapezoid, Simpson) | `numerics/integrate.py`, `control/pid.py`, `control/heading.py` | Step response, rise/overshoot/settling, gain map (`pid_study.py`) |
| 6 | Bisection vs false position (optional) | `numerics/roots.py`, `solar/position.py` | Iterations to equal tolerance (`sunrise_roots.py`) |
| - | Trapezoid and Simpson integration of Isc | `numerics/integrate.py` | Tracking gain, checked by the parked fixed-panel samples (`tracking_gain.py`) |

The full generated table with line numbers and test files is `Code/docs/method_code_map.md`. Cut for scope: full physics simulator, ODE servo model, finite-difference gradient method, joint 2-D quadratic fit, photodiode quadrant sensor, APDS9960 cloud detection, wheel-driven azimuth tracking.

**Analysis notes**
- The PID study shows Euler and trapezoid nearly identical at the 20 Hz loop rate; they differ more at a coarse step. Say so honestly. A hardware run with each integral rule is still required.
- Log everything (inputs, intermediate values, timestamps). The analysis must work from logs alone.

## 8. Where the code differs from the original specification

Full list: `Code/docs/decisions.md`, section "Decisions". The ones that matter for the report:
- `refine.max_cond` is 2e5, not 1e4: `cond₂(MᵀM)` is 2.3e4 at ±15° and 1.2e5 at ±10°.
- The offset comes directly from the peak command. The earlier formula had the wrong sign and was also wrong when a command was clamped.
- The acquire parabola uses the bracket ends plus the best golden point (section 5.3).
- Lamp re-acquire uses a 5% drop and a ±30° window (a 25° lamp move only drops Isc by 9.4%).
- Inside the turn tolerance the wheel command is 0. The turn is skipped if the magnetometer is uncalibrated.
- Declination is a placeholder (2.0° east). Look up the value for the site and date at NOAA and record the source.
- Not built: QR vs normal equations, secant on scan derivative.

Also reconciled across the old documents: tilt is from vertical (section 4); the servos are SG90s (the old BOM said "model TBD"); the old BOM assumed a ~75 mm pan bearing, while the CAD and assembly guide use a 94 × 94 × 9 mm square lazy susan (see `Hardware & BOM.md` section 4); the wheels are used only for the coarse turn.

## 9. Test ladder and field sessions

Nothing is debugged for the first time outdoors. Ladder: unit tests and simulator on a laptop → bench with the real backend (preflight, servo calibration, INA219 vs multimeter) → indoor lamp run → outdoor session 1 → outdoor session 2.

**Outdoor window:** about 10:30 to 13:30 CST around solar noon (about 12:10 CST). Pick the two clearest days from the forecast and keep one backup day. [Likely] Only about two outdoor sessions fit the schedule.

**Session 1 (about 2 h): calibration and first tracking**
1. Set up on flat pavement in open sun. Ethernet to the laptop, start `tmux`, confirm UTC time.
2. `static-log`: panel fixed, 5-10 min of Isc, for the noise model.
3. Coarse turn to south once the BNO055 shows the magnetometer calibrated.
4. Acquire, then track with refine scans at ±10°, ±15° and ±20° spreads.
5. Park at the fixed reference orientation for about 10 s every 15 min (automatic).
6. Copy all logs off the Pi before leaving. The course also requires a backup after every lab.

**Session 2 (about 2-3 h):** full tracking run at the spread chosen from session 1, with the same fixed-panel checks. The tracking-gain number and pointing-error plots come from this run.

**Indoor demo:** `lamp` mode (acquire and refine live with a lamp moved by hand), plus outdoor data and video for the sun model and coarse turn. [Guessing] The lamp must give tens of mA of Isc; test it early.

**Risks**
- **Weather:** keep a backup day.
- **Servo backlash:** SG90 plastic gears; expect about 1-1.5° hysteresis. Measure up and down sweeps on the real servos.
- **Servo brown-outs:** [Guessing] the HAT servo rail may share the Pi's 5 V converter. If servo moves reset the Pi, add a separate 5-6 V supply and a bulk capacitor (see `Hardware & BOM.md`).
- **Azimuth is the weak axis:** magnetometer heading near motors and servos can be off by several degrees. That is why the offset is learned from the sun. Do not remove it.
- **Light changing during a scan:** short scans, centre-to-centre drift gate, shuffled order.
- **Shading:** the robot body can shade the panel at low sun. Flag samples under 25° elevation in the analysis.
- **Tether:** strain relief on the Ethernet cable and panel leads; leave slack for the coarse turn.
- **BNO055 clock stretching:** [Likely] occasional `OSError` on the Pi's I2C. The code retries up to 3 times. Slow the bus only if errors actually appear.

## 10. Open items

- INA219 mux channel: not recorded. Find the channel showing 0x41 with `Code/lab/sensor_scan.py` and set `mux_channel_panel` in `Code/config/robot.toml`. The other channels are prefilled from the lab scripts (BNO055 on mux channel 6 from `lab/test_sensor.py`; pan servo 13, tilt servo 12 from `lab/test_motor.py`). Confirm all with `preflight`.
- Which wheel pair is left, the turn direction (`turn_sign`) and the gear ratio (section 2).
- Pi model and Python version; whether the INA219 package is installed in `~/env` [Guessing: it is missing and needs internet once].
- Real test-site coordinates and magnetic declination (placeholder: College Station, 2.0°).
- Clear-sky constants and cloud thresholds: tune on the first outdoor session.
- Due dates and report format (`Course Requirements.md`).
