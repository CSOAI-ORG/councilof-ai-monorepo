"""Tests for csoai-signal-index — the SOV SIGNAL index instruments."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from csoai_signal_index import (
    ConstituentScore, SovSignalVerdict,
    precision_weight, systemic_correlation_index, aggregate_sov_signal,
    trusted_from_chain_result, self_test,
)


def _safe_portfolio():
    """A genuinely SPREAD portfolio across the trust range (multiculture)."""
    return [
        ConstituentScore("a", 0.05, 0.4, 0.5, 6.25, True, "c1"),
        ConstituentScore("b", 0.30, 0.5, 0.5, 4.0, True, "c2"),
        ConstituentScore("c", 0.90, 0.6, 0.5, 2.78, False, "c3"),
        ConstituentScore("d", 2.50, 0.55, 0.5, 3.31, False, "c4"),
    ]


def _tight_trusted():
    """A narrow, all-trusted portfolio (high aggregate score)."""
    return [
        ConstituentScore("a", 0.05, 0.4, 0.5, 6.25, True, "c1"),
        ConstituentScore("b", 0.10, 0.45, 0.5, 4.94, True, "c2"),
        ConstituentScore("c", 0.15, 0.5, 0.5, 4.0, True, "c3"),
    ]


def test_si01_precision_is_inverse_sigma_squared():
    """Π = 1/σ² (Glicko law: high σ self-down-weights)."""
    assert abs(precision_weight(0.5) - 4.0) < 1e-9
    assert abs(precision_weight(2.0) - 0.25) < 1e-9
    assert abs(precision_weight(0.5) - precision_weight(0.5)) < 1e-12
    print(f"  ✅ precision_weight: σ=0.5→4.0, σ=2.0→0.25 (high σ down-weighted)")


def test_si02_systemic_correlation_safe_pf_low():
    """A varied portfolio → low systemic correlation (multiculture)."""
    c_idx = systemic_correlation_index(_safe_portfolio())
    assert 0.0 <= c_idx <= 1.0
    assert c_idx < 0.5, f"safe portfolio should be <0.5, got {c_idx:.3f}"
    print(f"  ✅ safe portfolio systemic={c_idx:.3f} < 0.5 (multiculture)")


def test_si03_systemic_correlation_monoculture_high():
    """Identical distances → high systemic correlation (monoculture)."""
    mono = [ConstituentScore(f"m{i}", 0.3, 0.5, 0.5, 4.0, True) for i in range(5)]
    c_idx = systemic_correlation_index(mono)
    assert c_idx > 0.5, f"monoculture should be >0.5, got {c_idx:.3f}"
    print(f"  ✅ monoculture systemic={c_idx:.3f} > 0.5")


def test_si04_systemic_correlation_single():
    """A single constituent → no systemic signal (0.0)."""
    single = [ConstituentScore("a", 0.1, 0.5, 0.5, 4.0, True)]
    c_idx = systemic_correlation_index(single)
    assert c_idx == 0.0
    print(f"  ✅ single constituent → systemic=0.0")


def test_si05_aggregate_good_services():
    """A tight all-trusted portfolio → high aggregate score (>0.8)."""
    v = aggregate_sov_signal(_tight_trusted())
    assert v.n_constituents == 3
    assert v.aggregate_score > 0.8, f"trusted portfolio agg={v.aggregate_score:.3f}"
    assert v.mean_distance < 0.6
    print(f"  ✅ tight-trusted portfolio: agg={v.aggregate_score:.3f} (trusted, >0.8)")


def test_si06_aggregate_far_portfolio_low():
    """Constituents far from permitted → low aggregate score."""
    far = [ConstituentScore("a", 3.0, 0.5, 1.0, 4.0, False) for _ in range(3)]
    v = aggregate_sov_signal(far)
    assert v.aggregate_score < 0.3, f"far portfolio agg={v.aggregate_score:.3f}"
    print(f"  ✅ far portfolio: agg={v.aggregate_score:.3f} (untrusted)")


def test_si07_aggregate_empty():
    """Empty portfolio → both conventional scores 0 + no chain_id."""
    v = aggregate_sov_signal([])
    assert v.n_constituents == 0
    assert v.aggregate_score == 0.0
    assert v.systemic_correlation == 0.0
    assert v.chain_id == ""
    print(f"  ✅ empty portfolio: agg=0, systemic=0")


def test_si08_chain_result_direct():
    """trusted_from_chain_result reads a sovos-chain-like object + meta sigma."""
    class CR:
        distance = 0.0845
        threshold = 1.0
        chain_id = "aabbccddeeff001122334455"
        inputs_sha = "inputs1234"
        meta = {"sigma": 0.5}
    s = trusted_from_chain_result(CR())
    assert abs(s.distance - 0.0845) < 1e-9
    assert abs(s.sigma - 0.5) < 1e-9
    assert abs(s.precision - 4.0) < 1e-9
    assert s.is_trusted is True
    assert s.chain_id == "aabbccddeeff001122334455"
    print(f"  ✅ CR → constituent: d={s.distance}, σ={s.sigma}, precision={s.precision}")


def test_si09_chain_result_missing_sigma_defaults_one():
    """Missing σ defaults to 1.0 (neutral uncertainty)."""
    class CR:
        fisher_rao_distance = 0.2
        threshold = 1.0
        chain_id = "x"
    s = trusted_from_chain_result(CR())
    assert s.sigma == 1.0
    assert s.precision == 1.0
    print(f"  ✅ missing σ → 1.0 (precision=1.0)")


def test_si10_chain_id_deterministic():
    """aggregate chain_id is 24 hex, deterministic per identical input."""
    v1 = aggregate_sov_signal(_safe_portfolio())
    v2 = aggregate_sov_signal(_safe_portfolio())
    assert v1.chain_id == v2.chain_id
    assert len(v1.chain_id) == 24
    print(f"  ✅ aggregate chain_id is 24-char hex, deterministic")


def test_si11_multiculture_flag():
    """multiculture_ccy = (systemic < 0.5)."""
    safe = aggregate_sov_signal(_safe_portfolio())
    mono = aggregate_sov_signal([ConstituentScore(f"m{i}", .3, .5, .5, 4., True) for i in range(5)])
    assert safe.multiculture_ccy is True
    assert mono.multiculture_ccy is False
    print(f"  ✅ multiculture flag: safe=True (% safe), mono=False")


def test_si12_verdict_composition():
    """The verdict is JSON-serializable (for the index feed)."""
    import json
    v = aggregate_sov_signal(_safe_portfolio())
    d = v.to_dict()
    blob = json.dumps(d)
    assert "aggregate_score" in blob
    assert "systemic_correlation" in blob
    assert "constituents" in blob
    print(f"  ✅ verdict JSON-serializable ({len(blob)} bytes)")


def test_si13_self_test():
    """self_test returns a complete picture.

    NB: the self_test 'safe' fixture is a SPREAD portfolio meant to show
    multiculture (low systemic), NOT high aggregate — its aggregate is
    moderate. The high-aggregate case is tested separately in _tight_trusted.
    """
    result = self_test()
    assert result["safe_multiculture"] is True     # spread → multiculture
    assert result["mono_multiculture"] is False     # identical → monoculture
    assert result["safe_syscorr"] < 0.5
    assert result["mono_syscorr"] > 0.5
    assert result["chain_id_len"] == 24
    print(f"  ✅ self_test: safe_syscorr={result['safe_syscorr']}, "
          f"mono_syscorr={result['mono_syscorr']} (spread vs monoculture)")


def test_si14_manifold_calibration():
    """calibrate_permitted_manifold builds a mean + SPD covariance dict."""
    import numpy as np
    from csoai_signal_index import calibrate_permitted_manifold
    profiles = [
        [0.95, 0.92, 0.90, 0.93],
        [0.90, 0.95, 0.88, 0.91],
        [0.93, 0.89, 0.94, 0.90],
        [0.91, 0.93, 0.92, 0.95],
    ]
    M = calibrate_permitted_manifold(profiles)
    assert "mean" in M and "cov" in M
    assert len(M["mean"]) == 4
    cov = np.asarray(M["cov"])
    assert cov.shape == (4, 4)
    assert np.allclose(cov, cov.T)
    evals = np.linalg.eigvalsh(cov)
    assert evals.min() > 0
    print(f"  ✅ manifold calibrated: mean len 4, SPD cov, min-eig={evals.min():.4f}")


def test_si15_distance_discriminates():
    """distance_to_permitted_manifold separates known-good from known-bad."""
    from csoai_signal_index import calibrate_permitted_manifold, distance_to_permitted_manifold
    ref = [
        [0.95, 0.92, 0.90, 0.93],
        [0.90, 0.95, 0.88, 0.91],
        [0.93, 0.89, 0.94, 0.90],
        [0.91, 0.93, 0.92, 0.95],
    ]
    M = calibrate_permitted_manifold(ref)
    near = [0.92, 0.93, 0.91, 0.92]   # inside the cluster
    far = [0.1, 0.1, 0.1, 0.1]         # way outside
    d_near = distance_to_permitted_manifold(near, M)
    d_far = distance_to_permitted_manifold(far, M)
    assert d_far > d_near
    print(f"  ✅ distance discriminates: near={d_near:.3f} < far={d_far:.3f}")


def test_si16_manifold_needs_profiles():
    """Fewer than 2 reference profiles raises ValueError."""
    from csoai_signal_index import calibrate_permitted_manifold
    try:
        calibrate_permitted_manifold([[0.9, 0.9]])
        assert False, "should raise"
    except ValueError:
        pass
    print(f"  ✅ <2 profiles → ValueError")


if __name__ == "__main__":
    tests = [
        test_si01_precision_is_inverse_sigma_squared,
        test_si02_systemic_correlation_safe_pf_low,
        test_si03_systemic_correlation_monoculture_high,
        test_si04_systemic_correlation_single,
        test_si05_aggregate_good_services,
        test_si06_aggregate_far_portfolio_low,
        test_si07_aggregate_empty,
        test_si08_chain_result_direct,
        test_si09_chain_result_missing_sigma_defaults_one,
        test_si10_chain_id_deterministic,
        test_si11_multiculture_flag,
        test_si12_verdict_composition,
        test_si13_self_test,
        test_si14_manifold_calibration,
        test_si15_distance_discriminates,
        test_si16_manifold_needs_profiles,
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
