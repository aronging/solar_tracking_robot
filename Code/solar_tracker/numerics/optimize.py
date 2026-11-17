"""1-D maximisation: golden-section search and parabolic (3-point) interpolation."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence, Tuple

GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0   # 0.618...


@dataclass
class SearchResult:
    value: float                       # x of the best evaluated point
    f_value: float
    converged: bool
    iterations: int
    evals: int
    a: float                           # final bracket
    b: float
    history: List[Dict[str, float]] = field(default_factory=list)  # {"k","x","f","width"}
    points: List[Tuple[float, float]] = field(default_factory=list)  # every (x, f) evaluated
    reason: str = ""


def golden_section_max(f: Callable[[float], float], a: float, b: float, tol: float = 1e-6,
                       max_evals: int = 100) -> SearchResult:
    """Maximise a unimodal f on [a, b]. The bracket shrinks by 0.618 per iteration and
    one interior point is reused, so each iteration costs exactly one new evaluation.

    NM-METHOD: Golden-section search | STAGE: 3
    """
    if b < a:
        a, b = b, a
    x1, x2 = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
    f1, f2 = f(x1), f(x2)
    pts = [(x1, f1), (x2, f2)]
    hist = [{"k": 0, "x": x1 if f1 >= f2 else x2, "f": max(f1, f2), "width": b - a}]
    k = 0
    while (b - a) > tol and len(pts) < max_evals:
        k += 1
        if f1 >= f2:                    # maximum lies in [a, x2]
            b, x2, f2 = x2, x1, f1
            x1 = b - GOLDEN * (b - a)
            f1 = f(x1)
            pts.append((x1, f1))
        else:                           # maximum lies in [x1, b]
            a, x1, f1 = x1, x2, f2
            x2 = a + GOLDEN * (b - a)
            f2 = f(x2)
            pts.append((x2, f2))
        hist.append({"k": k, "x": x1 if f1 >= f2 else x2, "f": max(f1, f2), "width": b - a})
    xb, fb = (x1, f1) if f1 >= f2 else (x2, f2)
    done = (b - a) <= tol
    return SearchResult(xb, fb, done, k, len(pts), a, b, hist, pts,
                        "width <= tol" if done else "max_evals reached")


def parabolic_vertex(x3: Sequence[float], f3: Sequence[float]) -> float:
    """Vertex of the parabola through three points. Returns nan when the points are
    collinear/duplicated or the parabola opens upward (no maximum).

    NM-METHOD: Parabolic interpolation | STAGE: 3
    """
    (x0, x1, x2), (f0, f1, f2) = x3, f3
    d01, d02, d12 = x0 - x1, x0 - x2, x1 - x2
    if d01 == 0.0 or d02 == 0.0 or d12 == 0.0:
        return math.nan
    # Lagrange form: second-derivative coefficient and vertex
    curv = f0 / (d01 * d02) - f1 / (d01 * d12) + f2 / (d02 * d12)
    if not curv < 0.0:
        return math.nan
    num = f0 * (x1 + x2) / (d01 * d02) - f1 * (x0 + x2) / (d01 * d12) + f2 * (x0 + x1) / (d02 * d12)
    return num / (2.0 * curv)
