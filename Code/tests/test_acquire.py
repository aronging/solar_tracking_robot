import math
import random

import pytest

from solar_tracker.control.acquire import acquire_axis

LIMITS = (-85.0, 85.0)
TOL = 1.5


def isc(peak, rng=None, amp=240.0, noise=0.4):
    """Synthetic panel: cosine bump clipped at 0, optional Gaussian noise (mA)."""
    def f(x):
        y = amp * max(0.0, math.cos(math.radians(x - peak)))
        return y + (rng.gauss(0.0, noise) if rng else 0.0)
    return f


@pytest.mark.parametrize("half_width, noise, min_rate", [
    (40.0, 0.4, 0.99),     # spec case: first (wide) acquire, single-reading noise 0.4 mA
    (15.0, 0.1, 0.99),     # narrow re-acquire with the callback averaging 16 readings
    (15.0, 0.4, 0.95),     # narrow window at raw noise: coarse step 3.75 deg changes Isc by
                           # only 0.5 mA near the peak, so 99% is not reachable (measured 97-98%)
])
def test_finds_peak_within_2_tol_in_500_trials(half_width, noise, min_rate):
    rng = random.Random(345)
    errs, evals = [], []
    for _ in range(500):
        center = rng.uniform(-30.0, 30.0)
        peak = center + rng.uniform(-0.9, 0.9) * half_width
        r = acquire_axis(isc(peak, rng, noise=noise), center, half_width, LIMITS, tol_deg=TOL)
        assert not r.no_signal and not r.edge_peak
        assert r.x_best == (r.x_golden if math.isnan(r.x_parabolic) else r.x_parabolic)
        errs.append(abs(r.x_best - peak))
        evals.append(r.evals)
    hit = sum(e <= 2 * TOL for e in errs) / len(errs)
    assert hit >= min_rate, hit
    assert max(evals) <= 9 + 24


def test_noise_free_parabola_refines_the_golden_estimate():
    r = acquire_axis(isc(7.3), 0.0, 40.0, LIMITS, tol_deg=TOL)
    assert r.converged and not math.isnan(r.x_parabolic)
    assert abs(r.x_parabolic - 7.3) < 0.2
    assert abs(r.x_golden - 7.3) < TOL
    assert r.f_best == pytest.approx(240.0, rel=1e-3)


def test_history_and_eval_budget():
    calls = []
    f = isc(-12.0)

    def counted(x):
        calls.append(x)
        return f(x)

    r = acquire_axis(counted, 0.0, 40.0, LIMITS, n_coarse=9, tol_deg=TOL, max_evals=24)
    assert r.evals == len(calls)
    phases = [h["phase"] for h in r.history]
    assert phases[:9] == ["coarse"] * 9 and phases[-2:] == ["parabolic", "result"]
    assert set(phases) == {"coarse", "golden", "parabolic", "result"}
    assert all({"phase", "iter", "x", "f", "width"} <= set(h) for h in r.history)
    widths = [h["width"] for h in r.history if h["phase"] == "golden"]
    assert widths[0] == pytest.approx(20.0) and widths[-1] <= TOL        # bracket = 2 coarse steps
    assert all(w2 < w1 for w1, w2 in zip(widths, widths[1:]))
    assert r.history[-1]["x"] == r.x_best
    assert all(LIMITS[0] <= x <= LIMITS[1] for x in calls)


def test_peak_one_window_away_is_found_after_the_shift():
    r = acquire_axis(isc(25.0), 0.0, 15.0, LIMITS, tol_deg=TOL)           # window [-15, 15]
    assert not r.edge_peak and abs(r.x_best - 25.0) <= 2 * TOL


@pytest.mark.parametrize("peak, side", [(70.0, 1), (-70.0, -1)])
def test_edge_peak_when_peak_is_outside_the_window(peak, side):
    r = acquire_axis(isc(peak, random.Random(1)), 0.0, 15.0, LIMITS, tol_deg=TOL)
    assert r.edge_peak and not r.no_signal
    assert "edge" in r.reason
    assert side * r.x_best > 25.0 and abs(r.x_best) <= 30.0 + 1e-9         # pinned to the shifted edge


def test_edge_peak_at_the_soft_limit():
    r = acquire_axis(isc(120.0), 60.0, 40.0, LIMITS, tol_deg=TOL)          # peak beyond +85 limit
    assert r.edge_peak and r.x_best <= 85.0 and r.x_best > 75.0


def test_no_signal_when_everything_is_below_the_threshold():
    rng = random.Random(2)
    r = acquire_axis(lambda x: 1.0 + rng.gauss(0.0, 0.4), 0.0, 40.0, LIMITS, min_signal_mA=5.0)
    assert r.no_signal and not r.converged and r.reason == "no signal"
    assert math.isnan(r.x_parabolic) and r.f_best < 5.0
    assert r.evals <= 18                                                    # coarse only, no search
    dark = acquire_axis(isc(0.0, amp=3.0), 0.0, 40.0, LIMITS)              # peak in window but dim
    assert dark.no_signal and not dark.edge_peak
