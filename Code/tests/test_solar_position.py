import math
from datetime import datetime, timedelta, timezone

import pytest

from solar_tracker.geometry import angdiff
from solar_tracker.numerics.roots import bisection
from solar_tracker.solar.position import (jd_from_utc, solve_kepler, sun_position,
                                          sunrise_sunset, utc)
from solar_tracker.solar.reference_noaa import noaa_azel

LAT, LON = 30.6280, -96.3344                    # College Station (appendix A.1)

ANCHORS = [  # 2026-11-16 UTC hh, mm, az, el, decl
    (15, 0, 130.84, 22.67, -18.84), (16, 0, 143.37, 31.47, -18.85), (17, 0, 158.88, 37.72, -18.86),
    (18, 10, 179.96, 40.50, -18.87), (19, 0, 195.25, 39.06, -18.88), (20, 0, 211.71, 33.88, -18.89),
    (21, 0, 225.20, 25.82, -18.90),
]


def test_julian_date_and_utc_requirement():
    assert jd_from_utc(utc(2000, 1, 1, 12)) == 2451545.0
    assert jd_from_utc(utc(2026, 11, 16, 0)) == 2461360.5
    with pytest.raises(ValueError):
        sun_position(datetime(2026, 11, 16, 18, 0), LAT, LON)                  # naive
    with pytest.raises(ValueError):
        sun_position(datetime(2026, 11, 16, 12, 0, tzinfo=timezone(timedelta(hours=-6))), LAT, LON)


def test_matches_noaa_reference_every_10_minutes_in_november():
    t, end = utc(2026, 11, 1), utc(2026, 12, 1)
    worst_az = worst_el = worst_decl = 0.0
    n = 0
    while t < end:
        p = sun_position(t, LAT, LON)
        az, el, decl = noaa_azel(t, LAT, LON)
        worst_az = max(worst_az, abs(angdiff(p.az_deg, az)))
        worst_el = max(worst_el, abs(p.el_deg - el))
        worst_decl = max(worst_decl, abs(p.decl_deg - decl))
        t += timedelta(minutes=10)
        n += 1
    assert n == 30 * 144
    assert worst_az < 0.1, worst_az
    assert worst_el < 0.1, worst_el
    assert worst_decl < 0.1, worst_decl


@pytest.mark.parametrize("hh, mm, az, el, decl", ANCHORS)
def test_anchor_table(hh, mm, az, el, decl):
    p = sun_position(utc(2026, 11, 16, hh, mm), LAT, LON)
    assert abs(angdiff(p.az_deg, az)) < 0.1
    assert abs(p.el_deg - el) < 0.1
    assert abs(p.decl_deg - decl) < 0.1
    ref = noaa_azel(utc(2026, 11, 16, hh, mm), LAT, LON)
    assert ref == pytest.approx((az, el, decl), abs=0.01)       # the table is the NOAA series


def _solar_noon(day):
    """Time the local hour angle crosses zero (own bisection on sun_position)."""
    t0 = day.replace(hour=17, minute=30)
    r = bisection(lambda s: sun_position(t0 + timedelta(seconds=s), LAT, LON).hour_angle_deg,
                  0.0, 5400.0, 1e-3)
    assert r.converged
    return t0 + timedelta(seconds=r.value)


@pytest.mark.parametrize("day", [1, 16, 30])
def test_solar_noon_and_midnight(day):
    noon = _solar_noon(utc(2026, 11, day))
    p = sun_position(noon, LAT, LON)
    assert abs(angdiff(p.az_deg, 180.0)) < 0.5
    assert p.el_deg == pytest.approx(90.0 - LAT + p.decl_deg, abs=1e-6)
    # noon is the elevation maximum (declination drift moves it by seconds at most)
    for ds in (-600, 600):
        assert sun_position(noon + timedelta(seconds=ds), LAT, LON).el_deg < p.el_deg
    # the independent NOAA series puts the sun due south at the same instant
    assert abs(angdiff(noaa_azel(noon, LAT, LON)[0], 180.0)) < 0.5
    assert sun_position(noon + timedelta(hours=1), LAT, LON).az_deg > 180.0     # afternoon: west
    midnight = sun_position(noon - timedelta(hours=12), LAT, LON)
    assert midnight.el_deg < -60.0
    assert sun_position(utc(2026, 11, day, 6, 0), LAT, LON).el_deg < 0.0        # 00:00 CST


def test_solar_noon_time_matches_anchor():
    noon = _solar_noon(utc(2026, 11, 16))
    assert abs((noon - utc(2026, 11, 16, 18, 10)).total_seconds()) < 120       # az 179.96 at 18:10


@pytest.mark.parametrize("e", [0.0167, 0.2, 0.5, 0.9])
def test_kepler_solvers_agree(e):
    for i in range(1, 60):
        M = 2.0 * math.pi * i / 60.0
        rn, rf = solve_kepler(M, e, "newton"), solve_kepler(M, e, "fixed_point")
        assert rn.converged and rf.converged
        assert rn.value == pytest.approx(rf.value, abs=1e-9)
        assert rn.value - e * math.sin(rn.value) == pytest.approx(M, abs=1e-11)
        assert rn.iterations == len(rn.history) and rf.iterations == len(rf.history)
        assert rn.iterations <= rf.iterations


def test_kepler_solvers_agree_in_sun_position_and_inputs_are_checked():
    for hh in range(0, 24, 3):
        t = utc(2026, 11, 16, hh)
        pn, pf = sun_position(t, LAT, LON, "newton"), sun_position(t, LAT, LON, "fixed_point")
        assert pn.az_deg == pytest.approx(pf.az_deg, abs=1e-9)
        assert pn.el_deg == pytest.approx(pf.el_deg, abs=1e-9)
        assert 1 <= pn.kepler_iterations < pf.kepler_iterations <= 12
    slow = solve_kepler(1.0, 0.9, "fixed_point", max_iter=5)
    assert slow.converged is False                               # no raise on non-convergence
    with pytest.raises(ValueError):
        solve_kepler(1.0, 1.2)
    with pytest.raises(ValueError):
        solve_kepler(1.0, 0.1, "magic")


def test_sunrise_sunset_bisection_and_false_position_agree():
    day = utc(2026, 11, 16)
    b = sunrise_sunset(day, LAT, LON, "bisection")
    f = sunrise_sunset(day, LAT, LON, "false_position")
    for key in ("sunrise", "sunset"):
        assert abs((b[key] - f[key]).total_seconds()) < 3.0
        assert sun_position(b[key], LAT, LON).el_deg == pytest.approx(-0.833, abs=0.01)
    assert b["rise_result"].converged and f["set_result"].converged
    assert b["sunrise"] < _solar_noon(day) < b["sunset"]
    # College Station mid-November: sunrise ~06:50 CST, sunset ~17:27 CST
    assert abs((b["sunrise"] - utc(2026, 11, 16, 12, 50)).total_seconds()) < 600
    assert abs((b["sunset"] - utc(2026, 11, 16, 23, 27)).total_seconds()) < 600
