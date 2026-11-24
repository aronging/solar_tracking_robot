# MXET 345 Solar Tracker

A pan/tilt solar panel on the lab robot: the Pi predicts the sun from the clock, points the panel, finds the power peak from the panel's short-circuit current, and learns the rig's pointing errors from periodic scans; the wheels are used once, to face the robot south.
Status: everything runs and passes its tests (193) against the simulator, but the real hardware backend has not been run on the robot yet.

Design: [Design Overview](../docs/Design%20Overview.md). Wiring: [Electrical Assembly Guide](../docs/Electrical%20Assembly%20Guide.md). Parts: [Hardware & BOM](../docs/Hardware%20%26%20BOM.md).
Where this code differs from the original build specification, and its known limits: [docs/decisions.md](docs/decisions.md).

## Folder map

This `Code/` folder is the folder you open in VS Code on the Pi.

```
Code/
  README.md              this guide
  .vscode/               VS Code settings and tasks; task numbers match the steps below
  config/default.toml    every setting with its default; do not edit
  config/robot.toml      the only file you edit (channels, site, signs, offsets); tracked in git
  lab/                   the lab scripts, unchanged; the tracker imports motor_servo_pwm.py and sensor_module.py from here
  solar_tracker/         the tracker (python -m solar_tracker <command>)
  analysis/              scripts that make the report figures from logs
  tests/                 pytest tests (run against the simulator)
  docs/                  decisions.md, method_code_map.md
```

How the configuration works:

- `config/robot.toml` is loaded automatically after `config/default.toml`. Commands do not need `--config`.
- `--set section.key=value` overrides one value for one run, for example `--set panel.zero_offset_mA=1.2`.
- `--hardware sim` runs a command against the simulator, without the robot.
- Global options go before the command: `python -m solar_tracker --hardware sim preflight`.
- The real backend refuses to start until the robot.toml keys for the mux and servo channels are set. It never guesses a channel.

## Setup, in order

Do the steps in order. Each step that has a VS Code task names it. Run a task with Terminal > Run Task, then pick it by name.
To type a command yourself, use the VS Code terminal (Terminal > New Terminal). It opens in `~/mxet345_project/Code`. If the prompt does not start with `(env)`, run `source ~/env/bin/activate` first.

### Part A. Laptop (once)

**Step 1. Install VS Code.**
Install VS Code and the extensions "Remote - SSH" and "Python" (both by Microsoft).
You should see a Remote Explorer icon in the left bar.

**Step 2. Connect to the Pi.**
Join the lab Wi-Fi `mxet_Lab`, or plug in Ethernet.
Press F1, run "Remote-SSH: Connect to Host...", and enter:

```
pi@192.168.1.2xx
```

`xx` is your team number. Pick "Linux" if asked, then type the Pi password.
You should see `SSH: 192.168.1.2xx` in the bottom-left corner.
If the connection times out, open the laptop's user settings (F1, "Preferences: Open User Settings (JSON)") and add `"remote.SSH.useLocalServer": false`, then connect again.

### Part B. Pi (once)

**Step 3. Clone the repo and open the folder.**
Open a terminal (Terminal > New Terminal). It runs on the Pi. Run:

```bash
git clone https://github.com/aronging/solar_tracking_robot ~/mxet345_project
```

The repo is private. The VS Code terminal uses the laptop's GitHub sign-in, so the clone works here. It may not work in a plain SSH session.
If `~/mxet345_project` already exists, rename it first: `mv ~/mxet345_project ~/mxet345_project_old`.
Then File > Open Folder, enter `/home/pi/mxet345_project/Code`, and click OK.
When VS Code asks to install the recommended extensions, accept. This installs the Python extension on the Pi.
You should see `README.md`, `config/` and `lab/` in the Explorer.

**Step 4. Install the Pi packages.** Task "4 Install Pi packages".

```bash
~/env/bin/pip install -r requirements-pi.txt
```

