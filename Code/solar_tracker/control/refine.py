"""Refine scan: sample Isc around the predicted pointing, fit a cosine, gate the result (spec 6.4).

``measure(cmd_deg)`` moves one axis to cmd_deg, settles, and returns an object with
``isc_mA, isc_std_mA, n, overrange`` (a hardware.base.PanelReading).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from ..geometry import clamp
from ..numerics.leastsq import CosineFit, fit_cosine


@dataclass
class ScanPoint:
    role: str            # "center_start" | "point" | "center_end"
    k: int
    cmd_deg: float
    delta_deg: float
    isc_mA: float
    isc_std_mA: float
    n: int
    overrange: bool = False


@dataclass
class Gates:
    min_signal_mA: float = 5.0
    min_points: int = 5
    max_rms_frac: float = 0.03
    peak_in_window_frac: float = 1.0
    max_drift_frac: float = 0.03
    max_cond: float = 2.0e5      # cond2(MtM) is 2.3e4 at S=15 deg, 1.2e5 at S=10 deg (K=7)
    max_sigma_deg: float = 3.0
    max_scan_s: float = 30.0


@dataclass
class ScanResult:
    points: List[ScanPoint]
    spread_deg: float
    duration_s: float
    accepted: bool
    reject_reason: str = ""
    fit: Optional[CosineFit] = None
    mean_isc_mA: float = 0.0

    @property
    def delta_star_deg(self) -> float:
        return self.fit.delta_star_deg if self.fit else float("nan")


def scan_deltas(spread_deg: float, n_points: int, order: str = "shuffled",
                rng: Optional[random.Random] = None) -> List[float]:
    """n_points offsets evenly spaced in [-spread, +spread], in visiting order."""
    d = [-spread_deg + 2.0 * spread_deg * i / (n_points - 1) for i in range(n_points)]
    if order == "shuffled":
        (rng or random).shuffle(d)
    elif order != "sweep":
        raise ValueError("scan_order must be 'sweep' or 'shuffled'")
    return d


def run_scan(measure: Callable[[float], object], center_cmd_deg: float, spread_deg: float,
             n_points: int, order: str, rng: Optional[random.Random],
             limits_deg: Tuple[float, float], monotonic: Callable[[], float]
             ) -> Tuple[List[ScanPoint], float]:
    """Visit centre, the scan points, centre again. Returns (points, duration_s)."""
    t0 = monotonic()
    pts: List[ScanPoint] = []

    def visit(role: str, k: int, delta: float) -> None:
        cmd = clamp(center_cmd_deg + delta, limits_deg[0], limits_deg[1])
        r = measure(cmd)
        pts.append(ScanPoint(role, k, cmd, cmd - center_cmd_deg, r.isc_mA, r.isc_std_mA, r.n,
                             r.overrange))

    visit("center_start", 0, 0.0)
    for k, d in enumerate(scan_deltas(spread_deg, n_points, order, rng)):
        visit("point", k, d)
    visit("center_end", 0, 0.0)
    return pts, monotonic() - t0


def evaluate_scan(points: List[ScanPoint], spread_deg: float, duration_s: float,
                  gates: Gates) -> ScanResult:
    """Fit Isc(d) = a cos d + b sin d + c to the scan points and apply the quality gates.
    The first failing gate is reported in ``reject_reason``.

    NM-METHOD: Refine scan cosine fit + quality gates | STAGE: 4
    """
    res = ScanResult(points, spread_deg, duration_s, False)

    def reject(why: str) -> ScanResult:
        res.reject_reason = why
        return res

    seen = set()
    pts = []
    for p in points:                              # points clamped onto a limit collapse together
        if p.role == "point" and round(p.cmd_deg, 6) not in seen:
            seen.add(round(p.cmd_deg, 6))
            pts.append(p)
    centers = [p for p in points if p.role != "point"]
    if duration_s > gates.max_scan_s:
        return reject("scan too slow")
    if not pts:
        return reject("too few points")
    mean = sum(p.isc_mA for p in pts) / len(pts)
    res.mean_isc_mA = mean
    if mean < gates.min_signal_mA:
        return reject("low signal")
    if any(p.overrange for p in points):
        return reject("overrange")
    if len(pts) < gates.min_points:
        return reject("too few points")
    fit = fit_cosine([p.delta_deg for p in pts], [p.isc_mA for p in pts])
    res.fit = fit
    if not fit.ok:
        return reject(fit.reason)
    if fit.rms > gates.max_rms_frac * mean:
        return reject("residual rms")
    if abs(fit.delta_star_deg) > gates.peak_in_window_frac * spread_deg:
        return reject("peak outside window")
    if len(centers) >= 2 and abs(centers[-1].isc_mA - centers[0].isc_mA) / mean > gates.max_drift_frac:
        return reject("drift during scan")
    if fit.cond2 > gates.max_cond:
        return reject("ill-conditioned")
    if fit.sigma_delta_deg > gates.max_sigma_deg:
        return reject("sigma too large")
    res.accepted = True
    return res
