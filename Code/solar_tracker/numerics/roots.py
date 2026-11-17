"""Scalar root finding: fixed-point, Newton-Raphson, bisection, false position, secant.

Pure functions on plain floats. Nothing prints; non-convergence returns
``converged=False`` (only invalid input raises ValueError). Every result carries
the per-iteration history for convergence plots.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class RootResult:
    value: float
    converged: bool
    iterations: int
    history: List[Dict[str, float]] = field(default_factory=list)  # {"k", "x", "residual"}
    reason: str = ""


def fixed_point(g: Callable[[float], float], x0: float, tol: float = 1e-12,
                max_iter: int = 200) -> RootResult:
    """Iterate x_{k+1} = g(x_k) until |x_{k+1} - x_k| < tol. Linear convergence, rate |g'(x*)|.

    NM-METHOD: Fixed-point iteration | STAGE: 1
    """
    x = x0
    hist: List[Dict[str, float]] = []
    for k in range(1, max_iter + 1):
        x_new = g(x)
        step = abs(x_new - x)
        hist.append({"k": k, "x": x_new, "residual": step})
        x = x_new
        if step < tol:
            return RootResult(x, True, k, hist, "step < tol")
    return RootResult(x, False, max_iter, hist, "max_iter reached")


def newton(f: Callable[[float], float], df: Callable[[float], float], x0: float,
           tol: float = 1e-12, max_iter: int = 50) -> RootResult:
    """Newton-Raphson x_{k+1} = x_k - f(x_k)/f'(x_k). Quadratic convergence near a simple root.

    NM-METHOD: Newton-Raphson | STAGE: 1
    """
    x = x0
    hist: List[Dict[str, float]] = []
    for k in range(1, max_iter + 1):
        d = df(x)
        if d == 0.0:
            return RootResult(x, False, k - 1, hist, "zero derivative")
        x_new = x - f(x) / d
        step = abs(x_new - x)
        hist.append({"k": k, "x": x_new, "residual": step})
        x = x_new
        if step < tol:
            return RootResult(x, True, k, hist, "step < tol")
    return RootResult(x, False, max_iter, hist, "max_iter reached")


def _bracket(f: Callable[[float], float], a: float, b: float):
    fa, fb = f(a), f(b)
    if fa * fb > 0.0:
        raise ValueError("f(a) and f(b) must have opposite signs")
    return fa, fb


def bisection(f: Callable[[float], float], a: float, b: float, tol: float = 1e-9,
              max_iter: int = 200) -> RootResult:
    """Halve a sign-change bracket until its width < tol. Guaranteed, one bit per step.

    NM-METHOD: Bisection | STAGE: 1
    """
    fa, fb = _bracket(f, a, b)
    hist: List[Dict[str, float]] = []
    c = 0.5 * (a + b)
    for k in range(1, max_iter + 1):
        c = 0.5 * (a + b)
        fc = f(c)
        hist.append({"k": k, "x": c, "residual": abs(fc), "width": b - a})
        if fc == 0.0 or abs(b - a) < tol:
            return RootResult(c, True, k, hist, "bracket < tol")
        if fa * fc < 0.0:
            b, fb = c, fc
        else:
            a, fa = c, fc
    return RootResult(c, False, max_iter, hist, "max_iter reached")


def false_position(f: Callable[[float], float], a: float, b: float, tol: float = 1e-9,
                   max_iter: int = 200) -> RootResult:
    """Regula falsi: root of the chord through the bracket ends; stops when the estimate moves < tol.

    NM-METHOD: False position (regula falsi) | STAGE: 1
    """
    fa, fb = _bracket(f, a, b)
    hist: List[Dict[str, float]] = []
    c = a
    for k in range(1, max_iter + 1):
        c_new = b - fb * (b - a) / (fb - fa)
        fc = f(c_new)
        step = abs(c_new - c)
        c = c_new
        hist.append({"k": k, "x": c, "residual": abs(fc), "width": b - a})
        if fc == 0.0 or (k > 1 and step < tol):
            return RootResult(c, True, k, hist, "step < tol")
        if fa * fc < 0.0:
            b, fb = c, fc
        else:
            a, fa = c, fc
    return RootResult(c, False, max_iter, hist, "max_iter reached")


def secant(f: Callable[[float], float], x0: float, x1: float, tol: float = 1e-12,
           max_iter: int = 50) -> RootResult:
    """Newton with the derivative replaced by a finite difference of the last two iterates.

    NM-METHOD: Secant | STAGE: 4
    """
    f0, f1 = f(x0), f(x1)
    hist: List[Dict[str, float]] = []
    for k in range(1, max_iter + 1):
        if f1 == f0:
            return RootResult(x1, False, k - 1, hist, "flat secant")
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
        step = abs(x2 - x1)
        x0, f0, x1, f1 = x1, f1, x2, f(x2)
        hist.append({"k": k, "x": x1, "residual": step})
        if step < tol:
            return RootResult(x1, True, k, hist, "step < tol")
    return RootResult(x1, False, max_iter, hist, "max_iter reached")
