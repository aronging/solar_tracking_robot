# MXET 345 Final Project: Overview

**Course:** MXET-345: Numerical Methods in Robotics Applications, Texas A&M University (Multidisciplinary Engineering Technology)

**Built from:**
- `Lab Ex - PreLab.md`: pre-lab self-study (Linux command line, Python)
- `Lab Ex - Robot Introduction.md`: robot hardware, connection and bring-up lab, plus the final project guidelines
- `MXET 345_Final Project_V1.md`: the official final project requirements, grading and deliverables

**How to read this document:** anything without a tag comes straight from the three course documents. Anything I added (from manufacturer datasheets, from reading the lab photos, or from engineering inference) carries a tag:
- **[Certain]**: hard evidence (manufacturer spec page, or clearly visible in a lab photo)
- **[Likely]**: strong inference
- **[Guessing]**: filling a gap; confirm with the TA before relying on it

---

## 1. At a Glance

| Item | What the documents say |
|---|---|
| Core requirement | A project that **substantially** depends on numerical methods, and not just in a token way |
| Hardware | **Required.** Use the lab mobile robot or your own hardware system |
| Team size | **3–4 students** |
| Deliverables | (1) Project proposal, (2) final demonstration, (3) written report, (4) slide deck (PPT) for the presentation |
| Mandatory content | A dedicated **numerical methods section** in both the demo and the report: method explanation, location in code, convergence/stability/accuracy analysis, and validating data or plots |
| Grading factors | Complexity and system design · Robustness and accuracy · Report, documentation and analysis · Creativity and innovation |
| Robot rule | **Do not disassemble the robot.** You may only **add** parts |
| Parts | Submit a parts list to your TA **after** the proposal |
| Robot platform | Raspberry Pi differential-drive robot: 2 DC drive motors with encoders, 2 servos, 16-channel PWM HAT, 8-channel I2C mux, ToF / light-gesture / IMU sensors |

---

## 2. What the Documents Do NOT Specify

Get these answers from the instructor or TA early. Several of them change how you plan the work.

1. **No due dates.** Neither the proposal nor the final submission has a date in the documents.
2. **No grading weights.** All four criteria are listed with no percentages.
3. **No report format.** No length, template, citation style or required sections beyond the numerical methods section.
4. **No presentation specifics.** No length, format, or who presents.
5. **No demo conditions.** "Robustness under different conditions" is graded, but the conditions aren't defined.
6. **No proposal format or length.** Only the four required contents are listed.
7. **No budget or parts sourcing rules.** The documents don't say whether the lab supplies parts on your list or whether you buy them.
8. **No servo model or drive gearbox ratio.** Both matter for kinematics (see §6).
9. **No library policy.** The documents don't say whether you must implement the numerical methods yourself or may call NumPy/SciPy solvers. **[Likely]** in a numerical methods course, your own implementations score better, with library calls used as a reference for checking accuracy.
10. **Robot use outside lab hours.** The documents don't say whether the robot can leave the lab or run outdoors.

---

## 3. Project Requirements in Detail

### 3.1 Application Selection
- The topic must **require** numerical methods to solve the problem. The application has to show that the numerical techniques are *essential* to meeting the objectives.
- Using them "only superficially" is explicitly called out as not acceptable.
- **[Likely]** In practice: if the robot would work the same with the numerical method removed or replaced by a lookup or hard-coded value, it's superficial. The method should sit in the robot's working loop (computing joint angles, estimating position, fitting a calibration, tuning a controller) and not be bolted on afterwards.

### 3.2 Hardware Implementation
- A **physical hardware component is mandatory.**
- Options: the lab's mobile robot platform, **or** a hardware system your team builds.
- You must clearly demonstrate the **integration between hardware and computational methods**: the numerical output has to drive physical behavior, or physical measurements have to feed the numerical method.

