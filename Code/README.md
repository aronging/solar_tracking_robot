# MXET 345 Solar Tracker

Two-servo pan/tilt solar panel on the lab robot. The Pi predicts the sun from the clock
(Kepler's equation), points the panel, finds the power peak from the panel's short-circuit
current, and every ~12 minutes scans around the prediction and fits a cosine to learn the
rig's built-in pointing errors. The wheels are used once, to face the robot south with a PID.

Design: `../Design Overview.md`. This README covers how to run it and where this code
deliberately differs from the original build specification (in git history, commit `30ef60b`).

**Status:** everything runs and is tested against the simulator on a laptop (190 tests).
`hardware/real.py` has **not been run on the robot yet**. Start with the first power-up
checklist below.

## Install

Laptop (Windows/Linux, Python 3.9+), from this folder:

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     (Linux: .venv/bin/python)
.venv/Scripts/python -m pytest
```

Raspberry Pi: copy this folder to `/home/pi/mxet345_project`, then

```
source ~/env/bin/activate
pip install -r requirements-pi.txt        # needs internet once (the INA219 package is probably missing)
```

The Pi runtime needs only the standard library plus the Adafruit packages (`tomli` too on
Python < 3.11). No numpy on the Pi.

## Configuration

`config/default.toml` holds every setting. Copy `config/site_example.toml` to
`config/site_<name>.toml`, fill in the real channels and site, and pass it with `--config`.
`--set section.key=value` overrides one value. Global options go **before** the command:

```
python -m solar_tracker --config config/site_field.toml track --robot-on-ground
```

The real backend refuses to start until these are set (it never guesses a channel):
`hardware.mux_channel_panel`, `hardware.mux_channel_imu`, `hardware.servo_channel_pan`,
`hardware.servo_channel_tilt`. The wheels refuse to move until `drive.left_channel`,
`drive.right_channel` and `drive.direction_scheme` are set.

## First power-up checklist

1. Robot on a stand, wheels off the ground. Ethernet to the laptop, `source ~/env/bin/activate`, start `tmux`.
2. `python -m solar_tracker --config <site> preflight`. Fix anything flagged. If it says the
   PCA9685 is not at 50 Hz (normal after a power cycle), run the lab's motor/servo script once
   first, or set `hardware.allow_set_pca9685_hz=true`.
3. `calibrate-servo --servo pan --check-sign`, then `--servo tilt --check-sign`. Positive pan
   must turn the panel clockwise seen from above; positive tilt must lift the normal. If not,
   set `servo.pan_sign = -1` / `servo.tilt_sign = -1`.
4. `calibrate-servo --servo pan`, then `--servo tilt` (type in the protractor angle at each
   prompt), then `python analysis/fit_servo_cal.py <log folder>/servo_cal.csv`. That writes
   `config/servo_cal.json`, which is picked up automatically. Run both servos into one CSV or
   run the fit once per log; it merges.
5. Panel under a lamp: compare the `preflight` Isc with a multimeter (sign and size).
6. Only then fill in `drive.*`. Check `direction_scheme` against the lab's `test_motor.py`
   (see Limitations). Test `coarse-turn --bench`, then off the ground, then `--robot-on-ground`.

## Commands

| Command | What it does |
|---|---|
| `preflight` | I2C scan, PCA9685 frequency, panel and IMU readings, clock sync, sun position, servo wiggle |
| `calibrate-servo --servo pan\|tilt [--check-sign] [--step-us 100]` | interactive pulse sweep up and down, writes `servo_cal.csv` |
| `static-log --minutes 10 --pan 0 --tilt 30` | fixed pose, Isc at 10 Hz (noise model) |
| `coarse-turn --robot-on-ground \| --bench [--integral euler\|trapezoid\|simpson] [--target 180]` | PID turn on its own |
| `acquire --mode sun\|lamp` | acquire only |
| `lamp --seconds 300` | indoor demo: acquire the lamp, polish with a cosine fit, re-acquire when Isc drops 5% |
| `track --robot-on-ground \| --skip-turn [--ack-clock] [--k-mA] [--duration-min] [--spread]` | the full session |
| `park` | servos to the park pose |
| `analyze <log folder>` | runs every analysis script that has data in that folder, output in `<log folder>/analysis_out/` |
| `sim-day [--seed] [--true-az-offset 7] [--true-el-offset -3] [--clouds 9000:10200:0.3] [--hours 6]` | simulated day with injected errors, about 6 s |

Add `--hardware sim` before any command to run it against the simulator.
Ctrl-C parks the servos, stops the wheels and closes the logs.

## Logs

Each run makes `logs/YYYYMMDD_HHMMSSZ_<command>/` with `session.json` (config, versions, final
offsets, exit reason), `events.jsonl`, `run.log` and the CSVs: `cycle.csv` (every second),
`scan.csv` and `scan_fit.csv` (refine scans), `acquire.csv`, `turn.csv`, `fixed_check.csv`,
`static.csv`, `servo_cal.csv`. Column lists are in `solar_tracker/logging_.py`. Rows are
fsync'd as written on real hardware. Copy `logs/` off the Pi after every session.

## Figures for the report

Each script writes to `analysis_out/<script>/`, prints its key numbers and takes `--seed`.
Without `--log` the session-based ones run a simulated day, so every figure can be produced
today; pass `--log <session folder>` (or the CSV) for hardware data.

| Script | Method | Shows |
|---|---|---|
| `kepler_convergence.py` | 1 | fixed-point (linear) vs Newton (quadratic) at e = 0.0167, 0.5, 0.9 |
| `prediction_vs_measured.py` | 1 | model vs NOAA reference (max 0.024 deg); measured peak vs prediction |
| `sunrise_roots.py` | 6 | bisection vs false position |
| `fit_servo_cal.py <csv>` / `--demo` | 2 | PWM to angle line fits, hysteresis |
| `golden_convergence.py` | 3 | 0.618 shrink rate; error vs noise with and without the parabola |
| `cosine_fit_study.py` | 4 | condition number and peak scatter vs scan spread |
| `offset_convergence.py` | 2/4 | learned offset vs number of scans, against sim truth |
| `pid_study.py [--log turn.csv ...]` | 5 | Euler vs trapezoid vs Simpson, gain/stability map |
| `tracking_gain.py` | trapezoid/Simpson | energy vs a virtual fixed panel |
| `noise_model.py`, `plot_session.py` | - | sensor noise; session overview |
| `method_code_map.py` | - | writes `docs/method_code_map.md` (method, file, lines, test, script) |

## Decisions (where the spec was ambiguous or wrong)

1. **`refine.max_cond` is 2e5, not 1e4.** cond2(MᵀM) is 2.3e4 at the default 15° spread and
   1.2e5 at 10°, so the spec's guess rejected every scan.
2. **Offset update sign.** With the spec's own pointing equations, a peak found at
   `command + δ*` means `offset_true = offset_used − sign·δ*`, not `+ δ*`. The code computes
   the offset directly from the peak command, which also stays correct when a command was clamped.
3. **Acquire parabola uses the bracket ends plus the best golden point,** not the nearest
   neighbours: points 1° apart on a flat cosine peak differ by less than the sensor noise.
   Narrow acquire windows also use fewer coarse points so they stay at least 7.5° apart.
   `golden_convergence.py` shows the effect (0.9° vs 2.0° RMS at 0.4 mA noise).
4. **`lamp_reacquire_drop_frac` is 0.05, not 0.10.** A 25° lamp move drops Isc only 9.4%.
   Lamp re-acquire uses a ±30° window.
5. **TOML has no `null`.** Required-but-unknown keys are commented out in `default.toml`.
6. **`hardware.allow_set_pca9685_hz`** (default false) was added so the tracker can be used
   after a power cycle without the lab script. Off by default, as the spec demands.
7. **Inside the turn tolerance the wheel command is 0** (success = inside for `hold_s`),
   because the minimum-duty rule would otherwise make the robot hunt.
8. **IMU magnetometer not calibrated → the turn is skipped** with a warning, not attempted.
9. **`calibrate-servo` steps 100 µs by default** (21 points each way) so a person can finish it.
10. **The session heading is frozen after the coarse turn** and used for all pointing; the IMU
    is not read into the pointing loop while tracking.
11. **PID derivative is taken on the error,** which equals the measurement derivative for a
    constant target, with the first sample contributing zero.
12. **fsync is off under the simulator** (it is on for real hardware) so tests stay fast.
13. **Scan/fixed-check cloud abort** is per scan point (ratio below the hold threshold); a
    fixed check is not aborted, it logs `fixed_check_drift` if the light changed.
14. **Lamp mode runs a cosine-fit scan after each acquire** to polish the peak and demo
    method 4 indoors; it does not learn offsets (there is no sun model indoors).
15. Refraction is not applied (about 0.02° at these elevations). Declination 2.0° is a
    placeholder: look it up at NOAA for the site and date and note the source here.

## Limitations

- **Real backend is untested on hardware.** Library names follow the Adafruit docs.
- **Wheel drive:** the driver wiring is unknown, so only one scheme exists, `rc_pulse`
  (1500 µs stop, ±500 µs full). If the lab's `test_motor.py` drives the motors another way,
  add that to `RealDrive` in `hardware/real.py`. `--skip-turn` always works.
- The lab's `motor_servo_pwm.py` / `sensor_module.py` are not used. Do not run `Sensor_Thread`
  alongside this program unless it takes `hardware.real.BUS_LOCK`.
- Not built (spec Tier 2): QR vs normal equations, secant-on-scan-derivative study. The
  secant, bisection and false-position root finders exist and are tested.
- Offsets are a plain weighted mean of all scans (`offset_forget = 1.0`), so a servo gain error
  that changes with pan angle is averaged, not tracked. Set `refine.offset_forget` below 1 to
  weight recent scans more.
- Bisection stops on bracket width and false position on step size, so their iteration counts
  are not a strictly like-for-like comparison. Say so in the report.
