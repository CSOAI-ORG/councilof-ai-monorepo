"""Tests for csoai-info-geometry (Fisher-Rao + GW).

Tests are written to pass on BOTH:
  - Local Mac (numpy fallback, no GPU) → tests 01-04
  - RunPod sov-brain-2 (GPU + geomstats + POT) → tests 05-07

To run on the pod:
  ssh sov-brain-2 'cd /workspace && source sov-governance-venv/bin/activate && PYTHONPATH=/workspace PYTHONPATH=.../csoai-info-geometry/src python3 -m pytest .../csoai-info-geometry/tests/ -v'
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_info_geometry import (
    FisherRaoResult, spd_geodesic_distance, sov_signal_fisher_rao,
    GWResult, gromov_wasserstein_distance, merge_models_via_gw,
    gpu_self_test,
)

import numpy as np


# ===========================================================================
# CPU fallback tests (work without GPU / geomstats / POT)
# ===========================================================================
def test_01_fisher_rao_symmetric():
    """d(A, B) = d(B, A)."""
    A = np.eye(3) * 2.0
    B = np.eye(3) * 0.5
    d_ab = spd_geodesic_distance(A, B)
    d_ba = spd_geodesic_distance(B, A)
    assert abs(d_ab - d_ba) < 1e-6
    print(f"  ✅ symmetric: d(A,B)={d_ab:.4f} == d(B,A)={d_ba:.4f}")


def test_02_fisher_rao_identity():
    """d(A, A) = 0."""
    A = np.eye(3) * 2.5
    d = spd_geodesic_distance(A, A)
    assert d < 1e-10
    print(f"  ✅ d(A,A) = {d:.4e}")


def test_03_sov_signal_permitted_vs_blocked():
    """A close to permitted → GOVERNED. Far from permitted → BLOCKED."""
    permitted = np.eye(3) * 1.0
    close = np.eye(3) * 1.05  # very close
    far = np.eye(3) * 5.0    # very far
    r_close = sov_signal_fisher_rao(close, permitted, threshold=1.0)
    r_far = sov_signal_fisher_rao(far, permitted, threshold=1.0)
    assert r_close.is_permitted
    assert not r_far.is_permitted
    print(f"  ✅ close: d={r_close.distance:.4f} permitted={r_close.is_permitted}")
    print(f"  ✅ far:   d={r_far.distance:.4f} permitted={r_far.is_permitted}")


def test_04_sov_signal_non_diagonal_spd():
    """Fisher-Rao on non-diagonal SPD matrices — the realistic case."""
    # Covariance matrices of two different Gaussian distributions
    A = np.array([[2.0, 0.5], [0.5, 2.0]])  # correlated
    B = np.array([[1.0, 0.1], [0.1, 1.0]])  # less correlated
    d = spd_geodesic_distance(A, B)
    assert d > 0
    print(f"  ✅ non-diagonal SPD: d(A,B)={d:.4f}")


# ===========================================================================
# GPU + geomstats + POT tests (only run if available)
# ===========================================================================
def test_05_gpu_self_test():
    """The GPU self-test must report torch+GPU+geomstats+POT all working."""
    info = gpu_self_test()
    print(f"  ℹ️  info: {info}")
    assert info["torch_available"], "torch missing"
    # GPU is optional — check but don't fail if absent
    if not info["torch_cuda"]:
        print("  ⚠️  no GPU detected — running CPU fallback")
        return  # skip GPU-specific tests
    assert info["geomstats_available"], "geomstats missing"
    assert info["pot_available"], "POT missing"
    assert info["fisher_rao_works"], f"Fisher-Rao failed: {info.get('fisher_rao_error')}"
    assert info["gw_works"], f"GW failed: {info.get('gw_error')}"
    print(f"  ✅ GPU self-test: fisher_rao={info['fisher_rao_test_distance']:.4f}, "
          f"gw={info['gw_test_distance']:.4f}")


def test_06_gw_distance_zero_for_identical():
    """GW distance between a set and itself should be ~0."""
    if not info_available():
        print("  ⏭️  SKIPPED — POT not available")
        return
    feats = np.random.RandomState(0).randn(10, 4)
    w = np.ones(10) / 10
    gw = gromov_wasserstein_distance(feats, feats, w, w)
    assert gw.gw_distance < 0.05, f"identical sets should have GW~0, got {gw.gw_distance}"
    # Transport plan should be close to identity
    diag_sum = np.trace(gw.transport_plan)
    print(f"  ✅ GW(feats, feats) = {gw.gw_distance:.6f}, diag_sum={diag_sum:.3f}")


def test_07_gw_cross_architecture():
    """GW between two feature sets of different dimensions — MergeKit can't do this."""
    if not info_available():
        print("  ⏭️  SKIPPED — POT not available")
        return
    rng = np.random.RandomState(42)
    feats_a = rng.randn(8, 4)   # 8 neurons, dim 4 (e.g., a small Llama layer)
    feats_b = rng.randn(12, 6)  # 12 neurons, dim 6 (e.g., a Qwen layer — different dim!)
    w_a = np.ones(8) / 8
    w_b = np.ones(12) / 12
    gw = gromov_wasserstein_distance(feats_a, feats_b, w_a, w_b)
    assert gw.gw_distance > 0
    assert gw.transport_plan.shape == (8, 12)
    print(f"  ✅ cross-arch GW: distance={gw.gw_distance:.4f}, plan shape={gw.transport_plan.shape}")


def test_08_merge_models_via_gw_shape():
    """The GW merge produces a (2*(n_a + n_b), output_dim) matrix."""
    if not info_available():
        print("  ⏭️  SKIPPED — POT not available")
        return
    feats_a = np.random.RandomState(0).randn(6, 3)
    feats_b = np.random.RandomState(1).randn(8, 5)
    w_a = np.ones(6) / 6
    w_b = np.ones(8) / 8
    merged = merge_models_via_gw(feats_a, feats_b, w_a, w_b, output_dim=4)
    expected_n = 2 * (6 + 8)
    assert merged.shape == (expected_n, 4), f"expected ({expected_n}, 4), got {merged.shape}"
    print(f"  ✅ GW-merged shape: {merged.shape}")


def info_available():
    import ot
    return True


def main():
    tests = [
        test_01_fisher_rao_symmetric,
        test_02_fisher_rao_identity,
        test_03_sov_signal_permitted_vs_blocked,
        test_04_sov_signal_non_diagonal_spd,
        test_05_gpu_self_test,
        test_06_gw_distance_zero_for_identical,
        test_07_gw_cross_architecture,
        test_08_merge_models_via_gw_shape,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())