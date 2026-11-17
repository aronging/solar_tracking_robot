import math

import pytest

from solar_tracker.numerics.roots import (RootResult, bisection, false_position, fixed_point,
                                          newton, secant)

DOTTIE = 0.7390851332151607          # root of cos x - x
SQRT2 = math.sqrt(2.0)


def f_cos(x): return math.cos(x) - x
def f_sq(x): return x * x - 2.0


def _check(r, root, tol):
    assert isinstance(r, RootResult)
    assert r.converged, r.reason
    assert r.value == pytest.approx(root, abs=tol)
    assert r.iterations == len(r.history) >= 1          # iteration count recorded
    assert [h["k"] for h in r.history] == list(range(1, r.iterations + 1))
    assert all({"k", "x", "residual"} <= set(h) for h in r.history)
    assert r.reason


def test_fixed_point():
    r = fixed_point(math.cos, 1.0, 1e-12, 200)
    _check(r, DOTTIE, 1e-11)
    # linear convergence at rate |g'(x*)| = sin(x*) ~ 0.674
    res = [h["residual"] for h in r.history]
    assert res[20] / res[19] == pytest.approx(math.sin(DOTTIE), abs=0.02)
    # x = (x + 2/x)/2 is a fixed-point form for sqrt(2)
    _check(fixed_point(lambda x: 0.5 * (x + 2.0 / x), 1.0), SQRT2, 1e-12)


def test_newton():
    r1 = newton(f_cos, lambda x: -math.sin(x) - 1.0, 1.0)
    r2 = newton(f_sq, lambda x: 2.0 * x, 1.0)
    _check(r1, DOTTIE, 1e-12)
    _check(r2, SQRT2, 1e-12)
    assert r1.iterations <= 6 and r2.iterations <= 7
    assert r1.iterations < fixed_point(math.cos, 1.0).iterations      # quadratic beats linear
    # quadratic convergence: error_{k+1} ~ C error_k^2
    errs = [abs(h["x"] - SQRT2) for h in r2.history]
    assert errs[2] < 10 * errs[1] ** 2


@pytest.mark.parametrize("f, a, b, root", [(f_cos, 0.0, 1.0, DOTTIE), (f_sq, 0.0, 2.0, SQRT2)])
def test_bisection_and_false_position(f, a, b, root):
    rb = bisection(f, a, b, 1e-9)
    _check(rb, root, 1e-9)
    assert rb.iterations == math.ceil(math.log2((b - a) / 1e-9)) + 1   # one bit per step
    widths = [h["width"] for h in rb.history]
    assert all(w2 == pytest.approx(w1 / 2) for w1, w2 in zip(widths, widths[1:]))
    rf = false_position(f, a, b, 1e-9)
    _check(rf, root, 1e-8)
    assert rf.iterations < rb.iterations


def test_secant():
    r1, r2 = secant(f_cos, 0.0, 1.0), secant(f_sq, 1.0, 2.0)
    _check(r1, DOTTIE, 1e-12)
    _check(r2, SQRT2, 1e-12)
    assert r1.iterations <= 10 and r2.iterations <= 10


def test_non_convergence_returns_flag_instead_of_raising():
    results = [
        fixed_point(lambda x: 2.0 * x + 1.0, 1.0, 1e-12, 20),            # diverges
        fixed_point(math.cos, 1.0, 1e-12, 5),                             # too few iterations
        newton(lambda x: x * x + 1.0, lambda x: 2.0 * x, 3.0, 1e-12, 30),  # no real root
        newton(lambda x: x * x + 1.0, lambda x: 2.0 * x, 0.0),            # zero derivative
        bisection(f_sq, 0.0, 2.0, 1e-12, 5),
        false_position(f_sq, 0.0, 2.0, 1e-15, 3),
        secant(lambda x: x * x + 1.0, 0.0, 1.0, 1e-12, 20),
        secant(lambda x: 1.0, 0.0, 1.0),                                  # flat
    ]
    for r in results:
        assert r.converged is False
        assert r.reason
        assert r.iterations == len(r.history)
        assert math.isfinite(r.value)


def test_invalid_bracket_raises_value_error():
    for method in (bisection, false_position):
        with pytest.raises(ValueError):
            method(f_sq, 2.0, 3.0)
