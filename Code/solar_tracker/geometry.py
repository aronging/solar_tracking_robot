"""Angle hygiene and pointing maths (spec section 4.1, appendix B).

All arguments and results are in DEGREES. Azimuth: 0 = true north, clockwise.
Elevation: above the horizon. Pan/tilt: signed servo angles, 0 at servo centre;
tilt is measured from VERTICAL (tilt 0 = panel vertical = normal on the horizon).
"""
from __future__ import annotations

import math
from typing import Tuple


def wrap360(x_deg: float) -> float:
    """Wrap to [0, 360)."""
    y = x_deg % 360.0
    return 0.0 if y >= 360.0 else y  # guards -1e-17 % 360 == 360.0


def wrap180(x_deg: float) -> float:
    """Wrap to [-180, 180)."""
    return (x_deg + 180.0) % 360.0 - 180.0


def angdiff(a_deg: float, b_deg: float) -> float:
    """Signed shortest difference a - b in [-180, 180). angdiff(1, 359) == 2."""
    return wrap180(a_deg - b_deg)


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def incidence_cos(sun_az_deg: float, sun_el_deg: float, n_az_deg: float, n_el_deg: float) -> float:
    """Cosine of the angle between the sun direction and the panel normal."""
    es, en = math.radians(sun_el_deg), math.radians(n_el_deg)
    return math.sin(es) * math.sin(en) + math.cos(es) * math.cos(en) * math.cos(
        math.radians(sun_az_deg - n_az_deg))


def pointing_to_servo(az_deg: float, el_deg: float, heading_true_deg: float,
                      az_offset_deg: float = 0.0, el_offset_deg: float = 0.0,
                      pan_sign: int = 1, tilt_sign: int = 1) -> Tuple[float, float]:
    """Desired normal (az, el) -> UNCLAMPED (pan_deg, tilt_deg) servo commands."""
    pan = pan_sign * angdiff(az_deg, heading_true_deg + az_offset_deg)
    tilt = tilt_sign * (el_deg - el_offset_deg)
    return pan, tilt


def servo_to_pointing(pan_deg: float, tilt_deg: float, heading_true_deg: float,
                      az_offset_deg: float = 0.0, el_offset_deg: float = 0.0,
                      pan_sign: int = 1, tilt_sign: int = 1) -> Tuple[float, float]:
    """Servo commands -> panel normal (az_deg in [0, 360), el_deg)."""
    az = wrap360(heading_true_deg + az_offset_deg + pan_sign * pan_deg)
    el = el_offset_deg + tilt_sign * tilt_deg
    return az, el
