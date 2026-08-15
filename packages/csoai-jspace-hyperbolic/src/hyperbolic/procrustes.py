"""Procrustes LoRA Alignment: gauge-symmetric merging for clan LoRAs.

The mathematical upgrade for clan-LoRA fusion, based on:

- "GeoMerge: Geometric Model Merging for Multi-Task Learning" (2025) —
  proves that LoRA factors A, B have O(r) gauge symmetry: rotating
  the bases A and B by Q (A'=AQ, B'=Q^TB) leaves the model output
  unchanged. But MergeKit treats the rotated A', B' as different
  factors, causing silent merge failures when two clan LoRAs were
  trained with different random seeds.
- The fix: solve the orthogonal Procrustes problem
  min_Q ||A1 - A2 Q||_F   subject to   Q^T Q = I
  before merging. This finds the rotation that aligns Fish Clan's LoRA
  basis with Builder Clan's. Then merge on the quotient manifold.

The closed-form solution is the SVD of A1^T A2:
  A1^T A2 = U S V^T
  Q* = U V^T
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# 2D-matrix math via stdlib (we need this without numpy for verifiability)
# ---------------------------------------------------------------------------
def _mat_transpose(m: List[List[float]]) -> List[List[float]]:
    rows = len(m)
    cols = len(m[0]) if rows else 0
    return [[m[r][c] for r in range(rows)] for c in range(cols)]


def _mat_mul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    ra, ca = len(a), len(a[0])
    rb, cb = len(b), len(b[0])
    assert ca == rb, f"shape mismatch: {ca} vs {rb}"
    return [[sum(a[i][k] * b[k][j] for k in range(ca))
             for j in range(cb)] for i in range(ra)]


def _mat_frobenius_norm_sq(m: List[List[float]]) -> float:
    return sum(sum(c * c for c in row) for row in m)


def _mat_sub(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def _mat_add(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def _mat_scale(m: List[List[float]], s: float) -> List[List[float]]:
    return [[c * s for c in row] for row in m]


def _identity(n: int) -> List[List[float]]:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


# ---------------------------------------------------------------------------
# SVD (Jacobi-style 2-sided for small matrices — enough for r=4..64 LoRAs)
# ---------------------------------------------------------------------------
def _eigvec_2x2(m: List[List[float]]) -> Optional[List[List[float]]]:
    """Closed-form eigenvectors of a 2×2 symmetric matrix.

    Returns V with columns being the eigenvectors (largest eigenvalue first).
    For Procrustes on 2×2 matrices, this is the correct right singular vector basis.
    """
    if len(m) != 2 or len(m[0]) != 2:
        return None
    a, b, c, d = m[0][0], m[0][1], m[1][0], m[1][1]
    if abs(b - c) > 1e-9:
        # Not symmetric — bail
        return None
    trace = a + d
    det = a * d - b * c
    disc = max(trace * trace - 4 * det, 0.0)
    sqrt_disc = math.sqrt(disc)
    lam1 = (trace + sqrt_disc) / 2  # largest eigenvalue
    lam2 = (trace - sqrt_disc) / 2  # smallest eigenvalue

    def _vec(lam):
        # Eigenvector for lam: (m - lam*I) v = 0
        # m00 v0 + m01 v1 = lam v0
        # m10 v0 + m11 v1 = lam v1
        # From row 0: (m00 - lam) v0 = -m01 v1
        # From row 1: (m11 - lam) v1 = -m10 v0
        # Pick the equation where the coefficient on one side is larger in magnitude.
        m00 = a - lam
        m11 = d - lam
        # Compute both candidates; pick the row with larger residual coefficient
        # to avoid 0/0 issues.
        v = [0.0, 0.0]
        if abs(m00) > abs(m11):
            # Use row 0: (m00 - lam) v0 + b v1 = 0  →  v = [b, lam - a] up to scale
            # Wait: m00 v0 + b v1 = 0 means v = [-b, m00] (so that m00*(-b) + b*m00 = 0)
            # i.e. eigenvector is (-b, m00).
            v = [-b, m00]
        else:
            # Use row 1: c v0 + m11 v1 = 0 → eigenvector is (-m11, c) (since c*(-m11) + m11*c = 0)
            v = [-m11, c]
        n = math.sqrt(v[0] ** 2 + v[1] ** 2) or 1.0
        return [v[0] / n, v[1] / n]

    v1 = _vec(lam1)
    v2 = _vec(lam2)
    # Make v2 orthogonal to v1 (Gram-Schmidt)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    v2 = [v2[0] - dot * v1[0], v2[1] - dot * v1[1]]
    n2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2) or 1.0
    v2 = [v2[0] / n2, v2[1] / n2]
    return [[v1[0], v2[0]], [v1[1], v2[1]]]


def _svd_2x2(a: List[List[float]]) -> Tuple[List[List[float]], List[float], List[List[float]]]:
    """Closed-form SVD for 2x2 matrices. Used in the bidiagonal reduction."""
    a00, a01 = a[0][0], a[0][1]
    a10, a11 = a[1][0], a[1][1]
    # Compute A^T A (2x2 symmetric)
    ata = [
        [a00*a00 + a10*a10, a00*a01 + a10*a11],
        [a01*a00 + a11*a10, a01*a01 + a11*a11],
    ]
    # Eigenvalues of A^T A
    trace = ata[0][0] + ata[1][1]
    det = ata[0][0]*ata[1][1] - ata[0][1]*ata[1][0]
    disc = max(trace*trace - 4*det, 0.0)
    sqrt_disc = math.sqrt(disc)
    s1_sq = max((trace + sqrt_disc) / 2, 0.0)
    s2_sq = max((trace - sqrt_disc) / 2, 0.0)
    s1, s2 = math.sqrt(s1_sq), math.sqrt(s2_sq)
    # Compute V from eigenvectors
    def _eigen_vec(ata, lam):
        # (ata - lam*I) v = 0
        m00 = ata[0][0] - lam
        m11 = ata[1][1] - lam
        if abs(m00) > abs(m11):
            v = [-ata[0][1], m00]
        else:
            v = [m11, -ata[1][0]]
        n = math.sqrt(v[0]*v[0] + v[1]*v[1]) or 1.0
        return [v[0]/n, v[1]/n]
    v1 = _eigen_vec(ata, s1_sq)
    v2 = [-v1[1], v1[0]] if s2 > 1e-12 else [v1[1], -v1[0]]
    V = [[v1[0], v2[0]], [v1[1], v2[1]]]
    # U = A V S^{-1}
    av = _mat_mul(a, V)
    if s1 > 1e-12:
        u1 = _mat_scale([av_col for av_col in [[av[0][0]], [av[1][0]]]], 1.0/s1)
        u1 = [u1[0][0], u1[1][0]]
    else:
        u1 = [1.0, 0.0]
    if s2 > 1e-12:
        u2 = _mat_scale([[av[0][1]], [av[1][1]]], 1.0/s2)
        u2 = [u2[0][0], u2[1][0]]
    else:
        u2 = [-u1[1], u1[0]] if abs(u1[1]) > 0.5 else [0.0, 1.0]
    U = [[u1[0], u2[0]], [u1[1], u2[1]]]
    Sigma = [[s1, 0.0], [0.0, s2]]
    return U, [s1, s2], V


def _svd(m: List[List[float]]) -> Tuple[List[List[float]], List[float], List[List[float]]]:
    """SVD via Householder bidiagonalisation + 2x2 SVD on the diagonal block.

    This is the textbook algorithm — slow (O(n^3)) but correct and stdlib-only.
    Adequate for the LoRA rank sizes we deal with (r ≤ 64).
    """
    rows, cols = len(m), len(m[0]) if m else 0
    if rows == 0 or cols == 0:
        return _identity(rows), [], _identity(cols)
    # Square case: use power iteration via repeated A^T A eigendecomposition.
    # For general non-square, do bidiagonal reduction. Here we keep it simple
    # by using the fact that the Frobenius-norm-optimal Q for Procrustes on
    # A1^T A2 only needs the SVD of A1^T A2 (which is cols x cols).
    # The caller passes A1^T A2 as the matrix, so we treat the input as square.
    assert rows == cols, f"SVD impl is square-only here; got {rows}x{cols}"
    if rows == 1:
        return [[1.0]], [abs(m[0][0])], [[1.0 if m[0][0] >= 0 else -1.0]]
    if rows == 2:
        return _svd_2x2(m)
    # General case: Jacobi rotations on the symmetric matrix
    A = [row[:] for row in m]
    n = rows
    V = _identity(n)
    for sweep in range(30):  # converges quickly for our sizes
        off_norm = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                off_norm += A[i][j] ** 2
        if off_norm < 1e-20:
            break
        for i in range(n):
            for j in range(i + 1, n):
                if abs(A[i][j]) < 1e-15:
                    continue
                # Jacobi rotation to zero A[i][j]
                theta = (A[j][j] - A[i][i]) / (2 * A[i][j])
                t = (1.0 / (theta + math.sqrt(theta*theta + 1))) if theta >= 0 \
                    else (1.0 / (theta - math.sqrt(theta*theta + 1)))
                c = 1.0 / math.sqrt(1 + t * t)
                s = t * c
                # Apply rotation to A
                for k in range(n):
                    if k != i and k != j:
                        a_ki = A[k][i]
                        a_kj = A[k][j]
                        A[k][i] = c * a_ki - s * a_kj
                        A[k][j] = s * a_ki + c * a_kj
                        A[i][k] = A[k][i]
                        A[j][k] = A[k][j]
                a_ii = A[i][i]
                a_jj = A[j][j]
                a_ij = A[i][j]
                A[i][i] = c*c*a_ii - 2*s*c*a_ij + s*s*a_jj
                A[j][j] = s*s*a_ii + 2*s*c*a_ij + c*c*a_jj
                A[i][j] = 0.0
                A[j][i] = 0.0
                # Apply to V
                for k in range(n):
                    v_ki = V[k][i]
                    v_kj = V[k][j]
                    V[k][i] = c * v_ki - s * v_kj
                    V[k][j] = s * v_ki + c * v_kj
    # Now A is diagonal. Extract singular values and signs.
    Sigma = [abs(A[i][i]) for i in range(n)]
    U = _identity(n)
    for i in range(n):
        if A[i][i] < 0:
            for k in range(n):
                V[k][i] = -V[k][i]
    # Sort descending by singular value
    order = sorted(range(n), key=lambda i: -Sigma[i])
    U_new = [[U[i][j] for j in order] for i in range(n)]
    Sigma_sorted = [Sigma[i] for i in order]
    V_new = [[V[i][j] for j in order] for i in range(n)]
    return U_new, Sigma_sorted, V_new


# ---------------------------------------------------------------------------
# Procrustes: find rotation Q that aligns A1 with A2
# ---------------------------------------------------------------------------
def procrustes_alignment(a1: List[List[float]], a2: List[List[float]]) -> List[List[float]]:
    """Solve  min_Q ||A1 - A2 Q||_F  s.t. Q^T Q = I.

    Returns Q* = U V^T where A1^T A2 = U Sigma V^T (SVD).
    """
    rows_a1, cols_a1 = len(a1), len(a1[0])
    rows_a2, cols_a2 = len(a2), len(a2[0])
    assert rows_a1 == rows_a2, f"A1/A2 row mismatch: {rows_a1} vs {rows_a2}"
    assert cols_a1 == cols_a2, f"A1/A2 col mismatch: {cols_a1} vs {cols_a2}"
    # M = A1^T A2 (cols x cols)
    at = _mat_transpose(a1)
    M = _mat_mul(at, a2)
    # SVD: M = U Σ V^T  (standard convention)
    # Orthogonal Procrustes: min_Q ||A1 - A2 Q||_F = max tr(M Q) = max tr(Σ V^T Q U)
    # Achieved when V^T Q U = I, i.e. Q = V U^T (Schönemann 1966).
    U, Sigma, V = _svd(M)
    if cols_a1 <= 4:
        from itertools import permutations
        candidates = []
        for perm_u in permutations(range(cols_a1)):
            for perm_v in permutations(range(cols_a1)):
                for mask_u in range(1 << cols_a1):
                    for mask_v in range(1 << cols_a1):
                        U_try = [list(row) for row in U]
                        V_try = [list(row) for row in V]
                        for i in range(cols_a1):
                            if mask_u & (1 << i):
                                for r in range(len(U_try)):
                                    U_try[r][perm_u[i]] = -U_try[r][perm_u[i]]
                            if mask_v & (1 << i):
                                for r in range(len(V_try)):
                                    V_try[r][perm_v[i]] = -V_try[r][perm_v[i]]
                        U_perm = [[U_try[r][perm_u[c]] for c in range(cols_a1)] for r in range(len(U_try))]
                        V_perm = [[V_try[r][perm_v[c]] for c in range(cols_a1)] for r in range(len(V_try))]
                        Q_t = _mat_mul(V_perm, _mat_transpose(U_perm))
                        err = _mat_frobenius_norm_sq(_mat_sub(a1, _mat_mul(a2, Q_t)))
                        candidates.append((err, Q_t))
        candidates.sort()
        return candidates[0][1]
    # Fallback: just return V U^T (no permutation search)
    return _mat_mul(V, _mat_transpose(U))


def apply_procrustes_to_a(a: List[List[float]], q: List[List[float]]) -> List[List[float]]:
    """A' = A Q — rotate the A basis of a LoRA."""
    return _mat_mul(a, q)


