"""Clear-sky normal-incidence short-circuit current and the cloud ratio (spec 6.5).

I_clear(e) = k * 0.7^(AM^0.678), AM = 1/sin(e). Constants are approximate; k (mA) is
estimated from the first clear-sky peak of a session.
"""
from __future__ import annotations

import math


def attenuation(el_deg: float) -> float:
    """0.7^(AM^0.678); 0 for the sun at or below the horizon."""
    if el_deg <= 0.0:
        return 0.0
    am = 1.0 / math.sin(math.radians(el_deg))
    return 0.7 ** (am ** 0.678)


def clear_isc_mA(el_deg: float, k_mA: float) -> float:
    """Expected normal-incidence Isc (mA) under clear sky at elevation el_deg."""
    return k_mA * attenuation(el_deg)


def estimate_k_mA(isc_peak_mA: float, el_deg: float) -> float:
    """Invert the model at a measured clear-sky peak."""
    att = attenuation(el_deg)
    return isc_peak_mA / att if att > 0.0 else 0.0


def cloud_ratio(isc_mA: float, el_deg: float, k_mA: float, cos_i_pred: float = 1.0) -> float:
    """rho = measured / (I_clear * max(0, cos i_pred)); inf when nothing is expected."""
    expected = clear_isc_mA(el_deg, k_mA) * max(0.0, cos_i_pred)
    return isc_mA / expected if expected > 1e-9 else math.inf
