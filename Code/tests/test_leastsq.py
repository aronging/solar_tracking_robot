import math
import random

import numpy as np
import pytest

from solar_tracker.numerics.leastsq import cosine_design, fit_cosine, fit_line

A_TRUE, DELTA_TRUE, C_TRUE, NOISE = 230.0, 3.0, 12.0, 0.4      # mA, deg, mA, mA
a0 = A_TRUE * math.cos(math.radians(DELTA_TRUE))
b0 = A_TRUE * math.sin(math.radians(DELTA_TRUE))


def _scan(K, S, rng, noise=NOISE):
    d = [-S + 2.0 * S * i / (K - 1) for i in range(K)]
    y = [a0 * math.cos(math.radians(x)) + b0 * math.sin(math.radians(x)) + C_TRUE
         + rng.gauss(0.0, noise) for x in d]
    return d, y


def _true_sigmas(d, noise=NOISE):
    """Exact 1-sigma of a, b, c and delta* (deg) for known noise: noise^2 (M^T M)^-1."""
    M = np.array(cosine_design(d))
    cov = noise ** 2 * np.linalg.inv(M.T @ M)
    g = np.array([-b0, a0, 0.0]) / (a0 * a0 + b0 * b0)
    return np.sqrt(np.diag(cov)), math.degrees(math.sqrt(g @ cov @ g))


def test_fit_line_recovers_slope_and_intercept():
    rng = random.Random(3)
    x = [float(p - 1500) for p in range(1000, 2001, 50)]           # pulse_us - 1500
    y = [0.09 * xi + 1.5 + rng.gauss(0.0, 0.5) for xi in x]
    fit = fit_line(x, y)
    se_m = 0.5 / math.sqrt(sum(xi * xi for xi in x))
    se_c = 0.5 / math.sqrt(len(x))
    assert abs(fit.m - 0.09) < 4 * se_m
    assert abs(fit.c - 1.5) < 4 * se_c
    assert 0.3 < fit.rms < 0.7 and fit.n == len(x) == len(fit.residuals)
    m_np, c_np = np.polyfit(x, y, 1)
    assert fit.m == pytest.approx(m_np, abs=1e-10) and fit.c == pytest.approx(c_np, abs=1e-9)
    exact = fit_line([0.0, 1.0, 2.0], [1.0, 3.0, 5.0])
    assert (exact.m, exact.c) == pytest.approx((2.0, 1.0)) and exact.rms < 1e-12
    with pytest.raises(ValueError):
        fit_line([1.0], [1.0])


@pytest.mark.parametrize("K", [5, 6, 7])
@pytest.mark.parametrize("S", [5, 10, 15, 20])
def test_fit_cosine_recovers_parameters_within_3_sigma(K, S):
    """200 seeded scans per (K, S): each of a, b, c, delta* lands within 3 sigma (exact sigma
    for the known noise) in at least 97% of scans (99.7% expected).

    Exception: at S = 5 deg sigma_a is ~110 mA on a = 230 mA, so delta* = atan2(b, a) is no
    longer linear in the noise and its linearised 3-sigma band only holds ~91-93% of scans
    (a, b, c themselves still pass). That is the spec's "small spreads are noise-limited"."""
    rng = random.Random(1000 * K + S)
    trials = 200
    d, _ = _scan(K, S, rng)
    sig_abc, sig_delta = _true_sigmas(d)
    hits = np.zeros(4)
    for _ in range(trials):
        fit = fit_cosine(*_scan(K, S, rng))
        assert fit.ok and fit.n == K
        err = np.abs([fit.a - a0, fit.b - b0, fit.c - C_TRUE, fit.delta_star_deg - DELTA_TRUE])
        hits += err <= 3.0 * np.append(sig_abc, sig_delta)
    need = np.array([0.97, 0.97, 0.97, 0.97 if S >= 10 else 0.88])
    assert (hits / trials >= need).all(), hits / trials


def test_fit_cosine_exact_on_noise_free_data():
    d, y = _scan(7, 15, random.Random(0), noise=0.0)
    fit = fit_cosine(d, y)
    assert (fit.a, fit.b, fit.c) == pytest.approx((a0, b0, C_TRUE), abs=1e-7)
    assert fit.delta_star_deg == pytest.approx(DELTA_TRUE, abs=1e-8)
    assert fit.amp == pytest.approx(A_TRUE, abs=1e-7) and fit.rms < 1e-9


def test_sigma_delta_matches_monte_carlo_scatter():
    rng = random.Random(2026)
    stars, sig2 = [], []
    for _ in range(2000):
        fit = fit_cosine(*_scan(7, 15, rng))
        stars.append(fit.delta_star_deg)
        sig2.append(fit.sigma_delta_deg ** 2)
    scatter = float(np.std(stars, ddof=1))
    predicted = math.sqrt(sum(sig2) / len(sig2))        # rms: s^2 is the unbiased quantity
    assert predicted == pytest.approx(scatter, rel=0.20)
    assert _true_sigmas(_scan(7, 15, rng)[0])[1] == pytest.approx(scatter, rel=0.10)
    assert abs(np.mean(stars) - DELTA_TRUE) < 4 * scatter / math.sqrt(2000)     # unbiased


@pytest.mark.parametrize("K", [5, 6, 7])
@pytest.mark.parametrize("S", [5, 10, 15, 20])
def test_fit_cosine_equals_numpy_lstsq(K, S):
    d, y = _scan(K, S, random.Random(K * S))
    fit = fit_cosine(d, y)
    M = np.array(cosine_design(d))
    ref, *_ = np.linalg.lstsq(M, np.array(y), rcond=None)
    # The normal equations square the condition number, so the achievable agreement is
    # ~ eps * cond2(M^T M) * |x|; 1e-8 holds for the operating spreads (S >= 10 deg), and
    # ~5e-8 is what a correct solver reaches at S = 5 deg (cond ~ 2e6).
    tol = 1e-8 if S >= 10 else 1e-6
    assert np.abs(np.array([fit.a, fit.b, fit.c]) - ref).max() < tol
    assert fit.delta_star_deg == pytest.approx(math.degrees(math.atan2(ref[1], ref[0])), abs=tol)
    assert fit.rms == pytest.approx(float(np.sqrt(np.mean((M @ ref - y) ** 2))), abs=1e-8)
    assert fit.cond2 == pytest.approx(np.linalg.cond(M.T @ M), rel=0.01)
    if K > 3:
        cov = np.sum((M @ ref - y) ** 2) / (K - 3) * np.linalg.inv(M.T @ M)
        assert np.allclose(fit.cov, cov, rtol=1e-4, atol=1e-9)


def test_fit_cosine_degenerate_inputs():
    with pytest.raises(ValueError):
        fit_cosine([0.0, 1.0], [1.0, 2.0])
    bad = fit_cosine([5.0, 5.0, 5.0, 5.0], [1.0, 1.0, 1.0, 1.0])       # singular: no raise
    assert bad.ok is False and bad.reason
    assert fit_cosine([-10.0, 0.0, 10.0], [1.0, 2.0, 1.0]).sigma_delta_deg == math.inf   # K = 3
