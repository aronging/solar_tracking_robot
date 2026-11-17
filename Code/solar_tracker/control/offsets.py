"""Running estimate of one constant pointing offset from accepted scan measurements (spec 6.4.7)."""
from __future__ import annotations

from typing import List, Optional

from ..numerics.leastsq import OffsetEstimate, weighted_mean_offset


class OffsetEstimator:
    """Keeps every accepted total-offset measurement o_i with its sigma_i and
    re-solves the weighted least-squares mean after each one.

    NM-METHOD: Running weighted least-squares offset estimate | STAGE: 4
    """

    def __init__(self, initial_deg: float = 0.0, forget: float = 1.0, sigma_floor_deg: float = 0.2):
        self.initial_deg = initial_deg
        self.forget = forget
        self.sigma_floor_deg = sigma_floor_deg
        self.values: List[float] = []
        self.sigmas: List[float] = []
        self.history: List[OffsetEstimate] = []     # estimate after each sample

    def add(self, value_deg: float, sigma_deg: float) -> OffsetEstimate:
        self.values.append(value_deg)
        self.sigmas.append(sigma_deg)
        est = weighted_mean_offset(self.values, self.sigmas, self.forget, self.sigma_floor_deg)
        self.history.append(est)
        return est

    def reset(self, value_deg: Optional[float] = None, sigma_deg: float = 1.0) -> None:
        """Forget all samples; optionally seed with one (used by the acquire bootstrap)."""
        self.values, self.sigmas, self.history = [], [], []
        if value_deg is not None:
            self.add(value_deg, sigma_deg)

    @property
    def value_deg(self) -> float:
        return self.history[-1].value if self.history else self.initial_deg

    @property
    def se_deg(self) -> float:
        return self.history[-1].se if self.history else float("inf")
