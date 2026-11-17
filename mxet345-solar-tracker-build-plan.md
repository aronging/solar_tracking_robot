# MXET 345 Solar Tracker — Build Plan

**Written:** Oct 27, 2026 · **Window:** 4 weeks (Oct 27 – Nov 23) · **Team:** 5 (roles A-E, defined in `mxet345-solar-tracker-breakdown.md`)
**Design and methods:** `mxet345-solar-tracker-plan.md` · **Parts:** `mxet345-solar-tracker-BOM.md` / `.xlsx`
**Confidence tags:** [Certain] / [Likely] / [Guessing]. Dates assume the final deliverables are due around Nov 24 [Guessing]; shift everything once the TA gives due dates.

## Scope in one paragraph
The lab robot carries a small 6 V solar panel on a printed pan-tilt mount driven by the robot's two servos. At the start of a session the wheels turn the robot to face south (PID on IMU heading). The Pi predicts the sun's position from UTC time (solar model with Kepler's equation), points the panel, finds the peak with a golden-section search, and every 10-15 min scans around the prediction and fits a cosine curve to the measured short-circuit current (least squares with our own LU). The fitted peak corrects the robot's heading and tilt offsets. Five graded methods, one panel, ~$30 of core parts, ~5-6 h per person per week [Guessing].

## Budget
- **Money:** core purchases ≈ $31 + shipping; conditional items only if a check fails (see BOM)
- **Time:** 5 people × ~5-6 h/week × 4 weeks ≈ 100-120 team-hours [Guessing]. Roughly 20% build, 35% code, 15% outdoor/indoor testing, 30% analysis + report + slides
- **Rule:** nothing is debugged for the first time outdoors. Every piece runs on the bench or under a lamp first

## Week 1 (Oct 27 – Nov 2): order, propose, start code
| Owner | Task | Done when |
|---|---|---|
| B | Ask the TA the six questions (breakdown file); order parts **by Wed Oct 28** | Parts ordered; answers recorded |
| All | Write and submit the proposal (each writes their own subsystem section) | Proposal submitted |
| A | CAD: panel frame + tilt yoke, pan plate on the bearing, mast/clamp to existing robot holes, tilt protractor. Measure robot mounting holes in lab | CAD ready to print once bearing dimensions are confirmed |
| B | Connect laptop ↔ Pi over Ethernet; check network time; `i2cdetect -y 1` baseline; find out what powers the HAT servo rail | SSH over Ethernet works; bus map recorded |
| C | Solar model (Julian date → Kepler → az/el) with fixed-point and Newton solvers; compare to NOAA at 10 times | Error < 0.5° vs NOAA |
| D | Own LU solver + normal-equation least squares; test on synthetic cosine data with noise | Recovers θ* on synthetic data |
| E | Coarse-turn PID on the robot in the lab (BNO055 heading, wrap to ±180°, anti-windup) | Robot turns to a commanded heading within a few degrees |

**Gate:** proposal in, parts ordered, solar model validated, Pi reachable over Ethernet.

## Week 2 (Nov 3 – 9): build, wire, calibrate, lamp test
| Owner | Task | Done when |
|---|---|---|
| A | Print in PETG/ASA, assemble the pan-tilt mount, mount on robot (no disassembly), strain relief for panel leads and Ethernet cable | Mount moves freely through both ranges; panel never shaded by the robot |
| B | Bridge INA219 A0 (→ 0x41); solder leads to panel pads; wire for short circuit (Panel+ → Vin+, Vin− → GND, Panel− → GND); 16 V / 400 mA range; add INA219 to `Sensor_Thread`; CSV logger | Isc logs at a steady rate; matches a multimeter within a few % |
| B + A | Servo calibration: step each servo through its range, measure angle with the printed protractor or a phone inclinometer, up and down sweeps; least-squares fit PWM → angle | Fit + residual plot + hysteresis number for both servos |
| D | Cosine fit on the real panel under a lamp; θ* scatter vs spread | Fit finds the lamp to a few degrees |
| E | Golden-section + parabolic acquisition under the lamp; main loop with ACQUIRE → TRACK → HOLD → PARK | Robot finds the lamp from a cold start |
| C | Kepler stress test (e = 0.5, 0.9); optional sunrise/sunset bisection vs false position; pointing geometry check with E (az/el → pan/tilt) | Convergence plots done |

**Gate:** full indoor run under a lamp: acquire → track → refine scans → logs. Fix servo power now if servo moves reset the Pi.

## Week 3 (Nov 10 – 16): outdoor sessions
Pick the two clearest days from the forecast. Target window ~10:30 am – 1:30 pm CST around solar noon (~12:10 pm CST [Likely]).

**Session 1 (~2 h): calibration + first tracking**
1. Set up on flat pavement in open sun; Ethernet to the laptop; start `tmux`; confirm UTC time
2. Static logging: panel fixed, 5-10 min of Isc → noise model
3. Coarse turn to south (after BNO055 shows calibrated)
4. Acquire, then track with refinement scans at ±10°, ±15°, ±20° spreads
5. Park at the fixed reference orientation (south, ~45° tilt) for ~10 s every ~15 min
6. Optional: log the APDS9960 once to see whether it saturates
7. Copy all logs off the Pi before leaving

**Session 2 (~2-3 h): full tracking run** at the spread chosen from session 1, with the same parked fixed-panel checks. This is the run the gain number and the pointing-error plots come from.

Meanwhile: D builds the analysis scripts from session 1 data; C validates the model against session timestamps; E fixes anything session 1 exposed.

**Gate:** two sessions of clean logs in hand.

## Week 4 (Nov 17 – 23): analysis, report, slides, demo
- Backup outdoor session early in the week only if Week 3 lost a session to weather
- Each owner produces their method's analysis (convergence, stability, accuracy + plots) and a method-to-code map (file, function, lines)
- D: tracking gain vs the virtual fixed panel, checked against the parked samples
- Report + slides assembled by ~Nov 21; README and code comments
- Demo rehearsal: indoor lamp moved by hand (Stages 3-4 live), plus outdoor data and video for Stages 1-2

## Build procedures

### Mechanical (A)
1. Panel frame with a lip to hold the 66 × 113 mm panel (no mounting holes on the panel); VHB tape if needed
2. Tilt axis through the frame + panel centre of mass; tilt servo horn on one side, printed pin on the other; tilt range centred near 60° from horizontal (sun elevation 23-44° in the window)
3. Tilt assembly on a pan plate; pan plate rides on the turntable bearing; pan servo horn drives the plate
4. Mast/clamp bolts to existing robot holes; height so the robot never shades the panel at 23° sun elevation
5. Hard stops on pan; route panel leads through the centre, with slack for the pan range

### Electrical (B)
1. Bridge the INA219 A0 jumper → address 0x41
2. Solder 22 AWG leads to the panel pads; strain-relieve at the frame
3. Panel+ → Vin+; Vin− → GND; Panel− → GND (short circuit through the 0.1 Ω shunt)
4. INA219 → free mux channel via Qwiic cable
5. Servos → two free HAT channels (S/V+/G)
6. In code: initialize the PCA9685 before the mux; INA219 at 0x41, 16 V / 400 mA range
7. If the Pi resets when servos move: separate 5-6 V supply for the HAT servo rail + 470-1000 µF capacitor

### Software (C, D, E)
- Repo with pure-function algorithm modules (solar model, LU/least squares, golden-section, PID) testable on a laptop, plus one hardware module (servos, INA219, BNO055)
- CSV log every cycle: UTC time, predicted az/el, pan/tilt commands, Isc, bus V, BNO055 heading + calibration status, state
- Run on the Pi inside `tmux`; back up the repo after every lab (course rule)

## What gets handed in, and where it comes from
| Deliverable | Source |
|---|---|
| Proposal | Week 1, all |
| Parts list to TA | BOM file, after the proposal |
| Numerical methods section | One sub-section per core method, written by its owner |
| Robustness/accuracy results | Session 1 + 2 logs; lamp test logs |
| Demo | Indoor lamp run + outdoor data/video |
| Report + slides | Week 4 |
