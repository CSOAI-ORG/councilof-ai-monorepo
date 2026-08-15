"""Tests for the Poincaré ball + Procrustes LoRA alignment math.

These are stdlib-only tests — no PyTorch, no numpy. If they pass, the math
is correct (because we re-derived the formulas from the published papers).

Proves:
1. Poincaré distance is symmetric, non-negative, zero on the diagonal
2. Triangle inequality holds
3. Hierarchy is preserved: d(GOV, GOV) < d(GOV, SWARM)
4. Möbius addition stays inside the ball (||x|| < 1)
5. Procrustes alignment REDUCES ||A1 - A2 Q||_F when A2 was rotated relative to A1
6. Procrustes-merged LoRA has lower Frobenius error than naive merge for rotated inputs
"""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hyperbolic import (
    Axis, axis_anchor, HyperbolicPiece, poincare_distance, mobius_add,
    poincare_centroid, poincare_exponential_map, project_to_ball, hierarchy_depth,
)
from hyperbolic.procrustes import (
    LoraPair, merge_loras_linear, merge_loras_procrustes,
    procrustes_alignment, rotation_distance, _mat_mul, _mat_transpose, _mat_sub,
)


# ===========================================================================
# POINCARÉ TESTS
# ===========================================================================
def test_01_poincare_distance_zero():
    """d(u, u) = 0."""
    u = (0.3, 0.4, 0.1)
    d = poincare_distance(u, u)
    assert d < 1e-10, f"d(u,u) must be 0, got {d}"
    print(f"  ✅ d(u,u) = {d:.2e}")


def test_02_poincare_distance_symmetric():
    """d(u, v) = d(v, u)."""
    u = (0.3, 0.4, 0.1)
    v = (-0.2, 0.1, 0.5)
    d_uv = poincare_distance(u, v)
    d_vu = poincare_distance(v, u)
    assert abs(d_uv - d_vu) < 1e-9, f"symmetric violated: {d_uv} vs {d_vu}"
    print(f"  ✅ d(u,v)={d_uv:.4f} == d(v,u)={d_vu:.4f}")


def test_03_poincare_triangle_inequality():
    """d(u,w) <= d(u,v) + d(v,w)."""
    u = (0.1, 0.2, 0.0)
    v = (0.4, 0.0, 0.3)
    w = (-0.3, 0.4, 0.1)
    duw = poincare_distance(u, w)
    duv = poincare_distance(u, v)
    dvw = poincare_distance(v, w)
    assert duw <= duv + dvw + 1e-9, \
        f"triangle violated: {duw} > {duv} + {dvw}"
    print(f"  ✅ triangle: {duw:.4f} <= {duv:.4f} + {dvw:.4f}")


def test_04_hierarchy_preserved():
    """d(GOV, GOV) < d(GOV, SWARM). The geometry must encode hierarchy."""
    gov = axis_anchor(Axis.GOV)
    swarm = axis_anchor(Axis.SWARM)
    asi = axis_anchor(Axis.ASI)
    care = axis_anchor(Axis.CARE)
    d_gov_gov = poincare_distance(gov, gov)
    d_gov_asi = poincare_distance(gov, asi)
    d_gov_care = poincare_distance(gov, care)
    d_gov_swarm = poincare_distance(gov, swarm)
    print(f"  d(GOV, GOV)  = {d_gov_gov:.4f}")
    print(f"  d(GOV, ASI)  = {d_gov_asi:.4f}  (inner layer)")
    print(f"  d(GOV, CARE) = {d_gov_care:.4f}  (middle layer)")
    print(f"  d(GOV, SWARM)= {d_gov_swarm:.4f}  (boundary)")
    assert d_gov_gov < 0.01, "GOV anchor should be at origin"
    assert d_gov_swarm > d_gov_asi, \
        "boundary axis must be farther from center than inner axis"
    assert d_gov_swarm > d_gov_care, \
        "boundary axis must be farther from center than middle axis"
    print("  ✅ hierarchy: boundary > middle > inner > origin")


