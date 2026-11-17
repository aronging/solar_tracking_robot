import math
import random

import pytest

from solar_tracker.numerics.optimize import GOLDEN, golden_section_max, parabolic_vertex


def bump(x):                                     # unimodal, max 240 at x = 12.3 deg
    return 240.0 * math.cos(math.radians(x - 12.3))


def test_golden_section_finds_maximum():
    r = golden_section_max(bump, -30.0, 40.0, 1e-6, 200)
    assert r.converged and r.reason
    assert r.value == pytest.approx(12.3, abs=1e-3)       # flat peak: f resolves x to ~sqrt(eps)
    assert r.f_value == pytest.approx(240.0)
    assert r.a <= 12.3 <= r.b and r.b - r.a <= 1e-6
    r2 = golden_section_max(lambda x: -(x - 2.0) ** 2, 5.0, -3.0, 1e-4)      # reversed bracket
    assert r2.value == pytest.approx(2.0, abs=1e-4)


def test_interval_shrinks_by_golden_ratio_with_one_new_evaluation_per_iteration():
    calls = []

    def f(x):
        calls.append(x)
        return bump(x)

    r = golden_section_max(f, -30.0, 40.0, 0.01, 200)
    widths = [h["width"] for h in r.history]
    assert widths[0] == 70.0
    for w1, w2 in zip(widths, widths[1:]):
        assert w2 / w1 == pytest.approx(GOLDEN, abs=1e-9)
    assert GOLDEN == pytest.approx(0.6180339887)
    assert r.iterations == len(widths) - 1 == math.ceil(math.log(0.01 / 70.0) / math.log(GOLDEN))
    assert len(calls) == r.evals == r.iterations + 2            # 2 to start, then exactly 1 each
    assert len(set(calls)) == len(calls)                        # the reused point is not re-evaluated
    assert [p[0] for p in r.points] == calls


def test_max_evals_stops_without_raising():
    r = golden_section_max(bump, -30.0, 40.0, 1e-9, 10)
    assert not r.converged and r.evals == 10 and r.reason
    assert abs(r.value - 12.3) < 70.0 * GOLDEN ** 8


def test_parabolic_vertex_recovers_a_parabola_exactly():
    rng = random.Random(5)
    for _ in range(200):
        xv, k, c = rng.uniform(-50, 50), rng.uniform(0.01, 5), rng.uniform(-10, 300)
        xs = sorted(rng.uniform(xv - 30, xv + 30) for _ in range(3))
        if min(xs[1] - xs[0], xs[2] - xs[1]) < 0.5:
            continue
        fs = [c - k * (x - xv) ** 2 for x in xs]
        assert parabolic_vertex(xs, fs) == pytest.approx(xv, abs=1e-8)
    assert parabolic_vertex((0.0, 1.0, 3.0), (-4.0, -1.0, -1.0)) == pytest.approx(2.0)


def test_parabolic_vertex_rejects_no_maximum():
    assert math.isnan(parabolic_vertex((0.0, 1.0, 2.0), (4.0, 1.0, 0.0 + 4.0)))   # opens upward
    assert math.isnan(parabolic_vertex((0.0, 1.0, 2.0), (1.0, 2.0, 3.0)))         # collinear
    assert math.isnan(parabolic_vertex((0.0, 1.0, 1.0), (1.0, 2.0, 2.0)))         # duplicate x


def _noisy_errors(noise, seed=11, trials=300):
    rng = random.Random(seed)
    errs = []
    for _ in range(trials):
        peak = rng.uniform(-8.0, 8.0)
        r = golden_section_max(
            lambda x: 240.0 * math.cos(math.radians(x - peak)) + rng.gauss(0.0, noise),
            -10.0, 10.0, 1.5, 24)
        assert r.converged and r.evals <= 24 and r.b - r.a <= 1.5       # always terminates on budget
        errs.append(abs(r.value - peak))
    return sorted(errs)


def test_golden_section_with_noise():
    """A 240 mA cosine is flat at the top: it drops only 0.4 mA at 3.3 deg from the peak, so
    with 0.4 mA noise per reading the comparisons near the peak are coin flips and the search
    can discard the true peak. Measured: median 1.5 deg, 99th percentile 4.8 deg. With the
    noise averaged down to 0.05 mA it resolves the peak to the bracket tolerance. (This is why
    acquire adds a parabola through the wide bracket and the callback averages readings.)"""
    raw = _noisy_errors(0.4)
    assert raw[len(raw) // 2] < 2.5 and raw[int(0.99 * len(raw))] < 7.0
    avg = _noisy_errors(0.05)
    assert avg[int(0.99 * len(avg))] < 2.5        # measured 1.86 deg (tolerance 1.5 + residual noise)
    assert avg[len(avg) // 2] < raw[len(raw) // 2]
