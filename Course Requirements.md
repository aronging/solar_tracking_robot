# MXET 345 Final Project: Course Requirements and Robot Platform

**Course:** MXET-345, Numerical Methods in Robotics Applications (Texas A&M, Multidisciplinary Engineering Technology).
**Replaces:** the pre-lab, robot-introduction lab, official requirements (V1) and the earlier "Final Project Overview" files. The originals are in git history (commit `30ef60b`) and on Canvas.
**Confidence tags:** [Certain] / [Likely] / [Guessing]. Untagged text comes from the course documents.

## 1. What the course requires

| Item | Requirement |
|---|---|
| Topic | Must need numerical methods **substantially**, not superficially |
| Hardware | A physical component is required: the lab mobile robot or your own system. Show how computation and hardware connect |
| Numerical methods section | Required in **both the demo and the report**. It must (1) explain each method, (2) show where it is in the code, (3) analyze convergence, stability and accuracy, (4) give supporting data, plots or experiments |
| Team size | Course document: 3-4 students. **Our team has 5** (assigned by the instructor because of class size) |
| Robot rule | Do not disassemble the robot. Only **add** parts |
| Files | Back up your files after each lab |

**Grading factors** (no weights given): complexity of the problem and system design; robustness and accuracy; report, documentation and analysis; creativity and innovation.

**Deliverables**
1. Project proposal: title and objectives, hardware description, numerical methods, expected outcomes and challenges.
2. Parts list to the TA, after the proposal.
3. Final: written report, slides (PPT) and a live demo.

**Not given in the course documents** (confirm with the TA): due dates (the team planned for about Nov 24 [Guessing]), grading weights, report format or length, presentation length, demo conditions for "robustness", whether SciPy/NumPy solvers are allowed. The code implements every graded method from scratch and uses NumPy only as a reference in tests and analysis, which is safe under either policy.

## 2. Where our evidence lives

| Requirement | Where to find it |
|---|---|
| Method explanation | `Design Overview.md` section 5 and 7 |
| Method location in code | `Code/docs/method_code_map.md` (generated; method, file, function, lines, test, analysis script) |
| Convergence, stability, accuracy | Analysis scripts in `Code/analysis/` (table in `Code/README.md`); figures write to `Code/analysis_out/` |
| Short method summary | `Solar Tracker – Numerical Methods Summary.docx` |
| Hardware integration | `Hardware & BOM.md`, `Hardware List & Assembly Guide.pdf`, `CAD/` |
| Robustness and accuracy results | Session logs from the lamp test and outdoor sessions (`Design Overview.md` section 9). None are in this folder yet |

## 3. Team roles and method owners

| Role | Owner area | Graded method |
|---|---|---|
| A | Mechanical: CAD, print, assemble, mount on the robot | none |
| B | Electronics, calibration, parts, TA contact | 2: linear least squares (servo calibration) |
| C | Sun prediction | 1: Kepler fixed-point vs Newton-Raphson; optional bisection vs false position |
| D | Estimation | 4: cosine least squares with own LU; condition number vs spread; tracking gain |
| E | Control and integration | 3: golden-section + parabolic; 5: PID with Euler vs trapezoid integration |

Everyone writes their own section of the proposal and report and builds their own slides.

## 4. The lab robot

Two-wheel differential-drive robot with a Raspberry Pi.

| Part | Facts |
|---|---|
| Raspberry Pi | Model not stated. Runs all Python. Wi-Fi, headless |
| Adafruit 16-ch PWM/Servo HAT | PCA9685 at I2C **0x40**. Drives the servos and the wheel-motor drivers. One PWM frequency for all channels (about 50 Hz as the lab sets it) |
| 2x REV HD Hex motor with encoder | Wheel drive. Encoders read through `gpiozero.RotaryEncoder` on Pi GPIO. Gearbox ratio not given. The three small green boards on the deck are presumably the drivers [Guessing]; the channel mapping is unknown |
| 2 servos | Free for add-ons (we use SG90 servos for pan and tilt; see the assembly guide) |
| SparkFun Qwiic Mux | TCA9548A at **0x70**, 8 channels, I2C |
| Sensors on the mux | BNO055 IMU (0x28), APDS9960 (0x39), VL53L4CD (0x29). Our tracker uses only the BNO055 |
| Power | Battery, rocker switch, distribution strips, DC-DC converter for the Pi |

**Connecting [Likely current]**
1. Join the lab's hidden Wi-Fi (SSID `mxet_Lab`). The password and the Pi login are in the lab handout. They are not stored here.
2. VS Code with the Python and Remote-SSH extensions. Connect to `pi@192.168.1.2xx` (xx = team number on the robot board). The first connection takes about 5 minutes. If it times out, set `"remote.SSH.useLocalServer": false`.
3. Every session: `source ~/env/bin/activate`. Interpreter: `/home/pi/env/bin/python`. Project folder: `/home/pi/mxet345_project`.
4. For outdoor work the team uses an Ethernet cable laptop to Pi, with a phone hotspot as fallback.

**Lab-provided scripts** (from Canvas, not stored in this repo): `motor_servo_pwm.py` (PCA9685 wrapper), `sensor_module.py` (`Sensor_Thread`), `test_motor.py`, `test_sensor.py`, `test_encoder.py`. The tracker does **not** import them. Do not run `Sensor_Thread` at the same time as the tracker unless it uses the tracker's bus lock (`hardware.real.BUS_LOCK`).

## 5. Still open (as of the last documents)

- Due dates, weights, report and presentation format, library policy (section 1).
- Wheel-driver wiring and PWM-to-motor mapping. Only the `rc_pulse` scheme exists in the code, and the turn is blocked until the `drive.*` config keys are set. `--skip-turn` always works.
- Whether the robot may run outdoors. The team has planned outdoor sessions.