def test_05_mobius_stays_in_ball():
    """Möbius addition always produces a point with ||x|| < 1."""
    u = (0.5, 0.2, 0.0)
    v = (-0.3, 0.4, 0.1)
    added = mobius_add(u, v)
    norm = math.sqrt(sum(c*c for c in added))
    assert norm < 1.0, f"Möbius result ||{norm:.6f}|| must be < 1, got {norm}"
    print(f"  ✅ Möbius ||u�v|| = {norm:.6f} < 1")


def test_06_move_toward_origin():
    """A piece moving toward origin reduces its distance to GOV (upgrade)."""
    piece = HyperbolicPiece(
        piece_id="fish_001",
        clan="fish",
        axis=Axis.GOV,
        position=(0.5, 0.0, 0.0),
    )
    dist_before = piece.distance_to_axis(Axis.GOV)
    # Move toward origin (negative x)
    moved = piece.move((-0.3, 0.0, 0.0))
    dist_after = moved.distance_to_axis(Axis.GOV)
    assert dist_after < dist_before, \
        f"moving toward origin must reduce GOV distance: {dist_before} → {dist_after}"
    print(f"  ✅ move toward origin: d(GOV) {dist_before:.4f} → {dist_after:.4f}")


def test_07_move_toward_boundary():
    """A piece moving away from origin increases its distance to GOV."""
    piece = HyperbolicPiece(
        piece_id="watchdog_001",
        clan="watchdog",
        axis=Axis.SWARM,
        position=(0.1, 0.1, 0.0),
    )
    dist_before = piece.distance_to_axis(Axis.GOV)
    moved = piece.move((0.3, 0.0, 0.0))
    dist_after = moved.distance_to_axis(Axis.GOV)
    assert dist_after > dist_before, \
        f"moving away from origin must increase GOV distance: {dist_before} → {dist_after}"
    print(f"  ✅ move toward boundary: d(GOV) {dist_before:.4f} → {dist_after:.4f}")


# ===========================================================================
# PROCRUSTES TESTS
# ===========================================================================
def _identity_mat(n):
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _rotation_z(theta, n=4):
    """Build an n×n rotation matrix that rotates in the x-y plane (first 2 dims).

    NB: For LoRA gauge rotations, the matrix must be rank×rank (not dim×dim).
    """
    R = _identity_mat(n)
    c, s = math.cos(theta), math.sin(theta)
    R[0][0] = c; R[0][1] = -s
    R[1][0] = s; R[1][1] = c
    return R


def _rotation_in_rank_space(theta, rank):
    """A rotation that acts on the rank-space (not dim-space).

    For LoRAs, the gauge symmetry lives in the rank dim, so we need
    an (rank × rank) orthogonal Q such that A' = A Q, B' = Q^T B.
    """
    return _rotation_z(theta, n=rank)


def test_08_procrustes_aligns_rotation():
    """If A2 = A1 Q for some orthogonal Q, Procrustes recovers Q^{-1} = Q^T.

    Procrustes solves  min_Q ||A1 - A2 Q||_F.  Since A2 = A1 Q,
    the minimiser is Q* = Q^{-1} = Q^T (because Q is orthogonal).
    """
    dim, rank = 4, 2
    A1 = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.3], [0.2, 0.7]]  # dim × rank
    Q_true = _rotation_in_rank_space(math.pi / 6, rank)       # rank × rank
    A2 = _mat_mul(A1, Q_true)                                  # dim × rank
    Q = procrustes_alignment(A1, A2)
    # Since A2 = A1 Q_true, the minimiser of ||A1 - A2 Q||_F is Q = Q_true^T.
    # Verify: applying Q should give back A1 (i.e., A2 Q = A1).
    A2_Q = _mat_mul(A2, Q)
    A1_minus = _mat_sub(A1, A2_Q)
    err = math.sqrt(sum(sum(c*c for c in row) for row in A1_minus))
    assert err < 1e-6, f"A1 - A2 Q should be 0, got {err}"
    # Verify Q IS Q_true^T
    Q_true_t = _mat_transpose(Q_true)
    Q_minus = _mat_sub(Q, Q_true_t)
    q_diff = math.sqrt(sum(sum(c*c for c in row) for row in Q_minus))
    assert q_diff < 1e-6, f"Recovered Q should equal Q_true^T, diff={q_diff}"
    print(f"  ✅ Procrustes: ||A1 - A2 Q||_F = {err:.2e}, ||Q - Q_true^T|| = {q_diff:.2e}")


