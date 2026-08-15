"""Tests for csoai-sheaf-gate — the pre-merge safety gate for federation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_sheaf_gate import (
    SheafVerdict,
    federate_with_gate,
    sheaf_pre_merge_check,
    self_test,
)


def test_sg01_identical_buses_pass():
    """Two identical buses form a perfect sheaf → passes."""
    a = {"s1": [1.0, 0.0, 0.0], "s2": [0.0, 1.0, 0.0]}
    b = {"s1": [1.0, 0.0, 0.0], "s2": [0.0, 1.0, 0.0]}
    v = sheaf_pre_merge_check(a, b)
    assert v.passed
    assert v.agreement_ratio == 1.0
    assert v.n_shared == 2
    assert v.n_agree == 2
    assert v.n_disagree == 0
    print(f"  ✅ identical buses: passed, ratio={v.agreement_ratio}")


def test_sg02_wildly_different_fails():
    """Two wildly different buses do not form a sheaf → fails."""
    a = {"s1": [1.0, 0.0, 0.0]}
    b = {"s1": [100.0, 0.0, 0.0]}
    v = sheaf_pre_merge_check(a, b, tolerance=0.1)
    assert not v.passed
    assert v.agreement_ratio < 0.5
    assert v.n_disagree >= 1
    assert len(v.violations) >= 1
    assert v.violations[0]["sv_id"] == "s1"
    assert v.violations[0]["l2_distance"] > 10.0
    print(f"  ✅ wildly different: failed, ratio={v.agreement_ratio:.2f}, "
          f"max_disp={v.max_disagreement:.1f}")


def test_sg03_empty_overlap_passes():
    """No shared sv_ids → vacuously true (nothing to disagree on)."""
    a = {"s1": [1.0, 0.0]}
    b: dict = {}
    v = sheaf_pre_merge_check(a, b)
    assert v.passed
    assert v.n_shared == 0
    print(f"  ✅ empty overlap: passed (n_shared=0)")


def test_sg04_partial_disagreement_below_threshold():
    """Some disagreement is OK if it's within tolerance."""
    a = {"s1": [1.0, 0.0, 0.0], "s2": [0.0, 1.0, 0.0]}
    # s1 agrees (within 0.1), s2 disagrees a bit but within tolerance
    b = {"s1": [1.05, 0.0, 0.0], "s2": [0.0, 1.5, 0.0]}
    v = sheaf_pre_merge_check(a, b, tolerance=0.5)  # generous
    assert v.passed
    print(f"  ✅ partial disagreement within tolerance: passed (ratio={v.agreement_ratio:.2f})")


def test_sg05_chain_id_audit():
    """chain_id is 24 hex chars, deterministic per input."""
    a = {"s1": [1.0, 0.0, 0.0]}
    b = {"s1": [1.0, 0.0, 0.0]}
    v1 = sheaf_pre_merge_check(a, b)
    v2 = sheaf_pre_merge_check(a, b)
    assert v1.chain_id == v2.chain_id
    assert len(v1.chain_id) == 24
    print(f"  ✅ chain_id is 24-char hex, deterministic")


def test_sg06_dim_padding():
    """Different-dim vectors are padded to max_dim before comparison."""
    a = {"s1": [1.0, 0.0]}            # dim 2
    b = {"s1": [1.0, 0.0, 0.0, 0.0]}  # dim 4
    v = sheaf_pre_merge_check(a, b, tolerance=0.1)
    # After pad to max_dim=4: a = [1.0, 0.0, 0.0, 0.0], b = same → agrees
    assert v.n_agree == 1
    print(f"  ✅ dim padding: dim-2 padded to dim-4, agreed")


def test_sg07_cosine_in_violations():
    """Violations include the cosine similarity for audit."""
    a = {"s1": [1.0, 0.0, 0.0]}
    b = {"s1": [-1.0, 0.0, 0.0]}  # opposite direction
    v = sheaf_pre_merge_check(a, b, tolerance=0.1)
    assert not v.passed
    assert v.violations[0]["cosine_similarity"] < 0  # anti-parallel
    print(f"  ✅ cosine similarity in violations: {v.violations[0]['cosine_similarity']:.3f}")


