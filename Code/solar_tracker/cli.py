"""Command line: ``python -m solar_tracker <command>`` (spec section 12).

Global options go BEFORE the command: --config, --set, --hardware, --log-dir, -v.
Ctrl-C always parks cleanly.
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .clock import SystemClock
from .config import CODE_DIR, ConfigError, load_config
from .logging_ import SessionLogger
from .supervisor import Options, Supervisor


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="solar_tracker", description="MXET 345 solar tracker")
    p.add_argument("--config", action="append", default=[], help="extra TOML file (site overrides)")
    p.add_argument("--set", action="append", default=[], metavar="section.key=value")
    p.add_argument("--hardware", choices=["real", "sim"], help="override hardware.backend")
    p.add_argument("--log-dir")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("preflight", help="hardware checks only")
    sub.add_parser("park", help="move the servos to the park pose and stop")

    c = sub.add_parser("calibrate-servo", help="interactive servo calibration -> servo_cal.csv")
    c.add_argument("--servo", choices=["pan", "tilt"], required=True)
    c.add_argument("--step-us", type=float, default=100.0, help="pulse step (multiple of 10 us)")
    c.add_argument("--min-us", type=float)
    c.add_argument("--max-us", type=float)
    c.add_argument("--check-sign", action="store_true", help="just move to -20, 0, +20 deg")

    c = sub.add_parser("static-log", help="hold a pose and log Isc at 10 Hz (noise model)")
    c.add_argument("--minutes", type=float, default=10.0)
    c.add_argument("--pan", type=float, default=0.0)
    c.add_argument("--tilt", type=float, default=30.0)

    c = sub.add_parser("coarse-turn", help="PID turn to a true heading")
    c.add_argument("--robot-on-ground", action="store_true")
    c.add_argument("--bench", action="store_true", help="wheels disabled, virtual plant")
    c.add_argument("--integral", choices=["euler", "trapezoid", "simpson"])
    c.add_argument("--target", type=float, help="true heading, deg")

    c = sub.add_parser("acquire", help="acquire only")
    c.add_argument("--mode", choices=["sun", "lamp"], default="sun")
    c.add_argument("--ack-clock", action="store_true")

    c = sub.add_parser("lamp", help="indoor demo: acquire, monitor, re-acquire on a lamp")
    c.add_argument("--seconds", type=float, default=300.0)

    c = sub.add_parser("track", help="full session")
    c.add_argument("--mode", choices=["sun"], default="sun")
    c.add_argument("--skip-turn", action="store_true")
    c.add_argument("--robot-on-ground", action="store_true")
    c.add_argument("--ack-clock", action="store_true")
    c.add_argument("--k-mA", type=float, dest="k_mA")
    c.add_argument("--duration-min", type=float)
    c.add_argument("--spread", type=float, help="refine scan spread, deg (10..20)")

    c = sub.add_parser("analyze", help="run the analysis scripts on a log folder")
    c.add_argument("log_dir")

    c = sub.add_parser("sim-day", help="simulated full session with injected offsets")
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--true-az-offset", type=float, default=7.0)
    c.add_argument("--true-el-offset", type=float, default=-3.0)
    c.add_argument("--clouds", default="", help="t0_s:t1_s:factor[,...] from session start")
    c.add_argument("--hours", type=float, default=6.0)
    c.add_argument("--start", default="2026-11-16T15:00", help="UTC start, ISO format")
    c.add_argument("--heading", type=float, help="initial true heading (default random)")
    return p


def parse_clouds(text: str):
    return [tuple(float(x) for x in item.split(":")) for item in text.split(",") if item.strip()]


# log file each analysis script needs, and how it takes it
ANALYSIS = [("plot_session.py", "cycle.csv", "dir"), ("tracking_gain.py", "cycle.csv", "dir"),
            ("offset_convergence.py", "scan_fit.csv", "dir"),
            ("prediction_vs_measured.py", "scan_fit.csv", "dir"),
            ("golden_convergence.py", "acquire.csv", "file"),
            ("cosine_fit_study.py", "scan_fit.csv", "file"), ("pid_study.py", "turn.csv", "file"),
            ("noise_model.py", "static.csv", "file"), ("fit_servo_cal.py", "servo_cal.csv", "pos")]


def analyze(log_dir: str) -> int:
    d = Path(log_dir)
    if not d.is_dir():
        print("not a log folder: %s" % d)
        return 2
    rc = 0
    for script, needs, how in ANALYSIS:
        if not (d / needs).exists():
            continue
        target = str(d if how == "dir" else d / needs)
        cmd = [sys.executable, str(CODE_DIR / "analysis" / script)] + \
              ([target] if how == "pos" else ["--log", target]) + \
              ["--out", str(d / "analysis_out" / script[:-3])]
        print(">>", " ".join(cmd))
        rc |= subprocess.call(cmd)
    return rc


def calibrate_servo(sup: Supervisor, args) -> None:
    """Step one servo through its pulse range up then down; the operator types the angle
    read from a protractor / phone inclinometer. Blank = skip the point, q = stop."""
    s, servos = sup.cfg.servo, sup.rig.servos
    sup.set_state("CALIBRATE")
    if args.check_sign:
        for a in (-20.0, 0.0, 20.0, 0.0):
            sup.move(a if args.servo == "pan" else 0.0, a if args.servo == "tilt" else 0.0)
            input("%s at %+.0f deg. Positive pan must turn the panel clockwise seen from above; "
                  "positive tilt must lift the normal. Enter to continue..." % (args.servo, a))
        return
    span = s.limit_deg / s.deg_per_us
    lo = args.min_us if args.min_us is not None else 10.0 * int((s.center_us - span) / 10.0 + 1)
    hi = args.max_us if args.max_us is not None else 10.0 * int((s.center_us + span) / 10.0)
    n = int((hi - lo) / args.step_us)
    up = [lo + i * args.step_us for i in range(n + 1)]
    sup.move(0.0, 0.0)
    for direction, pulses in (("up", up), ("down", up[::-1])):
        servos.write_pulse(args.servo, pulses[0] + (-30.0 if direction == "up" else 30.0))
        for pulse in pulses:                     # always approach from the sweep direction
            sup.check_stop()
            servos.write_pulse(args.servo, pulse)
            sup.clock.sleep(s.settle_s)
            text = input("%s %s %.0f us -> measured angle (deg, blank=skip, q=quit): "
                         % (args.servo, direction, pulse)).strip()
            if text.lower() == "q":
                return
            if text:
                sup.log.row("servo_cal.csv", {"servo": args.servo, "direction": direction,
                                              "pulse_us": pulse, "measured_deg": float(text)})
    print("Now run: python analysis/fit_servo_cal.py %s" % (sup.log.dir / "servo_cal.csv"))


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "analyze":
        return analyze(args.log_dir)
    overrides = list(args.set)
    if args.hardware or args.command == "sim-day":
        overrides.append('hardware.backend="%s"' % ("sim" if args.command == "sim-day" else args.hardware))
    if getattr(args, "integral", None):
        overrides.append('align.integral_mode="%s"' % args.integral)
    if getattr(args, "spread", None):
        overrides.append("refine.spread_deg=%s" % args.spread)
    try:
        cfg = load_config(args.config, overrides)
        sim = cfg.hardware.backend == "sim"
        opts = Options(command=args.command, argv=argv if argv is not None else sys.argv[1:],
                       mode="lamp" if args.command == "lamp" else getattr(args, "mode", "sun"),
                       skip_turn=getattr(args, "skip_turn", False),
                       robot_on_ground=getattr(args, "robot_on_ground", False),
                       bench=getattr(args, "bench", False),
                       ack_clock=getattr(args, "ack_clock", False),
                       k_mA=getattr(args, "k_mA", None),
                       target_heading_deg=getattr(args, "target", None))
        seed = getattr(args, "seed", 0)
        if sim:
            from .hardware.sim import SimParams, make_sim_rig
            params = SimParams(seed=seed)
            if args.command == "sim-day":
                params.start_utc = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
                params.true_az_offset_deg, params.true_el_offset_deg = args.true_az_offset, args.true_el_offset
                params.clouds = parse_clouds(args.clouds)
                params.heading0_true_deg = args.heading
                params.cal_gain = 1.02
                opts.duration_s = args.hours * 3600.0
            elif opts.mode == "lamp":
                params.lamp = (150.0, 35.0)
                params.heading0_true_deg = 180.0
            rig = make_sim_rig(cfg, params)
        else:
            if args.command == "track" and not (opts.skip_turn or opts.robot_on_ground):
                raise ConfigError("track drives the wheels for the coarse turn: pass "
                                  "--robot-on-ground, or --skip-turn after aligning by hand")
            from .hardware.real import make_real_rig
            rig = make_real_rig(cfg)
    except ConfigError as exc:
        print("CONFIG ERROR: %s" % exc, file=sys.stderr)
        return 2

    log_root = args.log_dir or str(CODE_DIR / cfg.runtime.log_dir)
    log = SessionLogger(log_root, args.command, rig.clock, fsync=isinstance(rig.clock, SystemClock),
                        verbose=args.verbose)
    sup = Supervisor(cfg, rig, log, opts, random.Random(seed) if sim else None)
    cmd = args.command
    if cmd == "track" and args.duration_min:
        opts.duration_s = args.duration_min * 60.0
    if cmd == "lamp":
        opts.duration_s = args.seconds
    body = {
        "preflight": sup.only_preflight, "park": sup.park, "coarse-turn": sup.only_turn,
        "acquire": sup.only_acquire, "lamp": sup.session_lamp, "track": sup.session_sun,
        "sim-day": sup.session_sun,
        "static-log": lambda: sup.static_log(getattr(args, "minutes", 0), getattr(args, "pan", 0),
                                             getattr(args, "tilt", 0)),
        "calibrate-servo": lambda: calibrate_servo(sup, args),
    }[cmd]
    code = sup.run(body)
    print("log folder: %s" % log.dir)
    print("exit: %s" % sup.exit_reason)
    if sim and cmd == "sim-day":
        p = rig.sim.p
        print("az_offset learned %+.2f (true %+.2f) | el_offset learned %+.2f (true %+.2f)"
              % (sup.az.value_deg, p.true_az_offset_deg, sup.el.value_deg, p.true_el_offset_deg))
    return code