This needs internet once. The INA219 package is probably not installed on the lab image.
You should see `Successfully installed ...` or `Requirement already satisfied` for each package.
The analysis scripts in steps 10 and 15 also need matplotlib. If `~/env/bin/python -c "import matplotlib"` fails, run `~/env/bin/pip install matplotlib`, or run those two steps on the laptop.

### Part C. Wiring into config/robot.toml (robot on a stand, wheels off the ground)

Wire the panel sensor and the servos first, as in the [Electrical Assembly Guide](../docs/Electrical%20Assembly%20Guide.md) steps 1 to 7. Measure the servo V+ rail before you connect a servo.

> **Warning:** `lab/test_motor.py` spins both wheels and swings servos 12 and 13 through 0 to 180 degrees. Only run it with the wheels off the ground and the panel's servo horns off. After step 8 the horns are on, so do not run it again unless you take them off.

**Step 5. Find the mux channels.** Task "5 Scan mux channels (lab)".

```bash
python lab/sensor_scan.py
```

You should see one line per mux channel, for example `Channel 6:['0x28']`. The INA219 (panel) shows as `0x41`. The BNO055 (IMU) shows as `0x28`. Other lab sensors also show (APDS9960 `0x39`, VL53L4CD `0x29`).
In `config/robot.toml` set:

- `hardware.mux_channel_panel` = the channel that shows `0x41`. It is commented out until you set it.
- `hardware.mux_channel_imu` = the channel that shows `0x28`. It is prefilled as 6 from `lab/test_sensor.py`.

If `0x41` does not show, see the troubleshooting table in the Electrical Assembly Guide.

**Step 6. Check the servo channels and the site.** No task.
Look at the servo HAT. Check that the pan servo is plugged into `hardware.servo_channel_pan` (prefilled 13) and the tilt servo into `hardware.servo_channel_tilt` (prefilled 12). These are the servo channels in `lab/test_motor.py`. If pan and tilt are reversed, swap the two numbers in robot.toml, not the plugs.
Check the `[site]` section: `name`, `lat_deg`, `lon_deg` (east positive) and `declination_deg` (east positive). The defaults are for College Station. Look up the declination for your site and date with the NOAA magnetic field calculator (https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml) and note the source in [docs/decisions.md](docs/decisions.md).

### Part D. Tracker checks

Each check is a VS Code task. Each runs `python -m solar_tracker <command>`. Ctrl-C in the terminal parks the servos, stops the wheels and closes the logs.

**Step 7. Preflight.** Task "7 Preflight".

```bash
python -m solar_tracker preflight
```

It scans the I2C bus, reads the panel and the IMU, checks the clock, computes the sun position, and wiggles each servo by 20 degrees.
You should see lines `i2c`, `panel`, `imu`, `clock`, `sun`, `preflight_ok`, and at the end `exit: done`.
Fix anything flagged:

- `CONFIG ERROR: ...` names the robot.toml key that is missing or wrong.
- `panel_warning ... negative current`: the panel leads are reversed.
- `imu_warning ... magnetometer calibration`: move the robot through figure-eights and hold it still on each face, then run preflight again. The coarse turn (step 12) is skipped until `cal_mag` is at least 3.
- `ntp_synced=false`: the Pi clock is not synchronised. Compare `date -u` with a phone. One minute of clock error is 0.25 degrees of pointing error.

**Step 8. Centre the servos.** Task "8 Park (centre servos)".

```bash
python -m solar_tracker park
```

Both servos move to the park pose (centre, 1500 us) and stop. You should see `exit: done`.
Install the servo horns now, with the servos in this centred state, as the assembly guide states.

**Step 9. Check the servo directions.** Tasks "9a Check pan sign", then "9b Check tilt sign".

```bash
python -m solar_tracker calibrate-servo --servo pan --check-sign
python -m solar_tracker calibrate-servo --servo tilt --check-sign
```

The servo moves to -20, 0, +20 and 0 degrees. It waits for Enter at each pose.
Positive pan must turn the panel clockwise, seen from above. Positive tilt must lift the panel normal.
If a direction is wrong, set `servo.pan_sign = -1` or `servo.tilt_sign = -1` in robot.toml. Do not swap wires.

