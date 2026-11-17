"""Sun position from the clock: orbital elements -> Kepler's equation -> az/el (spec 6.1).

Inputs: timezone-aware UTC datetimes, latitude/longitude in degrees (east positive).
Outputs in degrees. No refraction correction (about 0.02 deg at 23-44 deg elevation).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from ..geometry import wrap360
from ..numerics.roots import RootResult, bisection, false_position, fixed_point, newton

SUNRISE_EL_DEG = -0.833     # standard sunrise/sunset altitude (refraction + solar radius)


@dataclass(frozen=True)
class SunPosition:
    az_deg: float
    el_deg: float
    decl_deg: float
    ra_deg: float
    hour_angle_deg: float
    kepler_iterations: int


def _require_utc(t: datetime) -> None:
    if t.tzinfo is None or t.utcoffset() != timedelta(0):
        raise ValueError("time must be a timezone-aware UTC datetime")


def jd_from_utc(t: datetime) -> float:
    """Julian date from a UTC datetime (Gregorian calendar)."""
    _require_utc(t)
    y, m = t.year, t.month
    d = t.day + (t.hour + (t.minute + (t.second + t.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    A = y // 100
    B = 2 - A + A // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5


def solve_kepler(M_rad: float, e: float, method: str = "newton", tol: float = 1e-12,
                 max_iter: Optional[int] = None) -> RootResult:
    """Solve Kepler's equation E - e sin E = M for the eccentric anomaly E (radians).

    method "newton":      E <- E - (E - e sin E - M) / (1 - e cos E)   (quadratic)
    method "fixed_point": E <- M + e sin E                              (linear, rate e|cos E|)
    Start: E0 = M, or pi for e >= 0.8.

    NM-METHOD: Kepler's equation (fixed-point vs Newton-Raphson) | STAGE: 1
    """
    if not 0.0 <= e < 1.0:
        raise ValueError("eccentricity must be in [0, 1)")
    E0 = M_rad if e < 0.8 else math.pi
    if method == "newton":
        return newton(lambda E: E - e * math.sin(E) - M_rad, lambda E: 1.0 - e * math.cos(E),
                      E0, tol, max_iter or 50)
    if method == "fixed_point":
        return fixed_point(lambda E: M_rad + e * math.sin(E), E0, tol, max_iter or 500)
    raise ValueError("method must be 'newton' or 'fixed_point'")


def sun_position(t_utc: datetime, lat_deg: float, lon_deg: float,
                 method: str = "newton") -> SunPosition:
    """Azimuth (from north, clockwise) and elevation of the sun.

    NM-METHOD: Solar position via Kepler chain | STAGE: 1
    """
    n = jd_from_utc(t_utc) - 2451545.0                         # days from J2000.0
    M = math.radians(wrap360(357.5291 + 0.98560028 * n))       # mean anomaly
    e = 0.016709 - 1.151e-9 * n                                # eccentricity
    kep = solve_kepler(M, e, method)
    E = kep.value
    nu = 2.0 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2), math.sqrt(1 - e) * math.cos(E / 2))
    lam = nu + math.radians(282.9373 + 4.70684e-5 * n)         # ecliptic longitude
    eps = math.radians(23.4393 - 3.563e-7 * n)                 # obliquity
    dec = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = math.radians(wrap360(280.46061837 + 360.98564736629 * n))
    H = gmst + math.radians(lon_deg) - ra                      # local hour angle
    phi = math.radians(lat_deg)
    el = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H))
    az = math.atan2(-math.cos(dec) * math.sin(H),
                    math.sin(dec) * math.cos(phi) - math.cos(dec) * math.sin(phi) * math.cos(H))
    return SunPosition(wrap360(math.degrees(az)), math.degrees(el), math.degrees(dec),
                       wrap360(math.degrees(ra)), (math.degrees(H) + 180.0) % 360.0 - 180.0,
                       kep.iterations)


def sunrise_sunset(date_utc: datetime, lat_deg: float, lon_deg: float,
                   method: str = "bisection", tol_s: float = 1.0) -> Dict[str, object]:
    """Sunrise and sunset (UTC) around the local solar noon nearest ``date_utc``:
    the two roots of elevation(t) = -0.833 deg, bracketed between local solar
    midnight and local solar noon, found by bisection or false position.

    Returns {"sunrise": datetime|None, "sunset": datetime|None, "noon": datetime,
             "rise_result": RootResult|None, "set_result": RootResult|None}.
    None when the sun does not cross the threshold (polar day/night).

    NM-METHOD: Sunrise/sunset roots (bisection vs false position) | STAGE: 1
    """
    _require_utc(date_utc)
    finder = {"bisection": bisection, "false_position": false_position}[method]
    day0 = date_utc.replace(hour=12, minute=0, second=0, microsecond=0)
    noon = day0 - timedelta(hours=lon_deg / 15.0)              # mean solar noon, +-16 min

    def el(s: float) -> float:                                 # s = seconds from noon
        return sun_position(noon + timedelta(seconds=s), lat_deg, lon_deg).el_deg - SUNRISE_EL_DEG

    out: Dict[str, object] = {"sunrise": None, "sunset": None, "noon": noon,
                              "rise_result": None, "set_result": None}
    if el(0.0) <= 0.0:
        return out
    for key, res_key, s_far in (("sunrise", "rise_result", -43200.0), ("sunset", "set_result", 43200.0)):
        if el(s_far) >= 0.0:
            continue
        a, b = (s_far, 0.0) if s_far < 0 else (0.0, s_far)
        r = finder(el, a, b, tol_s, 200)
        out[key] = noon + timedelta(seconds=r.value)
        out[res_key] = r
    return out


def utc(*args: int) -> datetime:
    """Shorthand: utc(2026, 11, 16, 18, 10) -> aware UTC datetime."""
    return datetime(*args, tzinfo=timezone.utc)