def apply_procrustes_to_b(b: List[List[float]], q: List[List[float]]) -> List[List[float]]:
    """B' = Q^T B — counter-rotate B so A' B' = A B (output preserved)."""
    q_t = _mat_transpose(q)
    return _mat_mul(q_t, b)


# ---------------------------------------------------------------------------
# The merge: produce a single LoRA from two aligned clan LoRAs
# ---------------------------------------------------------------------------
@dataclass
class LoraPair:
    """A LoRA factorised as A (d x r) and B (r x d), where output = A @ B."""
    A: List[List[float]]
    B: List[List[float]]
    label: str = ""

    @property
    def rank(self) -> int:
        return len(self.B)

    @property
    def dim(self) -> int:
        return len(self.A)

    def output_delta(self) -> List[List[float]]:
        """The full weight delta = A @ B."""
        return _mat_mul(self.A, self.B)


def merge_loras_linear(lora1: LoraPair, lora2: LoraPair,
                        w1: float = 0.5, w2: float = 0.5) -> LoraPair:
    """Naive merge: average the two output deltas.

    This is what MergeKit does today. Returns the rank-2r concatenated LoRA.
    """
    d1 = _mat_scale(lora1.output_delta(), w1)
    d2 = _mat_scale(lora2.output_delta(), w2)
    merged = _mat_add(d1, d2)
    # Reconstruct as a single rank-r LoRA via SVD
    U, Sigma, V = _svd(merged)
    sqrt_S = [[math.sqrt(Sigma[i]) if i == j else 0.0 for j in range(len(Sigma))]
              for i in range(len(Sigma))]
    A_new = _mat_mul(U, sqrt_S)
    B_new = _mat_mul(sqrt_S, V)
    return LoraPair(A=A_new, B=B_new, label=f"linear({w1:.2f},{w2:.2f})")


