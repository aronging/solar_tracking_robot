import math
import random

import numpy as np
import pytest

from solar_tracker.control.offsets import OffsetEstimator
from solar_tracker.numerics.leastsq import weighted_mean_offset


def test_empty_estimator_and_bootstrap_seed():
    est = OffsetEstimator(initial_deg=2.5)
    assert est.value_deg == 2.5 and est.se_deg == math.inf
    est.reset(7.0, sigma_deg=1.0)                       # acquire bootstrap is the first sample
    assert est.value_deg == 7.0 and est.se_deg == pytest.approx(1.0) and len(est.history) == 1
    est.reset()
    assert est.value_deg == 2.5 and est.values == []


def test_weighted_mean_converges_to_injected_constant():
    rng = random.Random(7)
    est = OffsetEstimator()
    truth, sigma = 7.0, 0.8
    for _ in range(200):
        est.add(truth + rng.gauss(0.0, sigma), sigma)
    errs = [abs(h.value - truth) for h in est.history]
    ses = [h.se for h in est.history]
    assert [h.n for h in est.history] == list(range(1, 201))
    for n in (1, 10, 50, 200):
        assert ses[n - 1] == pytest.approx(sigma / math.sqrt(n))        # standard error ~ 1/sqrt(N)
        assert errs[n - 1] < 3.5 * ses[n - 1]
    assert errs[-1] < 0.2 and est.value_deg == est.history[-1].value
    assert np.mean(errs[100:]) < np.mean(errs[:10])                     # it actually converges
    assert est.value_deg == pytest.approx(np.mean(est.values))          # equal sigmas: plain mean


def test_matches_numpy_weighted_average():
    rng = random.Random(8)
    v = [rng.uniform(-10, 10) for _ in range(30)]
    s = [rng.uniform(0.3, 3.0) for _ in range(30)]
    w = 1.0 / np.square(s)
    r = weighted_mean_offset(v, s)
    assert r.value == pytest.approx(np.average(v, weights=w))
    assert r.se == pytest.approx(1.0 / math.sqrt(w.sum()))
    assert r.n == 30


def test_one_outlier_is_down_weighted():
    est = OffsetEstimator()
    for v in (6.9, 7.1, 7.0, 6.95, 7.05):
        est.add(v, 0.5)
    before = est.value_deg
    est.add(20.0, 5.0)                                   # bad scan reports a large sigma
    plain_mean = float(np.mean(est.values))
    assert abs(est.value_deg - before) < 0.03            # weight ratio 1:100 against 5 good scans
    assert abs(plain_mean - 7.0) > 2.0                   # an unweighted mean would be dragged
    assert est.se_deg < 0.5 / math.sqrt(5) + 1e-12


def test_sigma_floor_stops_an_overconfident_sample_from_dominating():
    r = weighted_mean_offset([0.0, 10.0], [1.0, 1e-6], sigma_floor=0.2)
    assert r.value == pytest.approx(10.0 * 25.0 / 26.0)                 # weights 1 and 1/0.2^2
    assert r.se >= 0.19


def test_forgetting_factor_behaves_as_documented():
    v = [1.0, 2.0, 4.0, 8.0]
    s = [0.5, 1.0, 0.5, 2.0]
    for forget in (1.0, 0.9, 0.5):
        # w_i = forget^(N-1-i) / sigma_i^2, newest sample has age 0
        w = np.array([forget ** (3 - i) / s[i] ** 2 for i in range(4)])
        r = weighted_mean_offset(v, s, forget)
        assert r.value == pytest.approx(float(w @ v / w.sum()))
        assert r.se == pytest.approx(float(np.sqrt((w ** 2) @ np.square(s)) / w.sum()))
    for bad in (0.0, 1.5, -0.1):
        with pytest.raises(ValueError):
            weighted_mean_offset(v, s, bad)
    with pytest.raises(ValueError):
        weighted_mean_offset([], [])


def test_forgetting_tracks_a_step_change_and_costs_precision():
    keep, forgetful = OffsetEstimator(forget=1.0), OffsetEstimator(forget=0.7)
    for est in (keep, forgetful):
        for _ in range(20):
            est.add(5.0, 1.0)
        for _ in range(10):
            est.add(9.0, 1.0)                           # the mount was bumped by 4 deg
    assert keep.value_deg == pytest.approx(5.0 + 4.0 * 10 / 30)
    assert forgetful.value_deg > 8.8                    # old samples have faded
    assert forgetful.se_deg > keep.se_deg               # fewer effective samples
    assert forgetful.se_deg == pytest.approx(math.sqrt((1 - 0.7) / (1 + 0.7)), rel=0.01)
