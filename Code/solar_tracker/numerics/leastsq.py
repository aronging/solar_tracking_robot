"""Linear least squares via the normal equations, solved with the own LU (numerics.linalg).

- fit_line:   y = m x + c                       (servo PWM -> angle calibration)
- fit_cosine: y = a cos d + b sin d + c         (refine scan; peak at d* = atan2(b, a))
- weighted_mean_offset: least-squares estimate of a constant from weighted samples
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Sequence

from .linalg import SingularMatrixError, cond2_spd, inverse, matmul, matvec, solve, transpose


@dataclass
class LineFit:
    m: float
    c: float
    rms: float            # residual RMS, same units as y
    n: int
    residuals: List[float] = field(default_factory=list)


@dataclass
class CosineFit:
    a: float
    b: float
    c: float
    delta_star_deg: float     # peak location relative to the scan centre
    amp: float                # R = sqrt(a^2 + b^2)
    rms: float                # residual RMS
    sigma_delta_deg: float    # 1-sigma of delta_star from the fit covariance (inf if K <= 3)
    cond2: float              # cond_2(M^T M)
    n: int
    cov: List[List[float]] = field(default_factory=list)   # s^2 (M^T M)^-1
    residuals: List[float] = field(default_factory=list)
    ok: bool = True
    reason: str = ""


@dataclass
class OffsetEstimate:
    value: float
    se: float                 # standard error of the estimate
    n: int


def _normal_equations(M: List[List[float]], y: Sequence[float]):
    Mt = transpose(M)
    return matmul(Mt, M), matvec(Mt, list(y))


def fit_line(x: Sequence[float], y: Sequence[float]) -> LineFit:
    """Least-squares line y = m x + c: solve (M^T M) [m, c]^T = M^T y with rows [x_i, 1].

    NM-METHOD: Linear least squares (line fit) | STAGE: 0
    """
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("need >= 2 points and equal lengths")
    MtM, Mty = _normal_equations([[xi, 1.0] for xi in x], y)
    m, c = solve(MtM, Mty)
    res = [yi - (m * xi + c) for xi, yi in zip(x, y)]
    return LineFit(m, c, math.sqrt(sum(r * r for r in res) / len(res)), len(x), res)


def cosine_design(deltas_deg: Sequence[float]) -> List[List[float]]:
    """K x 3 design matrix with rows [cos d, sin d, 1]."""
    return [[math.cos(math.radians(d)), math.sin(math.radians(d)), 1.0] for d in deltas_deg]


def fit_cosine(deltas_deg: Sequence[float], y: Sequence[float]) -> CosineFit:
    """Fit y = a cos d + b sin d + c by the normal equations + LU; peak d* = atan2(b, a).

    Also returns the covariance s^2 (M^T M)^-1 with s^2 = RSS/(K-3), sigma of d*
    propagated through atan2 (dd*/da = -b/R^2, dd*/db = a/R^2), and cond_2(M^T M).
    A singular system returns ok=False (never raises for well-formed input).

    NM-METHOD: Cosine least-squares fit (normal equations + LU) | STAGE: 4
    """
    K = len(deltas_deg)
    if K != len(y) or K < 3:
        raise ValueError("need >= 3 points and equal lengths")
    M = cosine_design(deltas_deg)
    MtM, Mty = _normal_equations(M, y)
    try:
        a, b, c = solve(MtM, Mty)
        inv = inverse(MtM)
    except SingularMatrixError:
        return CosineFit(0.0, 0.0, 0.0, 0.0, 0.0, math.inf, math.inf, math.inf, K,
                         ok=False, reason="singular normal equations")
    res = [yi - (a * r[0] + b * r[1] + c) for r, yi in zip(M, y)]
    rss = sum(r * r for r in res)
    R2 = a * a + b * b
    cov: List[List[float]] = []
    sigma = math.inf
    if K > 3 and R2 > 0.0:
        s2 = rss / (K - 3)
        cov = [[s2 * v for v in row] for row in inv]
        ga, gb = -b / R2, a / R2
        var = ga * ga * cov[0][0] + 2.0 * ga * gb * cov[0][1] + gb * gb * cov[1][1]
        sigma = math.degrees(math.sqrt(max(var, 0.0)))
    return CosineFit(a, b, c, math.degrees(math.atan2(b, a)), math.sqrt(R2),
                     math.sqrt(rss / K), sigma, cond2_spd(MtM), K, cov, res)


def weighted_mean_offset(values: Sequence[float], sigmas: Sequence[float], forget: float = 1.0,
                         sigma_floor: float = 0.2) -> OffsetEstimate:
    """Weighted least-squares estimate of a constant: argmin sum w_i (o_i - x)^2.

    w_i = forget^(N-1-i) / max(sigma_i, sigma_floor)^2 (newest sample has age 0).
    The closed-form solution of this 1-parameter normal equation is the weighted mean.

    NM-METHOD: Weighted least squares (constant offset) | STAGE: 4
    """
    n = len(values)
    if n == 0 or n != len(sigmas):
        raise ValueError("need >= 1 value and equal lengths")
    if not 0.0 < forget <= 1.0:
        raise ValueError("forget must be in (0, 1]")
    s = [max(si, sigma_floor) for si in sigmas]
    w = [forget ** (n - 1 - i) / (s[i] * s[i]) for i in range(n)]
    sw = sum(w)
    value = sum(wi * vi for wi, vi in zip(w, values)) / sw
    se = math.sqrt(sum(wi * wi * si * si for wi, si in zip(w, s))) / sw
    return OffsetEstimate(value, se, n)
