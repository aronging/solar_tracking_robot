"""Acquire: find the servo angle that maximises Isc on one axis (spec 6.3).

coarse bracket -> golden-section search -> parabolic interpolation.
``f(angle_deg) -> isc_mA`` moves the servo, settles and returns an averaged reading.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from ..numerics.optimize import golden_section_max, parabolic_vertex


@dataclass
class AcquireResult:
    x_best: float
    x_golden: float
    x_parabolic: float               # nan when the parabola was rejected
    f_best: float
    evals: int
    converged: bool
    edge_peak: bool = False
    no_signal: bool = False
    reason: str = ""
    history: List[Dict[str, object]] = field(default_factory=list)  # phase, iter, x, f, width


def acquire_axis(f: Callable[[float], float], center_deg: float, half_width_deg: float,
                 limits_deg: Tuple[float, float], n_coarse: int = 9, tol_deg: float = 1.5,
                 max_evals: int = 24, min_signal_mA: float = 5.0,
                 min_step_deg: float = 0.0) -> AcquireResult:
    """Maximise f over [center - half_width, center + half_width] clipped to limits_deg.

    1. Coarse pass at n_coarse evenly spaced angles; bracket = neighbours of the best.
       A best point on the window edge shifts the window once by half_width toward
       that edge; if it is still on the edge, ``edge_peak`` is set.
    2. Golden-section search on the bracket (stop at width < tol_deg or max_evals).
    3. Parabola through the two bracket ends and the best golden point; its vertex is
       used if it lies inside the bracket and the parabola opens downward.
       (The bracket ends are used rather than the nearest evaluated neighbours because
       points ~1 deg apart on a flat cosine peak differ by less than the sensor noise.)

    NM-METHOD: Acquire (coarse bracket + golden section + parabolic) | STAGE: 3
    """
    hist: List[Dict[str, object]] = []
    evals = 0
    if min_step_deg > 0.0:      # keep coarse points far enough apart to stand out of the noise
        n_coarse = max(3, min(n_coarse, int(2.0 * half_width_deg / min_step_deg) + 1))

    def coarse(center: float):
        nonlocal evals
        lo = max(center - half_width_deg, limits_deg[0])
        hi = min(center + half_width_deg, limits_deg[1])
        xs = [lo + (hi - lo) * i / (n_coarse - 1) for i in range(n_coarse)]
        fs = []
        for i, x in enumerate(xs):
            fs.append(f(x))
            evals += 1
            hist.append({"phase": "coarse", "iter": i, "x": x, "f": fs[-1], "width": hi - lo})
        return xs, fs, max(range(n_coarse), key=lambda i: fs[i])

    xs, fs, ib = coarse(center_deg)
    edge_peak = False
    if ib in (0, n_coarse - 1):
        direction = -1.0 if ib == 0 else 1.0
        at_limit = xs[ib] <= limits_deg[0] + 1e-9 or xs[ib] >= limits_deg[1] - 1e-9
        if not at_limit:
            xs, fs, ib = coarse(center_deg + direction * half_width_deg)
        if ib in (0, n_coarse - 1):
            edge_peak = True
    if fs[ib] < min_signal_mA:
        return AcquireResult(xs[ib], xs[ib], math.nan, fs[ib], evals, False, edge_peak, True,
                             "no signal", hist)

    a, b = xs[max(ib - 1, 0)], xs[min(ib + 1, n_coarse - 1)]
    fa, fb = fs[max(ib - 1, 0)], fs[min(ib + 1, n_coarse - 1)]
    res = golden_section_max(f, a, b, tol_deg, max_evals)
    evals += res.evals
    for h in res.history:
        hist.append({"phase": "golden", "iter": h["k"], "x": h["x"], "f": h["f"], "width": h["width"]})
    x_g, f_g = res.value, res.f_value
    if fs[ib] > f_g:                         # the coarse best can still be the best sample
        x_g, f_g = xs[ib], fs[ib]

    x_p = math.nan
    if a < x_g < b:
        v = parabolic_vertex((a, x_g, b), (fa, f_g, fb))
        if not math.isnan(v) and a <= v <= b:
            x_p = v
    hist.append({"phase": "parabolic", "iter": 0, "x": x_p, "f": math.nan, "width": b - a})
    x_best = x_g if math.isnan(x_p) else x_p
    hist.append({"phase": "result", "iter": 0, "x": x_best, "f": f_g, "width": res.b - res.a})
    return AcquireResult(x_best, x_g, x_p, f_g, evals, res.converged, edge_peak, False,
                         "edge peak" if edge_peak else res.reason, hist)
