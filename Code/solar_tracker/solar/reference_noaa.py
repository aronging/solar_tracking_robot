"""Independent NOAA-series sun position. REFERENCE ONLY (simulator truth and tests);
not a graded method and never used for pointing."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Tuple

from ..geometry import wrap360
from .position import jd_from_utc


def noaa_azel(t: datetime, lat: float, lon: float) -> Tuple[float, float, float]:
    """UTC datetime, lat/lon degrees (east positive) -> (az_deg, el_deg, decl_deg)."""
    jc = (jd_from_utc(t) - 2451545.0) / 36525
    L0 = wrap360(280.46646 + jc * (36000.76983 + jc * 0.0003032))
    M = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    Mr = math.radians(M)
    C = (math.sin(Mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
         + math.sin(2 * Mr) * (0.019993 - 0.000101 * jc) + math.sin(3 * Mr) * 0.000289)
    omega = 125.04 - 1934.136 * jc
    app = L0 + C - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    dec = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app))))
    y = math.tan(math.radians(eps / 2)) ** 2
    L0r = math.radians(L0)
    eot = 4 * math.degrees(y * math.sin(2 * L0r) - 2 * e * math.sin(Mr)
                           + 4 * e * y * math.sin(Mr) * math.cos(2 * L0r)
                           - 0.5 * y * y * math.sin(4 * L0r) - 1.25 * e * e * math.sin(2 * Mr))
    minutes = t.hour * 60 + t.minute + (t.second + t.microsecond / 1e6) / 60
    tst = (minutes + eot + 4 * lon) % 1440
    ha = tst / 4 - 180
    phi, d, h = map(math.radians, (lat, dec, ha))
    cz = max(-1.0, min(1.0, math.sin(phi) * math.sin(d) + math.cos(phi) * math.cos(d) * math.cos(h)))
    z = math.degrees(math.acos(cz))
    den = math.cos(phi) * math.sin(math.radians(z))
    arg = max(-1.0, min(1.0, (math.sin(phi) * cz - math.sin(d)) / den)) if den else 1.0
    az = math.degrees(math.acos(arg))
    az = (az + 180) % 360 if ha > 0 else (540 - az) % 360
    return az, 90 - z, dec
