"""Closed-loop simulation tests (spec 14.2). Everything runs on the virtual SimClock."""
import csv
import json
import math
import random
import signal

import pytest

from solar_tracker.config import load_config
from solar_tracker.geometry import angdiff
from solar_tracker.hardware.sim import SimParams, make_sim_rig
from solar_tracker.logging_ import SessionLogger
from solar_tracker.supervisor import Options, Supervisor


def run(tmp_path, params, opts=None, on_tick=None, body="session_sun", overrides=()):
    cfg = load_config(overrides=['hardware.backend="sim"', *overrides])
    rig = make_sim_rig(cfg, params)
    log = SessionLogger(str(tmp_path), "test", rig.clock, fsync=False)
    sup = Supervisor(cfg, rig, log, opts or Options(), random.Random(params.seed), on_tick)
    code = sup.run(getattr(sup, body))
    return sup, rig, log, code


def rows(log, name):
    with open(log.dir / name, newline="") as fh:
        return list(csv.DictReader(fh))


def events(log):
    return [json.loads(line) for line in open(log.dir / "events.jsonl")]


def clear_day(**kw):
    return SimParams(seed=3, true_az_offset_deg=7.0, true_el_offset_deg=-3.0, cal_gain=1.02,
                     backlash_deg=1.5, noise_mA=0.4, **kw)


def test_clear_day_learns_offsets(tmp_path):
    errs = []
    sup, rig, log, code = run(tmp_path, clear_day(), Options(duration_s=6 * 3600),
                              on_tick=lambda s: errs.append((s.clock.monotonic(),
                                                             s.rig.sim.pointing_error_deg())))
    assert code == 0 and sup.exit_reason == "duration reached"
    assert abs(sup.az.value_deg - 7.0) < 1.0 and abs(sup.el.value_deg + 3.0) < 1.0
    cycle, fits, scan = rows(log, "cycle.csv"), rows(log, "scan_fit.csv"), rows(log, "scan.csv")
    t_track0 = float(cycle[0]["t_mono_s"])
    t_first_scan = t_track0 + 720 + 60
    after = [e for t, e in errs if t > t_first_scan]
    assert math.sqrt(sum(e * e for e in after) / len(after)) < 2.0
    assert rig.sim.turn_commands and max(t for t, _ in rig.sim.turn_commands) < t_track0
    assert len(fits) == 2 * sup._scan_id and sup._scan_id >= 25
    assert sum(r["accepted"] == "true" for r in fits) > 0.8 * len(fits)
    assert len(scan) == len(fits) * (7 + 2)                      # every scan point logged
    assert len(rows(log, "fixed_check.csv")) >= 10
    session = json.load(open(log.dir / "session.json"))
    assert session["sim_truth"]["true_az_offset_deg"] == 7.0 and session["k_clear_mA"] > 0


def test_cloud_enters_hold_and_protects_offsets(tmp_path):
    t0, t1 = 5000.0, 6200.0                                      # 20-minute cloud, factor 0.3
    sup, rig, log, code = run(tmp_path, clear_day(clouds=[(t0, t1, 0.3)]),
                              Options(duration_s=3 * 3600))
    assert code == 0
    states = [(e["frm"], e["to"]) for e in events(log) if e["event"] == "state"]
    assert ("TRACK", "HOLD") in states and states.index(("TRACK", "HOLD")) < len(states) - 1
    assert sup.state == "DONE" and ("HOLD", "TRACK") in states or ("ACQUIRE", "TRACK") in states
    cycle = rows(log, "cycle.csv")
    hold = [r for r in cycle if r["state"] == "HOLD"]
    assert hold and all(t0 - 5 <= float(r["t_mono_s"]) <= t1 + 30 for r in hold)
    before = [r for r in cycle if float(r["t_mono_s"]) < t0][-1]
    during = [r for r in cycle if t0 + 10 < float(r["t_mono_s"]) < t1]
    assert all(r["az_offset_deg"] == during[0]["az_offset_deg"] for r in during)   # frozen in HOLD
    after = [r for r in cycle if float(r["t_mono_s"]) > t1 + 400][0]
    for key in ("az_offset_deg", "el_offset_deg"):
        assert abs(float(after[key]) - float(before[key])) < 1.0