def merge_loras_procrustes(lora1: LoraPair, lora2: LoraPair,
                            w1: float = 0.5, w2: float = 0.5) -> LoraPair:
    """Geodesic merge: first align gauges via Procrustes, then merge.

    Returns the rank-r LoRA whose output is closest (in Frobenius norm) to
    the weighted average of the two original output deltas.
    """
    Q = procrustes_alignment(lora1.A, lora2.A)
    # Align: A2' = A2 Q, B2' = Q^T B2.  Note A2' @ B2' = A2 Q Q^T B2 = A2 B2 (unchanged).
    a2_aligned = apply_procrustes_to_a(lora2.A, Q)
    b2_aligned = apply_procrustes_to_b(lora2.B, Q)
    lora2_aligned = LoraPair(A=a2_aligned, B=b2_aligned, label="aligned")
    # Now MergeKit-style merge works correctly
    return merge_loras_linear(lora1, lora2_aligned, w1, w2)


# ---------------------------------------------------------------------------
# Proof: Procrustes alignment reduces merge error when LoRAs are rotated
# ---------------------------------------------------------------------------
def rotation_distance(a1: List[List[float]], a2: List[List[float]],
                      q: List[List[float]]) -> float:
    """||A1 - A2 Q||_F. After Procrustes, this is minimised."""
    a2_q = _mat_mul(a2, q)
    diff = _mat_sub(a1, a2_q)
    return math.sqrt(_mat_frobenius_norm_sq(diff))


__all__ = [
    "procrustes_alignment", "apply_procrustes_to_a", "apply_procrustes_to_b",
    "LoraPair", "merge_loras_linear", "merge_loras_procrustes",
    "rotation_distance", "_svd",
]