**Step 10. Calibrate the servos.** Tasks "10a Calibrate pan" and "10b Calibrate tilt", then "10c Fit servo calibration".

```bash
python -m solar_tracker calibrate-servo --servo pan
python -m solar_tracker calibrate-servo --servo tilt
python analysis/fit_servo_cal.py logs/<log folder>/servo_cal.csv
```

The servo steps through its pulse range in 100 us steps, up and then down. At each prompt (`pan up 1100 us -> measured angle`) type the angle you read from a protractor or phone inclinometer. Blank skips a point. `q` stops.
Each calibration run prints its log folder, for example `logs/20261124_150000Z_calibrate-servo`. Run the fit once for each of the two folders (task 10c asks for the folder). The fit merges both servos.
You should see a slope, intercept, residual RMS and hysteresis for each servo. The fit writes `config/servo_cal.json`, and the tracker uses it automatically. No robot.toml key to set. The file is git-ignored, so it exists only on this Pi.

**Step 11. Zero the panel current.** Task "11 Panel zero (cover panel)".
Cover the panel completely (for example with a box). Then run:

```bash
python -m solar_tracker static-log --minutes 1
python analysis/noise_model.py --log logs/<log folder>/static.csv
```

The first command logs the current at 10 Hz for one minute. The second prints `mean_mA`.
Set `panel.zero_offset_mA` in robot.toml to that mean. The logged current already has the old `zero_offset_mA` subtracted, so if it was not 0.0, add the mean to the old value.
Then take the cover off, put the panel under a lamp, and run step 7 again. Compare the `panel isc_mA` value with a multimeter in current mode across the panel (sign and size).

**Step 12. Check the wheels.** Task "12 Bench turn (wheels off ground)", then two commands you type.
Keep the robot on the stand, wheels off the ground. The wheel settings in robot.toml are prefilled: `drive.left_motor_channels = [0, 1]` and `drive.right_motor_channels = [2, 3]` (the `PWM_Motor(0, 1)` and `PWM_Motor(2, 3)` pairs in `lab/test_motor.py`), `turn_sign = 1`. Nothing confirms yet which pair is the left wheel.

1. Bench turn. The wheels do not move. The PID turns a simulated robot, starting from the real IMU heading.

   ```bash
   python -m solar_tracker coarse-turn --bench
   ```

   You should see `coarse_align success=true reason=in tolerance` and `exit: done`.

2. Real wheels, still off the ground. Read `heading_true_deg` from the `imu` line. Pick a target 90 degrees clockwise from it (heading + 90, minus 360 if above 360). Run:

   ```bash
   python -m solar_tracker coarse-turn --robot-on-ground --target <heading + 90>
   ```

   The wheels spin. The robot cannot turn on the stand, so the wheels keep going for up to 40 s. Press Ctrl-C once you have seen the direction.
   A clockwise turn needs the left wheel to drive forward and the right wheel to drive backward. Fix robot.toml until that is what you see:

   | You see | Set in robot.toml |
   |---|---|
   | The "left" channels drive the right wheel | swap `drive.left_motor_channels` and `drive.right_motor_channels` |
   | One wheel turns the wrong way | flip that wheel's `drive.left_sign` or `drive.right_sign` to -1 |
   | Both wheels turn the wrong way | `drive.turn_sign = -1` |

   The right motor is mounted mirrored (`lab/test_encoder.py` counts it negative going forward), so expect to need `right_sign = -1`.
   If you cannot tell which pair drives which wheel, `lab/test_motor.py` runs both pairs forward, then backward. Read the warning in Part C before you run it.

3. On the ground. Put the robot on the floor with clear space around it and run:

   ```bash
   python -m solar_tracker coarse-turn --robot-on-ground
   ```

   The robot should turn to face south (180 degrees true) and stop. You should see `coarse_align success=true` with `heading_true_deg` within 2 degrees of 180.

### Part E. Run

**Step 13. Lamp demo (indoors).** Task "13 Lamp demo".

```bash
python -m solar_tracker lamp --seconds 300
```

