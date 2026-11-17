"""Dense linear algebra on lists of lists: LU with partial pivoting, solve, inverse, condition numbers.

Matrices are ``List[List[float]]`` (row major); nothing is special-cased to 3x3.
"""
from __future__ import annotations

import math
from typing import List, Tuple

Matrix = List[List[float]]
Vector = List[float]


class SingularMatrixError(ValueError):
    """Raised when a pivot is below 1e-12 * max|A|."""


def transpose(A: Matrix) -> Matrix:
    return [list(col) for col in zip(*A)]


def matmul(A: Matrix, B: Matrix) -> Matrix:
    Bt = transpose(B)
    return [[sum(a * b for a, b in zip(row, col)) for col in Bt] for row in A]


def matvec(A: Matrix, x: Vector) -> Vector:
    return [sum(a * b for a, b in zip(row, x)) for row in A]


def lu_decompose(A: Matrix) -> Tuple[Matrix, List[int], int]:
    """Doolittle LU with partial (row) pivoting: P A = L U.

    Returns (LU, perm, sign): L (unit diagonal) below and U on/above the diagonal of
    one matrix, the row permutation, and the determinant sign (+1/-1).

    NM-METHOD: LU decomposition with partial pivoting | STAGE: 4
    """
    n = len(A)
    if n == 0 or any(len(r) != n for r in A):
        raise ValueError("matrix must be square and non-empty")
    LU = [list(map(float, r)) for r in A]
    perm = list(range(n))
    sign = 1
    tiny = 1e-12 * max(abs(v) for r in LU for v in r)
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(LU[i][k]))
        if abs(LU[p][k]) <= tiny:
            raise SingularMatrixError("pivot %d below 1e-12*max|A|" % k)
        if p != k:
            LU[k], LU[p] = LU[p], LU[k]
            perm[k], perm[p] = perm[p], perm[k]
            sign = -sign
        for i in range(k + 1, n):
            LU[i][k] /= LU[k][k]
            m = LU[i][k]
            for j in range(k + 1, n):
                LU[i][j] -= m * LU[k][j]
    return LU, perm, sign


def lu_solve(LU: Matrix, perm: List[int], b: Vector) -> Vector:
    """Solve A x = b from an LU factorisation: forward then back substitution.

    NM-METHOD: Forward/back substitution | STAGE: 4
    """
    n = len(LU)
    y = [0.0] * n
    for i in range(n):                       # L y = P b
        y[i] = b[perm[i]] - sum(LU[i][j] * y[j] for j in range(i))
    x = [0.0] * n
    for i in range(n - 1, -1, -1):           # U x = y
        x[i] = (y[i] - sum(LU[i][j] * x[j] for j in range(i + 1, n))) / LU[i][i]
    return x


def solve(A: Matrix, b: Vector) -> Vector:
    """Solve A x = b (decompose + substitute)."""
    LU, perm, _ = lu_decompose(A)
    return lu_solve(LU, perm, b)


def inverse(A: Matrix) -> Matrix:
    """A^-1 by solving against the identity columns with one LU."""
    n = len(A)
    LU, perm, _ = lu_decompose(A)
    cols = [lu_solve(LU, perm, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return transpose(cols)


def norm1(A: Matrix) -> float:
    """Induced 1-norm: maximum absolute column sum."""
    return max(sum(abs(v) for v in col) for col in zip(*A))


def cond1(A: Matrix) -> float:
    """1-norm condition number ||A||_1 ||A^-1||_1 (inf if singular).

    NM-METHOD: Condition number (1-norm) | STAGE: 4
    """
    try:
        return norm1(A) * norm1(inverse(A))
    except SingularMatrixError:
        return math.inf


def cond2_spd(A: Matrix, tol: float = 1e-10, max_iter: int = 500) -> float:
    """2-norm condition number of a symmetric positive-definite matrix = lambda_max/lambda_min.

    lambda_max by power iteration on A; lambda_min by inverse iteration (power
    iteration on A^-1, each step one LU solve). Returns inf if A is singular.

    NM-METHOD: Condition number (power + inverse iteration) | STAGE: 4
    """
    n = len(A)
    try:
        LU, perm, _ = lu_decompose(A)
    except SingularMatrixError:
        return math.inf

    def dominant(step) -> float:
        # start vector with unequal entries so it is not orthogonal to an eigenvector by symmetry
        v = [1.0 + 0.37 * i for i in range(n)]
        lam = 0.0
        for _ in range(max_iter):
            nv = math.sqrt(sum(x * x for x in v))
            v = [x / nv for x in v]
            w = step(v)
            lam_new = sum(a * b for a, b in zip(v, w))      # Rayleigh quotient
            v = w
            if abs(lam_new - lam) <= tol * abs(lam_new):
                return lam_new
            lam = lam_new
        return lam

    lam_max = dominant(lambda v: matvec(A, v))
    inv_lam_min = dominant(lambda v: lu_solve(LU, perm, v))
    return lam_max * inv_lam_min
