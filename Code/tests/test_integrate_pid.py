import math

import pytest

from solar_tracker.control.heading import circular_mean_deg, coarse_turn
from solar_tracker.control.pid import PID
from solar_tracker.geometry import angdiff, wrap360
from solar_tracker.numerics.integrate import Integrator, simpson, trapezoid

CASES = [(math.sin, 0.0, math.pi, 2.0), (math.exp, 0.0, 1.0, math.e - 1.0)]


def _running(mode, f, a, b, n):
    """Feed n uniform steps of f on [a, b] to a running Integrator."""
    h = (b - a) / n
    integ = Integrator(mode)
    if mode != "euler":
        integ.update(f(a), h)                  # first sample only primes trapezoid/simpson
    for k in range(1, n + 1):
        integ.update(f(a + k * h), h)
    return integ.value


@pytest.mark.parametrize("f, a, b, exact", CASES)
def test_integrator_orders(f, a, b, exact):
    err = {m: [abs(_running(m, f, a, b, n) - exact) for n in (50, 100, 200)]
           for m in ("euler", "trapezoid", "simpson")}
    for e1, e2 in zip(err["trapezoid"], err["trapezoid"][1:]):
        assert e1 / e2 == pytest.approx(4.0, rel=0.02)          # second order
        assert e2 < 1e-3
    for e1, e2 in zip(err["simpson"], err["simpson"][1:]):
        assert e1 / e2 == pytest.approx(16.0, rel=0.05)         # fourth order
    assert err["simpson"][0] < err["trapezoid"][0]


def test_euler_is_first_order_with_known_error():
    # right-rectangle rule: error ~ (h/2) (f(b) - f(a)); int sin over [0, pi] has f(b) = f(a),
    # so the first-order term cancels there -- use [0, pi/2] to show it.
    for f, a, b, exact in [(math.sin, 0.0, math.pi / 2, 1.0), (math.exp, 0.0, 1.0, math.e - 1.0)]:
        errs = [_running("euler", f, a, b, n) - exact for n in (100, 200, 400)]
        for n, e in zip((100, 200, 400), errs):
            assert e == pytest.approx(0.5 * (b - a) / n * (f(b) - f(a)), rel=0.02)
        assert errs[0] / errs[1] == pytest.approx(2.0, rel=0.02)
        assert abs(errs[0]) > 50 * abs(_running("trapezoid", f, a, b, 100) - exact)


@pytest.mark.parametrize("f, a, b, exact", CASES)
def test_composite_rules(f, a, b, exact):
    for n in (20, 21):                                           # even and odd interval counts
        h = (b - a) / n
        x = [a + k * h for k in range(n + 1)]
        y = [f(v) for v in x]
        assert trapezoid(y, x) == pytest.approx(_running("trapezoid", f, a, b, n), abs=1e-12)
        assert abs(trapezoid(y, x) - exact) < (b - a) ** 3 / (12 * n * n) * 3.0
        assert abs(simpson(y, h) - exact) < abs(trapezoid(y, x) - exact)
    y = [f(a + k * (b - a) / 40) for k in range(41)]
    assert simpson(y, (b - a) / 40) == pytest.approx(exact, abs=1e-6)
    assert trapezoid([1.0, 3.0, 3.0], [0.0, 1.0, 4.0]) == pytest.approx(11.0)    # non-uniform


def test_integrator_reset_clamp_and_bad_mode():
    integ = Integrator("euler")
    for _ in range(10):
        integ.update(1.0, 0.5)
    assert integ.value == pytest.approx(5.0)
    integ.clamp(-2.0, 2.0)
    assert integ.value == 2.0
    integ.reset()
    assert integ.value == 0.0
    with pytest.raises(ValueError):
        Integrator("rk4")


def _step_response(pid, setpoint=1.0, tau=0.5, dt=0.01, t_end=20.0):
    """First-order plant tau y' = u - y under the PID. Returns the y samples."""
    y, ys = 0.0, []
    for _ in range(int(t_end / dt)):
        u = pid.update(setpoint - y, dt)
        y += dt * (u - y) / tau
        ys.append(y)
    return ys


@pytest.mark.parametrize("mode", ["euler", "trapezoid", "simpson"])
def test_pid_step_response_first_order_plant(mode):
    ys = _step_response(PID(2.0, 1.5, 0.0, integral_mode=mode, u_limit=10.0))
    assert ys[-1] == pytest.approx(1.0, abs=1e-3)               # integral action: no offset
    assert max(ys) < 1.1                                         # overdamped design
    rise = next(i for i, y in enumerate(ys) if y >= 0.9) * 0.01
    assert 0.2 < rise < 5.0
    assert all(abs(y - 1.0) < 0.02 for y in ys[1000:])           # settled after 10 s


def test_p_only_leaves_steady_state_error_and_modes_differ_slightly():
    ys = _step_response(PID(2.0, 0.0, 0.0, u_limit=10.0))
    assert ys[-1] == pytest.approx(2.0 / 3.0, abs=1e-3)          # kp / (1 + kp)
    e = _step_response(PID(2.0, 1.5, integral_mode="euler", u_limit=10.0), t_end=2.0)
    t = _step_response(PID(2.0, 1.5, integral_mode="trapezoid", u_limit=10.0), t_end=2.0)
    diff = max(abs(p - q) for p, q in zip(e, t))
    assert 0.0 < diff < 0.02                                     # same loop, O(dt) apart