def test_bad_start_bootstrap_and_fault(tmp_path):
    ok = SimParams(seed=5, heading0_true_deg=180.0, imu_bias_deg=25.0)     # believed heading 25 deg off
    sup, _, log, code = run(tmp_path / "a", ok, Options(skip_turn=True, duration_s=300))
    assert code == 0 and abs(sup.az.value_deg + 25.0) < 2.0
    bad = SimParams(seed=5, heading0_true_deg=180.0, imu_bias_deg=60.0)
    sup, rig, log, code = run(tmp_path / "b", bad, Options(skip_turn=True, duration_s=300))
    assert code == 1 and sup.state == "FAULT"
    assert "max_bootstrap_offset_deg" in sup.exit_reason and "clock" in sup.exit_reason
    assert any(e["event"] == "fault" and "traceback" in e for e in events(log))


def test_lamp_acquire_and_follow(tmp_path):
    rng = random.Random(8)
    lamp = (180.0 + rng.uniform(-40, 40), rng.uniform(20, 55))
    moved = (lamp[0] + 22.0, lamp[1] + 15.0)                     # about 25 deg on the sky
    seen = {"t_move": None, "errs": []}

    def on_tick(s):
        t = s.clock.monotonic()
        seen["errs"].append((t, s.rig.sim.pointing_error_deg()))
        if seen["t_move"] is None and len(seen["errs"]) == 10:
            s.rig.sim.move_lamp(*moved)
            seen["t_move"] = t

    params = SimParams(seed=8, lamp=lamp, heading0_true_deg=180.0)
    sup, rig, log, code = run(tmp_path, params, Options(mode="lamp", duration_s=260),
                              on_tick, body="session_lamp")
    assert code == 0
    tm = seen["t_move"]
    assert max(e for t, e in seen["errs"] if t < tm) < 3.0       # first acquire
    later = [(t, e) for t, e in seen["errs"] if t > tm + 2]
    assert later and later[0][0] - tm <= 60.0                    # re-acquired within 60 s
    assert all(e < 3.0 for _, e in later)
    assert any(e["event"] == "lamp_reacquire" for e in events(log))


@pytest.mark.parametrize("mode", ["euler", "trapezoid", "simpson"])
@pytest.mark.parametrize("heading0", [5.0, 95.0, 181.5, 270.0, 355.0])
def test_coarse_turn_reaches_target(tmp_path, mode, heading0):
    sup, rig, log, code = run(tmp_path, SimParams(seed=1, heading0_true_deg=heading0),
                              body="only_turn", overrides=['align.integral_mode="%s"' % mode])
    assert code == 0 and not sup.coarse_align_failed
    assert abs(angdiff(rig.sim.heading_true, 180.0)) < 3.0
    assert rig.sim.u == 0.0
    turn = rows(log, "turn.csv")
    assert turn and turn[0]["integral_mode"] == mode and float(turn[-1]["t_s"]) < 40.0


def test_coarse_turn_across_north(tmp_path):
    sup, rig, log, code = run(tmp_path, SimParams(seed=2, heading0_true_deg=300.0),
                              Options(target_heading_deg=20.0), body="only_turn")
    assert not sup.coarse_align_failed and abs(angdiff(rig.sim.heading_true, 20.0)) < 3.0
    first = rows(log, "turn.csv")[0]
    assert float(first["err_deg"]) > 0 and float(first["u"]) > 0     # short way: +80, not -280


def test_hardware_errors_fault(tmp_path):
    def on_tick(s):
        if s.clock.monotonic() > 200:
            s.rig.sim.fail_panel = True

    sup, rig, log, code = run(tmp_path, SimParams(seed=4), Options(duration_s=3600), on_tick)
    assert code == 1 and sup.state == "FAULT" and "hardware errors" in sup.exit_reason
    assert rig.sim.u == 0.0 and log._events.closed
    assert sum(e["event"] == "hardware_error" for e in events(log)) == 3


def test_sigint_parks_cleanly(tmp_path):
    def on_tick(s):
        if s.clock.monotonic() > 200 and not s.stop_requested:
            signal.raise_signal(signal.SIGINT)

    sup, rig, log, code = run(tmp_path, SimParams(seed=4), Options(duration_s=3600), on_tick)
    assert code == 0 and sup.state == "DONE" and sup.exit_reason == "stop requested"
    assert rig.servos.commanded() == (0.0, 0.0)
    assert json.load(open(log.dir / "session.json"))["exit_code"] == 0


def test_same_seed_is_byte_identical(tmp_path):
    out = []
    for name in ("a", "b"):
        _, _, log, _ = run(tmp_path / name, clear_day(), Options(duration_s=3600))
        out.append((log.dir / "cycle.csv").read_bytes())
    assert out[0] == out[1] and len(out[0]) > 10000
