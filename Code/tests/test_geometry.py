import math
import random

import pytest

from solar_tracker.geometry import (angdiff, incidence_cos, pointing_to_servo, servo_to_pointing,
                                    wrap180, wrap360)


@pytest.mark.parametrize("x, want", [(0, 0), (360, 0), (-360, 0), (720, 0), (359.5, 359.5),
                                     (-0.5, 359.5), (361, 1), (-1e-17, 0)])
def test_wrap360_edges(x, want):
    y = wrap360(x)
    assert y == pytest.approx(want, abs=1e-12)
    assert 0.0 <= y < 360.0


@pytest.mark.parametrize("x, want", [(0, 0), (180, -180), (-180, -180), (179.5, 179.5),
                                     (-179.5, -179.5), (181, -179), (-181, 179), (540, -180),
                                     (360, 0)])
def test_wrap180_edges(x, want):
    y = wrap180(x)
    assert y == pytest.approx(want, abs=1e-12)
    assert -180.0 <= y < 180.0


def test_angdiff():
    assert angdiff(1, 359) == 2
    assert angdiff(359, 1) == -2
    assert angdiff(10, 10) == 0
    assert angdiff(350, -10) == 0
    assert abs(angdiff(0, 180)) == 180


def test_pointing_servo_round_trip():
    rng = random.Random(1)
    for _ in range(500):
        heading, az_off = rng.uniform(0, 360), rng.uniform(-40, 40)
        el_off = rng.uniform(-10, 10)
        ps, ts = rng.choice((1, -1)), rng.choice((1, -1))
        kw = dict(az_offset_deg=az_off, el_offset_deg=el_off, pan_sign=ps, tilt_sign=ts)
        # servo -> pointing -> servo
        pan, tilt = rng.uniform(-179, 179), rng.uniform(-90, 90)
        pan2, tilt2 = pointing_to_servo(*servo_to_pointing(pan, tilt, heading, **kw), heading, **kw)
        assert pan2 == pytest.approx(pan, abs=1e-9)
        assert tilt2 == pytest.approx(tilt, abs=1e-9)
        # pointing -> servo -> pointing
        az, el = rng.uniform(0, 360), rng.uniform(0, 90)
        az2, el2 = servo_to_pointing(*pointing_to_servo(az, el, heading, **kw), heading, **kw)
        assert angdiff(az2, az) == pytest.approx(0, abs=1e-9)
        assert el2 == pytest.approx(el, abs=1e-9)


def test_pointing_to_servo_matches_appendix_b():
    # robot facing south, sun at az 225.2 / el 25.82 -> pan +45.2, tilt 25.82
    assert pointing_to_servo(225.2, 25.82, 180.0) == pytest.approx((45.2, 25.82))
    assert pointing_to_servo(130.84, 22.67, 180.0, az_offset_deg=7, el_offset_deg=-3) == \
        pytest.approx((-56.16, 25.67))


def _unit(az, el):   # east, north, up
    a, e = math.radians(az), math.radians(el)
    return (math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e))


def test_incidence_cos():
    assert incidence_cos(200, 35, 200, 35) == pytest.approx(1.0)
    assert incidence_cos(200, 0, 290, 0) == pytest.approx(0.0, abs=1e-12)     # 90 deg in azimuth
    assert incidence_cos(123, 90, 10, 0) == pytest.approx(0.0, abs=1e-12)     # zenith vs horizon
    assert incidence_cos(0, 30, 180, 30) == pytest.approx(math.cos(math.radians(120)))
    rng = random.Random(2)
    for _ in range(500):
        sa, se, na, ne = rng.uniform(0, 360), rng.uniform(-90, 90), rng.uniform(0, 360), rng.uniform(-90, 90)
        dot = sum(p * q for p, q in zip(_unit(sa, se), _unit(na, ne)))
        assert incidence_cos(sa, se, na, ne) == pytest.approx(dot, abs=1e-12)
