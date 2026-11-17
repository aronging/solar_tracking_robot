"""PID controller with a selectable numerical integration rule (spec 6.2)."""
from __future__ import annotations

from typing import Optional

from ..geometry import wrap180
from ..numerics.integrate import Integrator


class PID:
    """u = Kp e + Ki * integral(e) + Kd * de/dt, saturated to [-u_limit, u_limit].

    - Integral: Euler, trapezoid or Simpson (numerics.integrate.Integrator).
    - Derivative: backward difference with a first-order low-pass (tau = d_filter_tau_s).
      It differentiates the error, which for a constant setpoint equals minus the
      measurement derivative; the first sample contributes 0, so there is no kick.
    - Anti-windup: the integral is clamped so |Ki * I| <= u_limit, and it is frozen while
      the output is saturated in the direction of the error (conditional integration).
    - i_zone: if |e| > i_zone the integral is reset (integral-reset on large error).
    - angular=True wraps error differences to [-180, 180) for heading control.

    NM-METHOD: PID control with numerical integration | STAGE: 2
    """

    def __init__(self, kp: float, ki: float = 0.0, kd: float = 0.0,
                 integral_mode: str = "trapezoid", d_filter_tau_s: float = 0.0,
                 u_limit: float = 1.0, i_zone: Optional[float] = None, angular: bool = False):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.tau = d_filter_tau_s
        self.u_limit = u_limit
        self.i_zone = i_zone
        self.angular = angular
        self.integrator = Integrator(integral_mode)
        self.reset()

    def reset(self) -> None:
        self.integrator.reset()
        self._prev_e: Optional[float] = None
        self._d = 0.0
        self._saturated = 0          # sign of the last saturation, 0 if none
        self.p_term = self.i_term = self.d_term = 0.0

    def update(self, error: float, dt: float) -> float:
        """One control step. dt in seconds since the previous call."""
        if dt <= 0.0:
            raise ValueError("dt must be positive")
        # integral
        if self.i_zone is not None and abs(error) > self.i_zone:
            self.integrator.reset()
        elif not (self._saturated and self._saturated * error > 0.0):
            self.integrator.update(error, dt)
            if self.ki != 0.0:
                lim = self.u_limit / abs(self.ki)
                self.integrator.clamp(-lim, lim)
        # derivative (filtered backward difference)
        if self._prev_e is not None:
            de = error - self._prev_e
            if self.angular:
                de = wrap180(de)
            alpha = dt / (self.tau + dt)
            self._d += alpha * (de / dt - self._d)
        self._prev_e = error

        self.p_term = self.kp * error
        self.i_term = self.ki * self.integrator.value
        self.d_term = self.kd * self._d
        u = self.p_term + self.i_term + self.d_term
        if u > self.u_limit:
            self._saturated, u = 1, self.u_limit
        elif u < -self.u_limit:
            self._saturated, u = -1, -self.u_limit
        else:
            self._saturated = 0
        return u