def test_pid_derivative_filter_and_validation():
    pid = PID(0.0, 0.0, 1.0, d_filter_tau_s=0.0, u_limit=100.0)
    assert pid.update(1.0, 0.1) == 0.0                           # no derivative kick on sample 1
    assert pid.update(1.5, 0.1) == pytest.approx(5.0)
    slow = PID(0.0, 0.0, 1.0, d_filter_tau_s=0.4, u_limit=100.0)
    slow.update(1.0, 0.1)
    assert slow.update(1.5, 0.1) == pytest.approx(1.0)           # alpha = dt / (tau + dt) = 0.2
    with pytest.raises(ValueError):
        pid.update(1.0, 0.0)


def test_anti_windup_under_saturation():
    kp, ki, dt, tau = 1.0, 2.0, 0.01, 0.5
    pid = PID(kp, ki, integral_mode="trapezoid", u_limit=1.0)
    y, naive_i = 0.0, 0.0
    for _ in range(2000):                        # 20 s with an unreachable setpoint (plant max = 1)
        e = 3.0 - y
        u = pid.update(e, dt)
        naive_i += e * dt
        assert abs(u) <= 1.0
        assert abs(ki * pid.integrator.value) <= 1.0 + 1e-12
        y += dt * (u - y) / tau
    assert naive_i > 30.0                        # what an unprotected integrator would hold
    assert y == pytest.approx(1.0, abs=1e-3)
    ys, us = [], []
    for _ in range(500):                         # reachable setpoint: must recover at once
        u = pid.update(0.5 - y, dt)
        y += dt * (u - y) / tau
        ys.append(y)
        us.append(u)
    assert max(us[:5]) < 1.0                     # leaves saturation immediately, no wind-down
    assert all(abs(v - 0.5) < 0.02 for v in ys[300:])
    # an unprotected PI with the wound-up integral would still be saturated after these 5 s
    assert kp * (0.5 - 1.0) + ki * (naive_i - 0.5 * 5.0) > 1.0


def test_integral_reset_on_large_error():
    pid = PID(0.0, 1.0, integral_mode="euler", u_limit=100.0, i_zone=5.0)
    for _ in range(10):
        pid.update(2.0, 0.1)
    assert pid.integrator.value == pytest.approx(2.0)
    pid.update(9.0, 0.1)
    assert pid.integrator.value == 0.0
    pid.reset()
    assert (pid.p_term, pid.i_term, pid.d_term) == (0.0, 0.0, 0.0)


def test_heading_wrap_error_and_derivative():
    assert angdiff(1.0, 359.0) == 2.0 and angdiff(359.0, 1.0) == -2.0
    pid = PID(0.1, angular=True)
    assert pid.update(angdiff(1.0, 359.0), 0.05) == pytest.approx(0.2)     # short way: +2 deg
    d = PID(0.0, 0.0, 1.0, angular=True, u_limit=1e6)
    d.update(179.0, 0.1)
    assert d.update(-179.0, 0.1) == pytest.approx(20.0)        # +2 deg step, not -358
    plain = PID(0.0, 0.0, 1.0, u_limit=1e6)
    plain.update(179.0, 0.1)
    assert plain.update(-179.0, 0.1) == pytest.approx(-3580.0)
    assert circular_mean_deg([359.0, 1.0]) == pytest.approx(0.0, abs=1e-9) or \
        circular_mean_deg([359.0, 1.0]) == pytest.approx(360.0, abs=1e-9)
    assert circular_mean_deg([350.0, 20.0]) == pytest.approx(5.0)


class Bot:
    """Fake clock + turn-in-place plant: heading rate = rate_dps * u, integrated in sleep()."""

    def __init__(self, heading, rate_dps=90.0):
        self.t, self.h, self.u, self.rate, self.stops = 0.0, heading, 0.0, rate_dps, 0

    def monotonic(self):
        return self.t

    def sleep(self, s):
        self.t += s
        self.h = wrap360(self.h + self.rate * self.u * s)

    def set_turn(self, u):
        self.u = u

    def stop(self):
        self.u = 0.0
        self.stops += 1


@pytest.mark.parametrize("mode", ["euler", "trapezoid"])
@pytest.mark.parametrize("start, target", [(359.0, 1.0), (1.0, 359.0), (350.0, 20.0),
                                           (20.0, 340.0), (100.0, 250.0)])
def test_coarse_turn_across_wrap(mode, start, target):
    bot = Bot(start)
    pid = PID(0.03, 0.01, 0.0, integral_mode=mode, angular=True)
    r = coarse_turn(lambda: bot.h, bot.set_turn, bot.stop, bot, target, pid)
    assert r.success and r.reason == "in tolerance"
    assert abs(angdiff(r.final_heading_deg, target)) < 2.0
    assert r.duration_s < 40.0 and bot.u == 0.0 and bot.stops == 1
    e0 = angdiff(target, start)
    first = r.samples[0]
    assert math.copysign(1.0, first["u"]) == math.copysign(1.0, e0)        # turns the short way
    assert first["left_cmd"] == -first["u"] and first["right_cmd"] == first["u"]
    assert all(abs(s["err_deg"]) <= abs(e0) + 1e-6 for s in r.samples)     # never the long way
    assert all(s["u"] == 0.0 or abs(s["u"]) >= 0.25 for s in r.samples)   # deadband compensation
    assert all(s["integral_mode"] == mode for s in r.samples)


def test_coarse_turn_timeout_and_exception_stop_the_wheels():
    bot = Bot(90.0, rate_dps=0.0)                                # stalled robot
    r = coarse_turn(lambda: bot.h, bot.set_turn, bot.stop, bot, 180.0, PID(0.03, angular=True),
                    max_turn_s=5.0)
    assert not r.success and r.reason == "timeout" and bot.u == 0.0 and bot.stops == 1

    bot = Bot(90.0)

    def broken_imu():
        raise OSError("i2c")

    with pytest.raises(OSError):
        coarse_turn(broken_imu, bot.set_turn, bot.stop, bot, 180.0, PID(0.03, angular=True))
    assert bot.stops == 1