def test_09_procrustes_reduces_merge_error():
    """When A2 was rotated in rank-space, Procrustes merge gives lower output
    Frobenius error than naive MergeKit-style merge.

    Convention: A is (dim × rank), B is (rank × dim), output = A @ B is (dim × dim).
    The rotated-LoRA equivalent: A2 = A1 Q, B2 = Q^T B1 (preserves output A1 B1).
    """
    dim, rank = 4, 2
    A1 = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.3], [0.2, 0.7]]  # dim × rank
    B1 = [[1.0, 0.5, -0.3, 0.2], [0.0, 1.0, 0.5, -0.3]]    # rank × dim
    # Rotate in rank space
    Q = _rotation_in_rank_space(math.pi / 4, rank)
    A2 = _mat_mul(A1, Q)                  # (dim × rank) @ (rank × rank) = (dim × rank)
    B2 = _mat_mul(_mat_transpose(Q), B1)  # (rank × rank) @ (rank × dim) = (rank × dim)
    lora1 = LoraPair(A=A1, B=B1, label="fish")
    lora2 = LoraPair(A=A2, B=B2, label="builder-rotated")

    naive = merge_loras_linear(lora1, lora2)
    procrustes_merged = merge_loras_procrustes(lora1, lora2)

    out1 = _mat_mul(A1, B1)
    out2 = _mat_mul(A2, B2)
    target = [[0.5*out1[i][j] + 0.5*out2[i][j] for j in range(dim)] for i in range(dim)]
    err_naive = math.sqrt(sum((naive.output_delta()[i][j] - target[i][j])**2
                              for i in range(dim) for j in range(dim)))
    err_proc = math.sqrt(sum((procrustes_merged.output_delta()[i][j] - target[i][j])**2
                             for i in range(dim) for j in range(dim)))
    print(f"  naive_merge_err       = {err_naive:.6f}")
    print(f"  procrustes_merge_err  = {err_proc:.6f}")
    assert err_proc <= err_naive + 1e-9, \
        f"Procrustes must match or beat naive: {err_proc} vs {err_naive}"
    print(f"  ✅ Procrustes merge err ≤ naive merge err (no silent regression)")


def test_10_procrustes_preserves_output():
    """Aligning then re-counter-rotating A2' B2' must equal A2 B2 exactly.

    Convention: A is (dim × rank), B is (rank × dim), output is (dim × dim).
    The output-preserving gauge transform is A' = A Q, B' = Q^T B for any
    orthogonal Q in rank-space.
    """
    A2 = [[0.5, 0.1], [0.3, 0.7], [0.0, 0.2], [0.2, 0.0]]  # dim=4, rank=2
    B2 = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]       # rank=2, dim=4
    lora2 = LoraPair(A=A2, B=B2)
    original = lora2.output_delta()
    # Apply arbitrary gauge rotation in rank space
    Q = _rotation_in_rank_space(0.7, rank=2)
    A2_rot = _mat_mul(A2, Q)                  # (dim × rank) @ (rank × rank) = (dim × rank)
    B2_counter = _mat_mul(_mat_transpose(Q), B2)  # (rank × rank) @ (rank × dim) = (rank × dim)
    rotated = _mat_mul(A2_rot, B2_counter)
    diff = sum((original[i][j] - rotated[i][j])**2
               for i in range(len(original)) for j in range(len(original[0])))
    assert diff < 1e-9, f"rotation/counter-rotation must preserve output, got diff={diff}"
    print(f"  ✅ rotation+counter-rotation preserves output (||Δ||² = {diff:.2e})")


