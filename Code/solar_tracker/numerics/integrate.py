"""Numerical integration: a running integrator for the PID and composite rules for logged data."""
from __future__ import annotations

from typing import Optional, Sequence

MODES = ("euler", "trapezoid", "simpson")


class Integrator:
    """Running integral of a sampled signal.

    euler:     I += f_k dt                       (first order)
    trapezoid: I += 0.5 (f_k + f_{k-1}) dt       (second order)
    simpson:   every second sample, I += (h/3)(f_{k-2} + 4 f_{k-1} + f_k) over the last
               three samples (fourth order for uniform dt); the odd sample in between
               is bridged with a trapezoid.

    NM-METHOD: Numerical integration (Euler / trapezoid / Simpson) | STAGE: 2
    """

    def __init__(self, mode: str = "trapezoid"):
        if mode not in MODES:
            raise ValueError("mode must be one of %s" % (MODES,))
        self.mode = mode
        self.reset()

    def reset(self, value: float = 0.0) -> None:
        self.value = value
        self._base = value                 # simpson: integral up to the last even sample
        self._prev: Optional[float] = None
        self._prev2: Optional[float] = None
        self._h_prev = 0.0

    def update(self, f: float, dt: float) -> float:
        """Add one sample taken dt seconds after the previous one; return the integral."""
        if self.mode == "euler":
            self.value += f * dt
        elif self._prev is None:           # first sample: nothing to integrate yet
            pass
        elif self.mode == "trapezoid":
            self.value += 0.5 * (f + self._prev) * dt
        elif self._prev2 is None:          # simpson, odd sample: provisional trapezoid
            self.value = self._base + 0.5 * (f + self._prev) * dt
            self._prev2, self._h_prev = self._prev, dt
        else:                              # simpson, even sample: close the panel pair
            h = 0.5 * (self._h_prev + dt)
            self._base += (h / 3.0) * (self._prev2 + 4.0 * self._prev + f)
            self.value = self._base
            self._prev2 = None
        self._prev = f
        return self.value

    def clamp(self, lo: float, hi: float) -> None:
        """Anti-windup: limit the stored integral."""
        v = min(max(self.value, lo), hi)
        if v != self.value:
            self.value = v
            self._base = v
            self._prev2 = None


def trapezoid(y: Sequence[float], x: Sequence[float]) -> float:
    """Composite trapezoid rule on (possibly non-uniform) samples.

    NM-METHOD: Composite trapezoid rule | STAGE: 6
    """
    return sum(0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1]) for i in range(1, len(y)))


def simpson(y: Sequence[float], h: float) -> float:
    """Composite Simpson 1/3 rule on UNIFORM samples with spacing h. With an odd number
    of intervals the last one is done with a trapezoid.

    NM-METHOD: Composite Simpson rule | STAGE: 6
    """
    n = len(y) - 1                         # intervals
    if n < 1:
        return 0.0
    m = n - (n % 2)
    total = 0.0
    if m >= 2:
        total = (h / 3.0) * (y[0] + y[m] + 4.0 * sum(y[1:m:2]) + 2.0 * sum(y[2:m:2]))
    if n % 2:
        total += 0.5 * h * (y[n - 1] + y[n])
    return total