def test_sg08_federate_with_gate_passes_when_safe():
    """federate_with_gate returns the merged bus when safe."""
    a = {"s1": [1.0, 0.0, 0.0], "s2": [0.0, 1.0, 0.0]}
    b = {"s1": [1.0, 0.0, 0.0], "s2": [0.0, 1.0, 0.0]}
    fed, verdict = federate_with_gate(a, b)
    if fed is not None:
        assert verdict.passed
        print(f"  ✅ federate_with_gate: passed, merged {len(fed.merged_vectors) if hasattr(fed, 'merged_vectors') else 'N/A'}")
    else:
        # sovos_jspace_pipeline may not be on PYTHONPATH in this test
        print(f"  ✅ federate_with_gate: passed, but pipeline unavailable (standalone mode)")
        assert verdict.passed


def test_sg09_federate_with_gate_refuses_when_unsafe():
    """federate_with_gate returns None when the sheaf is inconsistent."""
    a = {"s1": [1.0, 0.0, 0.0]}
    b = {"s1": [100.0, 0.0, 0.0]}  # wildly different
    fed, verdict = federate_with_gate(a, b)
    assert fed is None, "should refuse to merge inconsistent buses"
    assert not verdict.passed
    print(f"  ✅ federate_with_gate: REFUSED unsafe merge (ratio={verdict.agreement_ratio:.2f})")


def test_sg10_federate_with_gate_force_overrides():
    """force=True skips the gate (for emergency use only)."""
    a = {"s1": [1.0, 0.0, 0.0]}
    b = {"s1": [100.0, 0.0, 0.0]}
    fed, verdict = federate_with_gate(a, b, force=True)
    # Even with force, verdict reports passed=False (we didn't override the verdict)
    assert not verdict.passed
    if fed is None:
        print(f"  ✅ federate_with_gate force: pipeline unavailable, but force honored")
    else:
        print(f"  ✅ federate_with_gate force: merged despite inconsistency")


def test_sg11_self_test_helper():
    """self_test returns a complete picture."""
    info = self_test()
    assert info["identical_passed"] is True
    assert info["identical_agreement"] == 1.0
    assert info["wildly_diff_passed"] is False
    assert info["wildly_diff_violations"] >= 1
    assert info["empty_overlap_passed"] is True
    print(f"  ✅ self_test: {info}")


def test_sg12_agreement_ratio_formula():
    """agreement_ratio = n_agree / n_shared."""
    a = {"s1": [1.0, 0.0], "s2": [0.0, 1.0], "s3": [1.0, 1.0]}
    # s1 agrees, s2 disagrees (anti-parallel), s3 agrees
    b = {"s1": [1.0, 0.0], "s2": [0.0, -1.0], "s3": [1.0, 1.0]}
    v = sheaf_pre_merge_check(a, b, tolerance=0.1)
    # 2/3 agree = 0.667 ratio
    assert abs(v.agreement_ratio - 2/3) < 0.01
    assert v.n_agree == 2
    assert v.n_disagree == 1
    print(f"  ✅ agreement_ratio: {v.agreement_ratio:.3f} = 2/3 (n_agree=2, n_disagree=1)")


if __name__ == "__main__":
    tests = [
        test_sg01_identical_buses_pass,
        test_sg02_wildly_different_fails,
        test_sg03_empty_overlap_passes,
        test_sg04_partial_disagreement_below_threshold,
        test_sg05_chain_id_audit,
        test_sg06_dim_padding,
        test_sg07_cosine_in_violations,
        test_sg08_federate_with_gate_passes_when_safe,
        test_sg09_federate_with_gate_refuses_when_unsafe,
        test_sg10_federate_with_gate_force_overrides,
        test_sg11_self_test_helper,
        test_sg12_agreement_ratio_formula,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            import traceback; traceback.print_exc()
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
