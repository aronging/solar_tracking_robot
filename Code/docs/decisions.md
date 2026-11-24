# Decisions and limitations

Where this code deliberately differs from the original build specification (in git history,
commit `30ef60b`), and what it does not do. Setup and run steps are in [../README.md](../README.md).

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
6. **The PCA9685 frequency comes from `lab/motor_servo_pwm.py` (100 Hz).** The tracker no
   longer checks or sets it.
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
- **Wheel drive:** the drive uses the lab's `PWM_Motor` FWD/RV channel pairs from
  `drive.left_motor_channels` and `drive.right_motor_channels`. Only the bench and on-ground
  checks (README step 12) verify which wheel is which. `--skip-turn` always works.
- The tracker imports `lab/motor_servo_pwm.py` and `lab/sensor_module.py`. Do not run the lab's
  `Sensor_Thread` alongside it unless it takes `hardware.real.BUS_LOCK`.
- Not built (spec Tier 2): QR vs normal equations, secant-on-scan-derivative study. The
  secant, bisection and false-position root finders exist and are tested.
- Offsets are a plain weighted mean of all scans (`offset_forget = 1.0`), so a servo gain error
  that changes with pan angle is averaged, not tracked. Set `refine.offset_forget` below 1 to
  weight recent scans more.
- Bisection stops on bracket width and false position on step size, so their iteration counts
  are not a strictly like-for-like comparison. Say so in the report.