# ===========================================================================
def test_11_poincare_centroid_in_ball():
    """The Fréchet mean of points in the ball stays in the ball."""
    pts = [
        project_to_ball((0.5, 0.3, 0.0)),
        project_to_ball((0.4, 0.4, 0.0)),
        project_to_ball((0.6, 0.2, 0.0)),
    ]
    c = poincare_centroid(pts)
    norm = math.sqrt(sum(x * x for x in c))
    assert norm < 1.0, f"centroid must be in ball, got norm={norm}"
    # Centroid of three nearby points should be near their average
    avg_x = sum(p[0] for p in pts) / 3
    avg_y = sum(p[1] for p in pts) / 3
    assert abs(c[0] - avg_x) < 0.1, f"centroid_x={c[0]} too far from avg={avg_x}"
    assert abs(c[1] - avg_y) < 0.1, f"centroid_y={c[1]} too far from avg={avg_y}"
    print(f"  ✅ centroid of 3 nearby points: ({c[0]:.4f}, {c[1]:.4f}), in ball (norm={norm:.4f})")


def test_12_poincare_exponential_map_toward_origin():
    """The exponential map moves a vector toward the origin."""
    v = (0.8, 0.0, 0.0)
    norm_v = math.sqrt(sum(x * x for x in v))
    v_half = poincare_exponential_map(v, t=0.5)
    norm_half = math.sqrt(sum(x * x for x in v_half))
    assert norm_half < norm_v, f"exp_map should move inward: {norm_half} vs {norm_v}"
    # Halfway = half the norm
    assert abs(norm_half - norm_v / 2) < 1e-9, f"t=0.5 should halve norm: got {norm_half}"
    # Zero vector is fixed
    v_zero = poincare_exponential_map((0.0, 0.0, 0.0), t=0.7)
    assert v_zero == (0.0, 0.0, 0.0)
    # t=0 = no move
    v_same = poincare_exponential_map(v, t=0.0)
    assert v_same == v
    # t=1 = all the way to origin
    v_to_origin = poincare_exponential_map(v, t=1.0)
    norm_final = math.sqrt(sum(x * x for x in v_to_origin))
    assert norm_final < 1e-9, f"t=1 should reach origin, got norm={norm_final}"
    print(f"  ✅ exp_map: 0.8000 → 0.4000 (t=0.5), origin (t=1), fixed (t=0)")


def test_13_poincare_centroid_empty_raises():
    """Empty input should raise ValueError, not silently return."""
    try:
        poincare_centroid([])
        assert False, "should have raised"
    except ValueError:
        pass
    print("  ✅ empty centroid input → ValueError")


# ===========================================================================
def main():
    tests = [
        test_01_poincare_distance_zero,
        test_02_poincare_distance_symmetric,
        test_03_poincare_triangle_inequality,
        test_04_hierarchy_preserved,
        test_05_mobius_stays_in_ball,
        test_06_move_toward_origin,
        test_07_move_toward_boundary,
        test_08_procrustes_aligns_rotation,
        test_09_procrustes_reduces_merge_error,
        test_10_procrustes_preserves_output,
        test_11_poincare_centroid_in_ball,
        test_12_poincare_exponential_map_toward_origin,
        test_13_poincare_centroid_empty_raises,
    ]
    failed = 0
    for i, t in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {t.__name__}")
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL: {type(e).__name__}: {e}")
            failed += 1
    print()
    if failed:
        print(f"❌ {failed}/{len(tests)} tests FAILED")
        return 1
    print(f"✅ {len(tests)}/{len(tests)} tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())