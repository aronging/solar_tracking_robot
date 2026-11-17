"""Coarse turn: rotate the robot in place to a true heading with the PID (spec 6.2).

Hardware is reached only through the callbacks passed in.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..geometry import angdiff, wrap360
from .pid import PID


@dataclass
class TurnResult:
    success: bool
    final_heading_deg: float
    duration_s: float
    reason: str
    samples: List[Dict[str, object]] = field(default_factory=list)   # turn.csv rows


def circular_mean_deg(angles_deg: List[float]) -> float:
    """Mean of headings that may straddle 0/360."""
    s = sum(math.sin(math.radians(a)) for a in angles_deg)
    c = sum(math.cos(math.radians(a)) for a in angles_deg)
    return wrap360(math.degrees(math.atan2(s, c)))


def coarse_turn(read_heading_true: Callable[[], float], set_turn: Callable[[float], None],
                stop: Callable[[], None], clock, target_deg: float, pid: PID,
                tol_deg: float = 2.0, hold_s: float = 1.0, max_turn_s: float = 40.0,
                loop_hz: float = 20.0, min_turn_duty: float = 0.25, stall_s: float = 1.0,
                on_sample: Optional[Callable[[Dict[str, object]], None]] = None,
                should_stop: Optional[Callable[[], bool]] = None) -> TurnResult:
    """Closed-loop turn. +u must increase the heading (clockwise from above).

    Inside the tolerance band the wheels are commanded to 0 (the motors' deadband makes
    a smaller command useless); success = inside the band continuously for hold_s.
    The wheels are stopped on every exit path. A loop iteration longer than stall_s
    aborts (in-loop watchdog; the supervisor adds a thread watchdog on real hardware).

    NM-METHOD: Heading PID loop (coarse align) | STAGE: 2
    """
    period = 1.0 / loop_hz
    samples: List[Dict[str, object]] = []
    success, reason = False, "timeout"
    t0 = t_prev = clock.monotonic()
    in_tol_since: Optional[float] = None
    pid.reset()
    try:
        while True:
            clock.sleep(period)
            t = clock.monotonic()
            dt = t - t_prev
            t_prev = t
            if dt > stall_s:
                reason = "watchdog: loop stalled %.2f s" % dt
                break
            if should_stop is not None and should_stop():
                reason = "stop requested"
                break
            heading = read_heading_true()
            err = angdiff(target_deg, heading)
            if abs(err) < tol_deg:
                u = 0.0
                if in_tol_since is None:
                    in_tol_since = t
            else:
                in_tol_since = None
                u = pid.update(err, dt)
                if 0.0 < abs(u) < min_turn_duty:
                    u = math.copysign(min_turn_duty, u)
            set_turn(u)
            row = {"t_s": round(t - t0, 4), "heading_true_deg": round(heading, 3),
                   "target_deg": round(target_deg, 3), "err_deg": round(err, 3), "u": round(u, 5),
                   "p_term": round(pid.p_term, 5), "i_term": round(pid.i_term, 5),
                   "d_term": round(pid.d_term, 5), "integral_mode": pid.integrator.mode,
                   "left_cmd": round(-u, 5), "right_cmd": round(u, 5)}
            samples.append(row)
            if on_sample is not None:
                on_sample(row)
            if in_tol_since is not None and t - in_tol_since >= hold_s:
                success, reason = True, "in tolerance"
                break
            if t - t0 >= max_turn_s:
                break
    finally:
        stop()
    clock.sleep(0.3)                                   # let the robot come to rest
    final = circular_mean_deg([read_heading_true() for _ in range(20)])
    return TurnResult(success, final, clock.monotonic() - t0, reason, samples)