### 3.3 Numerical Methods and Analysis Section (Report AND Demo)
Both the final demonstration and the written report need a **dedicated** section that does all four of the following:

| Requirement | What it means in practice |
|---|---|
| Explain the method(s) | Theory, equations, and why this method was chosen over alternatives |
| Show where they are in the code | File, function and line references; ideally code excerpts or a flow diagram mapping method to code |
| Analyze performance | **Convergence** (iterations or rate to tolerance), **stability** (behavior under noise, bad initial guesses, step size), **accuracy** (error against ground truth or a reference solution) |
| Validate with data | Plots, tables, experiments; e.g. error vs iteration, error vs step size, measured vs predicted trajectory |

**[Likely]** The fastest way to produce this analysis is to log everything (inputs, intermediate values, outputs, timestamps) to CSV from day one and run comparisons offline. Comparing two methods on the same data (e.g. Newton-Raphson vs bisection, trapezoidal vs Simpson's) gives the convergence and accuracy analysis almost for free.

### 3.4 Team Structure
- **3–4 students** per team.

### 3.5 Deliverables and Sequence

| Stage | Contents | Source |
|---|---|---|
| Pre-lab (self-study) | LinkedIn Learning: *Learning Linux Command Line*, Ch. 2–4 (all videos including challenges and solutions, green checkmarks), and *Learning Python*, "Python Basics" (variables and expressions, functions, conditionals, loops, classes, importing modules) | PreLab |
| Robot Introduction lab | Connect to the Pi, run motor, servo, sensor and encoder test scripts; optional IK and FK practice scripts | Robot Intro |
| **Project proposal** | Title and objectives · hardware system description · numerical methods to be used · expected outcomes and potential challenges | Requirements |
| Parts list | Given to the TA after the proposal | Robot Intro, Guideline 2 |
| **Final submission** | Written report + slide deck (PPT) for the presentation | Requirements |
| **Final demonstration** | Live demo including the numerical methods section | Requirements §3 |

---

## 4. Grading Criteria

No weights are given, so treat all four as significant.

| Criterion | What's evaluated | How to score well |
|---|---|---|
| **1. Complexity of the problem and system design** | Technical challenge; sophistication of the numerical methods; system integration | More than one numerical method working together (e.g. IK + interpolation + PID); real integration of sensors, actuators and computation |
| **2. Robustness and accuracy** | Reliability and performance under different conditions; correctness of results | Test repeatedly and under varied conditions (surfaces, lighting, start positions); report error statistics and not just one good run |
| **3. Report, documentation and analysis** | Clarity, completeness, professionalism; technical explanation; code documentation; data analysis | Commented code, a README, a clear method-to-code map, quality plots, and the full convergence/stability/accuracy analysis |
| **4. Creativity and innovation** | Originality of idea, design approach and implementation | **[Likely]** Going beyond the example drawing robot and the four listed "ideas" gets credit here; reusing them unchanged probably won't |

---

## 5. Rules and Lab Guidelines

From "Guidelines for the Final Project" (Robot Introduction lab):

1. **Don't disassemble the robot.** You can only add parts to the original robot.
2. **Make a parts list** after your proposal and give it to your TA.
3. **Back up your files after every lab** (download to your computer or save to a cloud service). **[Likely]** The Pi's SD card is shared lab equipment and is not a safe place to keep the only copy; use Git or copy the folder off after each session.
4. Suggested project ideas (each paired with a numerical method):
   - **Inverse kinematics**: Newton-Raphson to solve for the joint angles that reach a target end-effector position.
   - **Trajectory generation**: Lagrange polynomial interpolation for smooth, efficient paths for arms and mobile robots.
   - **Sensor-based control**: numerical integration (e.g. trapezoidal rule) to compute speed and position from sensor readings for real-time control.
   - **Control systems**: PID controllers, which rely on numerical calculation of error over time, to make the motors reach and hold desired wheel speeds accurately.

---

## 6. The Robot Platform

### 6.1 Summary
The lab robot is a **two-wheel differential-drive mobile robot** controlled by a **Raspberry Pi**. It has **two DC drive motors** with encoders and **two servos**. It is "capable of locomotion tasks and ready for modifications." Actuators are driven through a 16-channel I2C PWM HAT. Sensors connect through an 8-channel I2C multiplexer (Qwiic), and encoders connect to Pi GPIO.

### 6.2 Component Table

| # | Component | Role | Interface / connection | Key details |
|---|---|---|---|---|
| 1 | **Raspberry Pi** | Main computer; runs all Python code | Wi-Fi (headless) → SSH from VS Code | Host `pi@192.168.1.2xx` (xx = team number on the board); password `mxet`; Python venv at `~/env` (interpreter `/home/pi/env/bin/python`); project folder `/home/pi/mxet345_project`. **[Guessing]** Pi model not stated |
| 2 | **Adafruit 16-Channel PWM/Servo HAT** ("motor controller") | Generates PWM for the drive motors and servos | Sits on the Pi header; I2C | **PCA9685** chip, **16 channels**, I2C address **0x40** (change it in `motor_servo_pwm.py` if yours differs). **[Certain, photo]** 12-bit PWM, 5–6 VDC servo-power barrel jack and screw terminal, address jumpers A0–A5, S/V+/G 3-pin channel headers |
| 3 | **2× REV HD Hex Motor** | Left and right wheel drive | Power via the motor connectors on the deck; commanded by PWM from the HAT | **[Certain, REV spec for the no-gearbox motor]** 12 V DC · 6000 rpm free speed · 0.105 N·m stall torque · 8.5 A stall · 0.4 A free current · 15 W max · 234 g · 37 mm body · integrated encoder, **28 counts/rev at the motor shaft**. **[Likely]** The lab motors have a gearbox (6000 rpm is far too fast to drive wheels directly). The **ratio isn't given**: check the gearbox label or ask the TA |
| 4 | **2× Motor encoders** (built into the HD Hex motors) | Wheel rotation feedback | Pi GPIO via a screw-terminal GPIO breakout (xikentec HDD40), "Left Encoder" and "Right Encoder"; wire colors must match | Read with **`gpiozero.RotaryEncoder`**. Counts at the wheel = 28 × gear ratio per wheel revolution **[Likely]** |
| 5 | **2× Servo motors** | Free actuators for your add-ons (steering a sensor, arm joints, etc.) | Any free PWM channel on the HAT ("To Servos") | **Model, range and torque not specified.** Ask the TA |
| 6 | **SparkFun Qwiic Mux** | Lets several I2C sensors share the bus (including sensors with identical addresses) | Qwiic cable from the Qwiic port on the Pi/HAT; I2C | **TCA9548A**, **8 channels**. If a channel doesn't work, try another |
| 7 | **Adafruit VL53L4CD** | Time-of-flight distance sensor | Mux channel (Qwiic) | Range to obstacles or targets. **[Likely]** short-range (on the order of 1 m) and best indoors |
| 8 | **Adafruit APDS9960** | Proximity, ambient light, RGB color, gesture | Mux channel (Qwiic) | Light intensity, color sensing, gesture input |
| 9 | **Adafruit BNO055** | 9-DOF absolute orientation IMU with sensor fusion | Mux channel (Qwiic) | Heading, pitch/roll, quaternions, angular rate, linear acceleration |
| 10 | **Power and distribution** | Battery input, switching, distribution | n/a | **[Certain, photo]** Rocker power switch, blue screw-terminal distribution strips, red/black Powerpole-style connectors ("To Motors"), a "CPT" DC-DC converter module. **[Likely]** The CPT converter steps the 12 V supply down to 5 V for the Pi |
| 11 | **Three small green driver boards** (visible in Figure 7) | **[Guessing]** Motor driver / H-bridge boards that turn the HAT's PWM signals into motor power | Between the HAT channels and the motors | Not described in the lab document. Ask the TA what they are and how the PWM channels map onto them (direction + speed, or two PWM per motor) |

**Sensor libraries (from lab links):** Adafruit CircuitPython drivers: `adafruit_tca9548a`, `adafruit_vl53l4cd`, `adafruit_apds9960`, `adafruit_bno055`; the PCA9685 driver is used in `motor_servo_pwm.py`. Encoders use `gpiozero`.

### 6.3 Default I2C Addresses
Not in the course documents; these are the standard datasheet defaults. **[Likely]**

| Device | Default address | Notes |
|---|---|---|
| PCA9685 PWM HAT | 0x40 | Confirmed by the lab doc as the expected address |
| TCA9548A mux | 0x70 | 0x70 is also the PCA9685's power-on "all-call" address. The lab setup works as shipped and **[Likely]** Adafruit's PCA9685 driver clears all-call when it initializes, so don't re-address the mux; initialize the PCA9685 before touching the mux in code |
| VL53L4CD | 0x29 | Behind the mux |
| APDS9960 | 0x39 | Behind the mux |
| BNO055 | 0x28 (alt 0x29) | Behind the mux |

**[Certain] Correction (Oct 27):** a mux channel does **not** avoid every address clash. The TCA9548A connects the selected channel to the upstream bus, so the PCA9685 HAT (0x40) and the mux itself (0x70) are visible on every channel. An added sensor on a mux channel is safe only if its address is not 0x40 or 0x70 (the INA219 defaults to 0x40 and must be moved to 0x41). Sensors on *different* mux channels can share an address, as long as only one channel is enabled at a time. Run `i2cdetect -y 1` on the Pi to see what's on the bus.

### 6.4 System Architecture

```
                        Laptop (VS Code + Remote-SSH)
                                    │  Wi-Fi: hidden SSID "mxet_Lab"
                                    ▼
┌───────────────────────────── Raspberry Pi ─────────────────────────────┐
│  Python venv (~/env) · project: /home/pi/mxet345_project               │
│                                                                        │
│  motor_servo_pwm.py ──I2C──► PCA9685 16-ch PWM HAT (0x40)              │
│                                ├─ ch a,b… ─► motor drivers ─► L/R HD Hex│
│                                └─ ch x,y   ─► Servo 1, Servo 2         │
│                                                                        │
│  sensor_module.py  ──I2C (Qwiic)──► TCA9548A mux (8 ch)                │
│   (Sensor_Thread)                    ├─ ch i ─► VL53L4CD (ToF)          │
│                                      ├─ ch j ─► APDS9960 (light/RGB)    │
│                                      └─ ch k ─► BNO055 (IMU)            │
│                                                                        │
│  test_encoder.py ──GPIO (gpiozero RotaryEncoder)──► L/R motor encoders │
└────────────────────────────────────────────────────────────────────────┘
          Power: battery → switch → distribution → motors / DC-DC → Pi
```

---

## 7. How the Robot Works

### 7.1 Connecting to the Robot (workflow)
1. **Install VS Code** plus the extensions **Python** (Microsoft) and **Remote - SSH** (Microsoft). Restart VS Code.
2. **Join the lab Wi-Fi:** it's a hidden network. Choose "Hidden," SSID `mxet_Lab`, password `mxetlab006`. This puts your laptop on the same network as the Pi (headless operation).
3. **Power on the robot** and SSH in: Remote Explorer → "+" next to SSH → `ssh pi@192.168.1.2xx` → save to your `~/.ssh/config` → Connect → platform **Linux** → password `mxet`. The **first connection takes about 5 minutes** while the VS Code server installs on the Pi.
4. **If the connection times out:** Settings → search `useLocalServer` → set `"remote.SSH.useLocalServer": false`.
5. **Every session, before running any script:** `source ~/env/bin/activate`. All the Python packages live in this virtual environment.
6. **Project folder:** `mkdir mxet345_project && cd mxet345_project`, then open `/home/pi/mxet345_project` as the workspace folder.
7. **Point VS Code at the venv:** install Python and Pylance; Ctrl+Shift+P → *Python: Select Interpreter* → *Enter interpreter path* → *Find* → `/home/pi/env/bin/python`.
8. **Copy in the Canvas scripts:** `touch` each file and paste in the code, or drag and drop the files into the VS Code explorer.

### 7.2 Provided Software (from Canvas)

| Script | Purpose |
|---|---|
| `motor_servo_pwm.py` | Wrapper around the PCA9685 (`self.pca = PCA9685(i2c_bus, address=0x40)`); provides motor and servo control functions |
| `test_motor.py` | Imports the wrapper and spins the DC motors and servos. **Edit the channel numbers to match your wiring** |
| `sensor_module.py` | Defines **`Sensor_Thread`**, a background thread that continuously reads the sensors and stores the latest values. Add new sensor data by declaring attributes in **`__init__`** and assigning them in **`_read_data`** |
| `test_sensor.py` | Imports the sensor module and prints readings. **Edit the mux channel numbers to match your wiring** |
| Per-sensor test scripts | Examples for each sensor; use with the sensor docs for extra features |
| `test_encoder.py` | Reads both encoders using `gpiozero.RotaryEncoder` |
| *(optional, you write)* `inverse_kinematics.py` | Input: forward velocity v (m/s) and rotational speed ω (rad/s). Output: motor commands |
| *(optional, you write)* `forward_kinematics.py` | Input: encoder readings. Output: motor rev/s, then robot v (m/s) and ω (rad/s) |

The two optional scripts are explicitly flagged as "helpful when you build your final project."

### 7.3 Actuation Path
Python sets a duty cycle on a PCA9685 channel over I2C. The HAT outputs a hardware-timed PWM signal on that channel:
- **Servos:** the PWM pulse width sets the servo angle. Plug into any free channel.
- **Drive motors:** the PWM goes through the motor driver stage to the HD Hex motors. Motor power plugs into the "To Motors" connectors on the deck.

**Safety:** put the robot **off the ground** before running `test_motor.py`.

### 7.4 Sensing Path
- **I2C sensors:** Python selects a mux channel (TCA9548A), then talks to the sensor on that channel. `Sensor_Thread` does this continuously in the background, so your main control loop just reads the latest stored values without blocking.
- A sensor's LED lights when it's connected correctly.
- **Encoders:** quadrature signals go to Pi GPIO pins, and `gpiozero.RotaryEncoder` counts steps in software. To wire them: **power off the Pi**, lift the PWM HAT off, connect the encoders to the GPIO breakout (matching cable colors), then reseat the HAT.

### 7.5 Kinematics (Differential Drive)
You measure the wheel radius *r* and the track width *L* (distance between the wheels), as the optional practice instructs.

**Inverse kinematics** (robot command → wheel speeds):

```
ω_R = (v + ω·L/2) / r        [rad/s]
ω_L = (v − ω·L/2) / r        [rad/s]
wheel rev/s = ω_wheel / (2π)
```

Then convert wheel rev/s to a PWM command. **[Likely]** The PWM-to-speed relationship isn't perfectly linear and differs between the two motors. Measure it with the encoders and fit a curve (least squares or polynomial). That fit is a legitimate numerical-methods piece in its own right.

**Forward kinematics** (encoders → robot motion):

```
wheel rev/s = Δcounts / (CPR_motor × gear_ratio × Δt)
v = r·(ω_R + ω_L) / 2        [m/s]
ω = r·(ω_R − ω_L) / L        [rad/s]
```

Integrating v and ω over time (Euler, trapezoidal, RK) gives the robot's pose (x, y, θ), i.e. odometry. The BNO055 heading provides an independent check on θ.

**Encoder caveats:**
- **[Likely]** REV's "28 counts/rev" counts every quadrature edge. `gpiozero.RotaryEncoder` counts one *step* per full quadrature cycle, so expect about 7 steps per motor revolution, multiplied by the gear ratio at the wheel. **Calibrate by turning a wheel exactly one revolution and reading the count.**
- **[Likely]** `RotaryEncoder` defaults to `max_steps=16` and clamps `steps` at ±16 unless that's changed. Check how `test_encoder.py` creates the encoder; `max_steps=0` gives an unbounded count.
- **[Guessing]** Python GPIO callbacks can miss edges at high motor speed. If counts look low at speed, compare against a slow hand-turned revolution.

---

## 8. Numerical Methods: Where They Fit on This Robot

The four "ideas" from the lab guidelines and the example project, mapped to the hardware and to the analysis the report requires:

| Method (from course docs) | Where it lives on the robot | What to analyze (convergence / stability / accuracy) |
|---|---|---|
| **Newton-Raphson for inverse kinematics** | Joint angles for an add-on arm driven by the 2 servos | Iterations to tolerance; sensitivity to the initial guess; failure near singularities or unreachable targets; position error at the pen or end-effector |
| **Lagrange polynomial interpolation for trajectory generation** | Smooth paths for the base or an arm through waypoints | Interpolation error vs number of nodes; Runge oscillation at high order (compare against piecewise or spline); measured vs planned path |
| **Trapezoidal-rule numerical integration for sensor-based control** | Encoder or IMU rates → distance, position, heading | Drift over time; step-size (sample-rate) effects; comparison with Euler or Simpson's; error against a measured ground-truth distance |
| **PID control** (numerical integral and derivative of error) | Wheel speed control from the encoders; heading control from the BNO055 | Step response (rise time, overshoot, settling); stability across gains; steady-state error; effect of the integration and differentiation scheme and the loop rate |
| *Example project:* IK + interpolation / trajectory optimization | Drawing robot (base + 2-link arm + pen) | Trajectory accuracy and convergence (explicitly called out) |

**[Likely]** A strong project chains several of these together. For example, interpolation plans the path, IK turns it into joint or wheel commands, PID tracks those commands, and integrated odometry closes the loop. That hits "complexity" and "system integration" directly.

---

## 9. The Example Project, Unpacked: Drawing Robot System

| Element | Description | Requirement it satisfies |
|---|---|---|
| Platform | Lab mobile robot | Hardware implementation |
| Add-on | Two-link robotic arm with a motor at each joint and a pen at the end-effector | "Only add parts" rule; integration |
| Task | Plan a trajectory so the pen draws shapes, letters or patterns | Clear, measurable objective |
| Numerical methods | IK, interpolation or trajectory optimization, used to compute joint angles at each time step and to determine the base motion | Methods are *essential*, not superficial |
| Demo | Coordinated robot + arm control producing accurate drawings | Robustness and accuracy |
| Analysis | Trajectory accuracy and convergence | Numerical methods analysis section |

**[Likely]** The robot's two servos are the obvious actuators for a two-link arm like this. This example is the template the course gives for "the right level" of a project, so a project noticeably simpler than this will probably score low on complexity.

---

## 10. Checklists

### 10.1 Proposal Must Include
- [ ] Project title and objectives
- [ ] Description of the hardware system (lab robot and the parts you'll add)
- [ ] Numerical methods to be used (and why they're essential)
- [ ] Expected outcomes and potential challenges
- [ ] *(Next step)* Parts list to the TA

### 10.2 Final Submission Must Include
- [ ] Working physical hardware demo
- [ ] Dedicated numerical methods section in the **demo**
- [ ] Written **report** with a dedicated numerical methods section:
  - [ ] Method explanation
  - [ ] Where and how each method is implemented in the code
  - [ ] Convergence, stability and accuracy analysis
  - [ ] Supporting data, plots and experiments
- [ ] Code documentation
- [ ] **Slides (PPT)** for the presentation

### 10.3 Robot Bring-Up Checklist
- [ ] Pre-lab LinkedIn Learning courses done (green checks)
- [ ] VS Code + Python + Remote-SSH + Pylance installed
- [ ] Connected to `mxet_Lab` (hidden network)
- [ ] SSH into `pi@192.168.1.2xx` works
- [ ] `source ~/env/bin/activate` (every session)
- [ ] Interpreter set to `/home/pi/env/bin/python`
- [ ] Canvas scripts copied into `/home/pi/mxet345_project`
- [ ] PCA9685 address confirmed (0x40)
- [ ] Motor and servo channel numbers updated in `test_motor.py`; motors run with the robot off the ground
- [ ] Sensors on the mux; channel numbers updated in `test_sensor.py`; readings print
- [ ] Encoders wired (with the Pi powered off); `test_encoder.py` counts when the wheels are turned by hand
- [ ] Wheel diameter and track width measured
- [ ] *(Optional)* `inverse_kinematics.py` and `forward_kinematics.py` written and tested
- [ ] Files backed up off the Pi

---

## 11. Gotchas and Safety Notes
- **Robot off the ground** before running motor tests.
- **Power off the Pi** before lifting the PWM HAT to wire the encoders, and match the wire colors.
- **Activate the venv** every session, or the imports will fail.
- **Channel numbers** in `test_motor.py` and `test_sensor.py` must match your actual wiring.
- **PCA9685 address** must match the `motor_servo_pwm.py` line if your board isn't at 0x40.
- **First SSH connection takes about 5 minutes.** Don't kill it.
- **Timeouts:** set `remote.SSH.useLocalServer` to `false`.
- **Dead mux channel:** move the sensor to another channel.
- **Never disassemble** the robot; only add parts.
- **Back up after every lab.**

---

## 12. Questions to Ask the TA / Instructor
1. When are the proposal, demo, report and slides due?
2. How are the four grading criteria weighted?
3. Is there a report template, page limit or required structure?
4. Presentation length and format?
5. Must the numerical methods be implemented from scratch, or are NumPy/SciPy solvers allowed?
6. What is the drive gearbox ratio, and what servo model is installed (range, torque)?
7. What are the three green boards on the deck, and how do the PWM channels map to motor speed and direction?
8. Who pays for or supplies the parts on the parts list, and what's the turnaround?
9. Can the robot be used outside lab hours, taken home, or run outdoors?
10. What are the "different conditions" for the robustness evaluation?

---

## Sources
- Course documents: `Lab Ex - PreLab (1).pdf`, `Lab Ex - Robot Introduction (1).pdf`, `MXET 345_Final Project_V1 (1).docx`
- [REV HD Hex Motor product page (REV-41-1291)](https://www.revrobotics.com/REV-41-1291): motor specifications
- Links embedded in the lab document: [Adafruit 16-Channel PWM/Servo HAT](https://learn.adafruit.com/adafruit-16-channel-pwm-servo-hat-for-raspberry-pi/overview) · [REV HD Hex Motor docs](https://docs.revrobotics.com/duo-build/motion/motors/hd-hex-motor) · [REV motor encoders](https://docs.revrobotics.com/duo-control/sensors/encoders/motor-based-encoders) · [TCA9548A mux library](https://docs.circuitpython.org/projects/tca9548a/en/latest/) · [VL53L4CD library](https://docs.circuitpython.org/projects/vl53l4cd/en/latest/) · [APDS9960 library](https://docs.circuitpython.org/projects/apds9960/en/latest/) · [BNO055 library](https://docs.circuitpython.org/projects/bno055/en/latest/) · [gpiozero RotaryEncoder](https://gpiozero.readthedocs.io/en/stable/api_input.html#rotaryencoder)