Put a lamp in front of the panel. The panel finds the lamp, polishes the peak with a cosine-fit scan, and finds it again when the current drops 5%. Move the lamp to show this.
You should see acquire and scan lines, then `exit: duration reached` after 300 s.

**Step 14. Track the sun (outdoors).** Task "14 Track (robot on ground)".

```bash
python -m solar_tracker track --robot-on-ground
```

Put the robot on level ground in full sun. The robot turns to face south, finds the sun, then tracks it and scans about every 12 minutes to learn the pointing offsets.
It runs until the sun is below 10 degrees elevation, or until `--duration-min` minutes (for example `--duration-min 60`). Ctrl-C stops it cleanly.
To skip the wheels, aim the robot south by hand and run `track --skip-turn` instead.
If the clock is not NTP-synchronised, track refuses to start. Check `date -u` against a phone, then add `--ack-clock`.

**Step 15. Analyze the log.** Task "15 Analyze latest log" runs it on the newest folder in `logs/` (`analyze latest`).

```bash
python -m solar_tracker analyze logs/<log folder>
```

This runs every analysis script that has data in that folder. Figures and CSVs go into `logs/<log folder>/analysis_out/`.
Copy `logs/` off the Pi after every session (see "Get the logs off the Pi" below).

Extra tasks: "Run tests" (`python -m pytest -q`) and "Sim day (no hardware)" (`python -m solar_tracker sim-day`).

## Everyday use

1. Turn on the robot. Join `mxet_Lab` (or plug in Ethernet).
2. In VS Code: F1, "Remote-SSH: Connect to Host...", `pi@192.168.1.2xx`. VS Code reopens the last folder. If not, File > Open Folder `/home/pi/mxet345_project/Code`.
3. In the terminal:

   ```bash
   cd ~/mxet345_project/Code
   git pull
   ```

   If `git pull` refuses because `config/robot.toml` has local changes, run `git stash`, `git pull`, `git stash pop`, then check robot.toml.
4. Run task "13 Lamp demo" indoors or task "14 Track (robot on ground)" outdoors.
5. Get the logs off the Pi. `logs/` is git-ignored, so git does not carry it. Either right-click `logs` in the VS Code Explorer and pick Download, or run this on the laptop:

   ```bash
   scp -r pi@192.168.1.2xx:~/mxet345_project/Code/logs .
   ```

When you change `config/robot.toml` on the Pi, commit and push it so the team has the same settings.

Working on the laptop without the robot (Windows; on Linux use `.venv/bin/python`):

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m solar_tracker --hardware sim preflight
```

The Pi runtime needs only the standard library and the Adafruit packages (and `tomli` on Python < 3.11). No numpy on the Pi.

## Commands

| Command | What it does |
|---|---|
| `preflight` | I2C scan, panel and IMU readings, clock sync, sun position, servo wiggle |
| `calibrate-servo --servo pan\|tilt [--check-sign] [--step-us 100]` | interactive pulse sweep up and down, writes `servo_cal.csv` |
| `static-log --minutes 10 --pan 0 --tilt 30` | fixed pose, Isc at 10 Hz (noise model) |
| `coarse-turn --robot-on-ground \| --bench [--integral euler\|trapezoid\|simpson] [--target 180]` | PID turn on its own |
| `acquire --mode sun\|lamp` | acquire only |
| `lamp --seconds 300` | indoor demo: acquire the lamp, polish with a cosine fit, re-acquire when Isc drops 5% |
| `track --robot-on-ground \| --skip-turn [--ack-clock] [--k-mA] [--duration-min] [--spread]` | the full session |
| `park` | servos to the park pose |
| `analyze <log folder> \| latest` | runs every analysis script that has data in that folder, output in `<log folder>/analysis_out/` |
| `sim-day [--seed] [--true-az-offset 7] [--true-el-offset -3] [--clouds 9000:10200:0.3] [--hours 6]` | simulated day with injected errors, about 6 s |

Run each as `python -m solar_tracker <command>`. Add `--hardware sim` before any command to run it against the simulator.
The PCA9685 runs at 100 Hz, set by `lab/motor_servo_pwm.py`. The tracker does not check or change it.
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
