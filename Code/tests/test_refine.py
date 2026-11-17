import math
import random
from types import SimpleNamespace

import pytest

from solar_tracker.control.refine import Gates, evaluate_scan, run_scan, scan_deltas

LIMITS = (-85.0, 85.0)
GATES = Gates(max_cond=2e5)       # cond2(MtM) is ~2.3e4 at S = 15 deg, K = 7 (default 1e4 rejects it)


def scan(peak_deg=4.0, spread=15.0, K=7, center=10.0, amp=230.0, offset=10.0, noise=0.0, seed=0,
         end_factor=1.0, overrange_at=None, order="shuffled", limits=LIMITS, step_s=1.0):
    """Run a scan on a synthetic panel whose Isc peaks at center + peak_deg."""
    rng = random.Random(seed)
    clock = [0.0]
    calls = [0]

    def measure(cmd):
        calls[0] += 1
        clock[0] += step_s
        y = amp * math.cos(math.radians(cmd - center - peak_deg)) + offset + rng.gauss(0.0, noise)
        if calls[0] == K + 2:                       # the closing centre reading
            y *= end_factor
        return SimpleNamespace(isc_mA=y, isc_std_mA=noise, n=8, overrange=calls[0] == overrange_at)

    return run_scan(measure, center, spread, K, order, rng, limits, lambda: clock[0])


def test_run_scan_structure():
    pts, dur = scan(K=7)
    assert [p.role for p in pts] == ["center_start"] + ["point"] * 7 + ["center_end"]
    assert dur == pytest.approx(9.0)
    assert pts[0].delta_deg == pts[-1].delta_deg == 0.0
    deltas = [p.delta_deg for p in pts[1:-1]]
    assert sorted(deltas) == pytest.approx([-15, -10, -5, 0, 5, 10, 15])
    assert deltas != sorted(deltas)                                    # shuffled visiting order
    assert all(p.cmd_deg == pytest.approx(10.0 + p.delta_deg) for p in pts)
    assert scan_deltas(15.0, 7, "sweep") == pytest.approx([-15, -10, -5, 0, 5, 10, 15])
    assert scan_deltas(15.0, 7, "shuffled", random.Random(3)) == scan_deltas(15.0, 7, "shuffled", random.Random(3))
    with pytest.raises(ValueError):
        scan_deltas(15.0, 7, "spiral")


@pytest.mark.parametrize("K", [5, 6, 7])
@pytest.mark.parametrize("peak", [-9.0, 0.0, 4.0])
def test_accepts_clean_data_and_returns_delta_star(K, peak):
    pts, dur = scan(peak_deg=peak, K=K)
    res = evaluate_scan(pts, 15.0, dur, Gates(max_cond=2e5 if K == 7 else 1e6))
    assert res.accepted and res.reject_reason == ""
    assert res.delta_star_deg == pytest.approx(peak, abs=1e-6)
    assert res.fit.amp == pytest.approx(230.0, rel=1e-6)
    assert res.mean_isc_mA > 200.0


def test_accepts_noisy_data_within_sigma():
    for seed in range(20):
        pts, dur = scan(peak_deg=4.0, noise=0.4, seed=seed)
        res = evaluate_scan(pts, 15.0, dur, GATES)
        assert res.accepted, res.reject_reason
        assert abs(res.delta_star_deg - 4.0) < 1.0
        assert res.fit.sigma_delta_deg < 1.0


def _reason(pts, dur, spread=15.0, gates=GATES):
    res = evaluate_scan(pts, spread, dur, gates)
    assert not res.accepted
    return res.reject_reason


def test_rejects_too_few_points():
    assert _reason(*scan(K=4)) == "too few points"
    # five commanded points, but the soft limit collapses three of them onto one angle
    pts, dur = scan(K=5, center=80.0, limits=(-85.0, 85.0))
    assert _reason(pts, dur) == "too few points"
    assert _reason([], 0.0) == "too few points"


def test_rejects_drift_between_centre_readings():
    assert _reason(*scan(end_factor=0.90)) == "drift during scan"
    assert _reason(*scan(end_factor=1.05)) == "drift during scan"
    pts, dur = scan(end_factor=0.98)                                    # 2% < 3% gate
    assert evaluate_scan(pts, 15.0, dur, GATES).accepted


def test_rejects_peak_outside_window():
    assert _reason(*scan(peak_deg=25.0)) == "peak outside window"
    assert _reason(*scan(peak_deg=-25.0)) == "peak outside window"
    pts, dur = scan(peak_deg=10.0)
    assert evaluate_scan(pts, 15.0, dur, GATES).accepted
    assert _reason(pts, dur, gates=Gates(max_cond=2e5, peak_in_window_frac=0.5)) == "peak outside window"


def test_rejects_ill_conditioned_small_spread():
    pts, dur = scan(peak_deg=0.5, spread=2.0)
    res = evaluate_scan(pts, 2.0, dur, GATES)
    assert not res.accepted and res.reject_reason == "ill-conditioned"
    assert res.fit.cond2 > 1e7                                          # vs ~2.3e4 at 15 deg
    pts, dur = scan()
    assert 1e4 < evaluate_scan(pts, 15.0, dur, GATES).fit.cond2 < 5e4


def test_rejects_low_amplitude():
    assert _reason(*scan(amp=2.0, offset=1.0)) == "low signal"         # mean ~3 mA < 5 mA
    # a flat, noisy trace has no usable peak: sigma of delta* blows up
    r = _reason(*scan(amp=0.5, offset=50.0, noise=0.4, seed=4))
    assert r in ("sigma too large", "peak outside window")


def test_rejects_noisy_fit_overrange_and_slow_scan():
    assert _reason(*scan(noise=15.0, seed=1)) == "residual rms"
    assert _reason(*scan(overrange_at=3)) == "overrange"
    assert _reason(*scan(step_s=4.0)) == "scan too slow"               # 36 s > 30 s
    pts, dur = scan(noise=1.5, seed=2)
    assert _reason(pts, dur, gates=Gates(max_cond=2e5, max_sigma_deg=0.05)) == "sigma too large"
