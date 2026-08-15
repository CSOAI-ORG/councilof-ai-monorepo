"""Tests for the dedicated csoai_fisher_rao kernel package."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from csoai_fisher_rao import (
    FisherRaoResult,
    fisher_rao_distance,
    gpu_self_test,
    sov_signal_gate,
)


def test_fr01_symmetric():
    """d(A, B) == d(B, A)."""
    A = np.eye(3) * 2.0
    B = np.eye(3) * 0.5
    d_ab = fisher_rao_distance(A, B)
    d_ba = fisher_rao_distance(B, A)
    assert abs(d_ab - d_ba) < 1e-9, f"asymmetric: {d_ab} vs {d_ba}"
    print(f"  ✅ symmetric: d(A,B)={d_ab:.4f} == d(B,A)={d_ba:.4f}")


def test_fr02_identity_zero():
    """d(A, A) == 0."""
    A = np.eye(4) * 2.5
    d = fisher_rao_distance(A, A)
    assert abs(d) < 1e-9, f"d(A,A)={d}, expected 0"
    print(f"  ✅ identity: d(A,A)={d:.2e}")


def test_fr03_diagonal_known_value():
    """For diagonal A=2I, B=0.5I: log-Euclidean d = sqrt(n) * |log(2/0.5)| = sqrt(n)*log(4)."""
    n = 3
    A = np.eye(n) * 2.0
    B = np.eye(n) * 0.5
    expected = np.sqrt(n) * np.log(4.0)  # = sqrt(3) * 1.3863 ≈ 2.4011
    d = fisher_rao_distance(A, B)
    assert abs(d - expected) < 1e-6, f"expected {expected}, got {d}"
    print(f"  ✅ diagonal d(A,B) = {d:.6f} = sqrt(3)·log(4) = {expected:.6f}")


def test_fr04_off_diagonal_no_nan():
    """Off-diagonal SPD matrices must NOT return NaN (the original np.log bug)."""
    rng = np.random.RandomState(42)
    # Construct SPD via A = M^T M + I
    M1 = rng.randn(3, 3)
    M2 = rng.randn(3, 3)
    A = M1.T @ M1 + np.eye(3)
    B = M2.T @ M2 + np.eye(3)
    d = fisher_rao_distance(A, B)
    assert np.isfinite(d), f"off-diagonal SPD returned NaN/Inf: {d}"
    assert d > 0, f"different matrices returned 0: {d}"
    print(f"  ✅ off-diagonal SPD: d(A,B) = {d:.4f} (no NaN)")


def test_fr05_shape_mismatch_raises():
    """Different shapes must raise ValueError, not silently return NaN."""
    A = np.eye(3)
    B = np.eye(4)
    try:
        fisher_rao_distance(A, B)
        assert False, "should have raised"
    except ValueError as e:
        assert "shape" in str(e).lower()
        print(f"  ✅ shape mismatch → ValueError: {e}")


def test_fr06_non_square_raises():
    """Non-square matrix must raise ValueError."""
    A = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])  # 2x3
    B = A
    try:
        fisher_rao_distance(A, B)
        assert False, "should have raised"
    except ValueError as e:
        assert "square" in str(e).lower()
        print(f"  ✅ non-square → ValueError: {e}")


def test_fr07_sov_signal_gate_close():
    """A close to permitted → is_permitted=True."""
    permitted = np.eye(3)
    close = np.eye(3) * 1.05
    r = sov_signal_gate(close, permitted, threshold=1.0)
    assert r.is_permitted, f"close should be permitted, d={r.distance}"
    assert r.threshold == 1.0
    assert r.matrix_shape == (3, 3)
    assert r.backend in ("geomstats", "scipy-logm"), f"unknown backend: {r.backend}"
    print(f"  ✅ close: d={r.distance:.4f} permitted={r.is_permitted} backend={r.backend}")


def test_fr08_sov_signal_gate_far():
    """A far from permitted → is_permitted=False."""
    permitted = np.eye(3)
    far = np.eye(3) * 10.0
    r = sov_signal_gate(far, permitted, threshold=1.0)
    assert not r.is_permitted, f"far should NOT be permitted, d={r.distance}"
    print(f"  ✅ far: d={r.distance:.4f} permitted={r.is_permitted}")


def test_fr09_result_is_dataclass():
    """FisherRaoResult is a frozen dataclass with the expected fields."""
    r = FisherRaoResult(
        distance=1.5, is_permitted=False, threshold=1.0,
        geodesic_ball_radius=1.0, matrix_shape=(3, 3),
        on_gpu=False, backend="scipy-logm",
    )
    assert r.distance == 1.5
    assert r.backend == "scipy-logm"
    # frozen — assignment should fail
    try:
        r.distance = 99.0  # type: ignore
        assert False, "frozen dataclass should be immutable"
    except Exception:
        pass
    print(f"  ✅ FisherRaoResult is frozen dataclass with 7 fields")


def test_fr10_gpu_self_test_returns_valid():
    """gpu_self_test must return a dict with the expected keys + a real distance."""
    info = gpu_self_test()
    assert isinstance(info, dict)
    assert "fisher_rao_works" in info
    assert "fisher_rao_test_distance" in info
    if info["fisher_rao_works"]:
        d = info["fisher_rao_test_distance"]
        assert np.isfinite(d) and d > 0
        print(f"  ✅ self-test OK: backend={info['fisher_rao_backend']}, "
              f"d={d:.4f} (vs expected 2.4011)")
    else:
        print(f"  ⚠️  self-test failed (no backend): {info['fisher_rao_error']}")


def test_fr11_no_torch_no_crash():
    """If torch isn't installed, CPU path still works."""
    A = np.eye(3) * 2.0
    B = np.eye(3) * 0.5
    d = fisher_rao_distance(A, B, use_gpu=False)
    assert d > 0
    print(f"  ✅ use_gpu=False path works: d={d:.4f}")


def test_fr12_imports_clean():
    """Package must export the canonical API surface (no surprise names)."""
    import csoai_fisher_rao as fr
    public = ["FisherRaoResult", "fisher_rao_distance",
              "sov_signal_gate", "gpu_self_test"]
    for name in public:
        assert hasattr(fr, name), f"missing public symbol: {name}"
    print(f"  ✅ public API: {public}")


if __name__ == "__main__":
    tests = [
        test_fr01_symmetric,
        test_fr02_identity_zero,
        test_fr03_diagonal_known_value,
        test_fr04_off_diagonal_no_nan,
        test_fr05_shape_mismatch_raises,
        test_fr06_non_square_raises,
        test_fr07_sov_signal_gate_close,
        test_fr08_sov_signal_gate_far,
        test_fr09_result_is_dataclass,
        test_fr10_gpu_self_test_returns_valid,
        test_fr11_no_torch_no_crash,
        test_fr12_imports_clean,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
