import math

import numpy as np
import pytest

from solar_tracker.numerics.leastsq import cosine_design
from solar_tracker.numerics.linalg import (SingularMatrixError, cond1, cond2_spd, inverse,
                                           lu_decompose, lu_solve, matmul, solve)


def _relerr(x, ref):
    return np.linalg.norm(np.array(x) - ref) / np.linalg.norm(ref)


@pytest.mark.parametrize("n", [3, 8])
def test_solve_matches_numpy_on_random_systems(n):
    rng = np.random.default_rng(100 + n)
    for _ in range(50):
        A, b = rng.normal(size=(n, n)), rng.normal(size=n)
        if np.linalg.cond(A) > 1e4:            # keep the reference itself accurate to 1e-10
            continue
        assert _relerr(solve(A.tolist(), b.tolist()), np.linalg.solve(A, b)) < 1e-10


@pytest.mark.parametrize("n", [3, 8])
def test_lu_factors_reproduce_PA_and_determinant(n):
    A = np.random.default_rng(n).normal(size=(n, n))
    LU, perm, sign = lu_decompose(A.tolist())
    LU = np.array(LU)
    L, U = np.tril(LU, -1) + np.eye(n), np.triu(LU)
    assert np.allclose(L @ U, A[perm], atol=1e-12)
    assert np.abs(np.tril(LU, -1)).max() <= 1.0 + 1e-12           # partial pivoting bounds L
    assert sign * np.prod(np.diag(U)) == pytest.approx(np.linalg.det(A), rel=1e-10)


def test_matrix_needing_pivoting():
    A = [[0.0, 2.0, 1.0], [1.0, 1.0, 0.0], [2.0, 0.0, 3.0]]
    b = [5.0, 3.0, 11.0]
    LU, perm, sign = lu_decompose(A)
    assert perm != [0, 1, 2] and sign in (1, -1)
    assert _relerr(lu_solve(LU, perm, b), np.linalg.solve(np.array(A), np.array(b))) < 1e-12
    assert solve([[0.0, 1.0], [1.0, 0.0]], [3.0, 4.0]) == pytest.approx([4.0, 3.0])


@pytest.mark.parametrize("A", [
    [[1.0, 2.0, 3.0], [2.0, 4.0, 6.0], [1.0, 0.0, 1.0]],          # dependent rows
    [[1.0, 2.0], [0.5, 1.0]],
    [[0.0, 0.0], [0.0, 0.0]],
    [[1e6, 1.0], [1e6, 1.0 + 1e-9]],                                # pivot < 1e-12 * max|A|
])
def test_singular_matrix_raises(A):
    with pytest.raises(SingularMatrixError):
        lu_decompose(A)
    with pytest.raises(SingularMatrixError):
        solve(A, [1.0] * len(A))
    assert cond1(A) == math.inf and cond2_spd(A) == math.inf


def test_non_square_is_invalid_input():
    with pytest.raises(ValueError):
        lu_decompose([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])


@pytest.mark.parametrize("n", [3, 8])
def test_inverse_times_A_is_identity(n):
    A = np.random.default_rng(7 * n).normal(size=(n, n)) + n * np.eye(n)
    inv = inverse(A.tolist())
    assert np.allclose(matmul(inv, A.tolist()), np.eye(n), atol=1e-12)
    assert np.allclose(inv, np.linalg.inv(A), atol=1e-12)


def test_cond2_spd_matches_numpy_within_1_percent():
    rng = np.random.default_rng(42)
    for _ in range(100):
        B = rng.normal(size=(3, 3))
        A = B @ B.T + 1e-3 * np.eye(3)
        assert cond2_spd(A.tolist()) == pytest.approx(np.linalg.cond(A, 2), rel=0.01)


@pytest.mark.parametrize("spread, K", [(15, 7), (10, 5), (20, 6), (5, 7)])
def test_cond_of_cosine_normal_matrix(spread, K):
    M = np.array(cosine_design(np.linspace(-spread, spread, K)))
    MtM = M.T @ M
    c = cond2_spd(MtM.tolist())
    assert c == pytest.approx(np.linalg.cond(MtM, 2), rel=0.01)
    s = np.linalg.svd(M, compute_uv=False)
    assert c == pytest.approx((s[0] / s[-1]) ** 2, rel=0.01)       # cond2(MtM) = cond2(M)^2
    c1 = cond1(MtM.tolist())
    assert c1 == pytest.approx(np.linalg.cond(MtM, 1), rel=1e-6)
    assert c / 3 <= c1 <= 3 * c                                     # norms equivalent within n
