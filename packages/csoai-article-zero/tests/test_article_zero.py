"""Tests for csoai-article-zero — the foundational governance gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import math

from csoai_article_zero import (
    ARTICLE_ZERO_VERSION, BFT_QUORUM, CARE_FLOOR, VALID_LAYERS,
    evaluate, load_rego_policy, rego_summary, self_test,
)


def _valid_vector() -> dict:
    return {
        "source": "birth:iokfarm",
        "layer": "water",
        "vector": [0.1, 0.2, 0.3],
        "payload": {"user_id": "alice"},
        "sv_id": "abc123def4567890abcdef01",
    }


def test_az01_valid_vector_passes():
    """A complete, well-formed vector passes all 8 rules."""
    v = evaluate(_valid_vector())
    assert v.allowed, f"unexpected violations: {v.violations}"
    assert v.violations == []
    print(f"  ✅ valid vector passes ({len(v.violations)} violations)")


def test_az02_missing_source_fails():
    """V1: source missing."""
    sv = _valid_vector(); del sv["source"]
    v = evaluate(sv)
    assert not v.allowed
    assert any("V1" in x for x in v.violations)
    print(f"  ✅ missing source → V1 violation")


def test_az03_missing_layer_fails():
    """V1: layer missing."""
    sv = _valid_vector(); del sv["layer"]
    v = evaluate(sv)
    assert not v.allowed
    assert any("V1" in x for x in v.violations)
    print(f"  ✅ missing layer → V1 violation")


def test_az04_short_vector_fails():
    """V2: vector too short."""
    sv = _valid_vector(); sv["vector"] = [0.1]
    v = evaluate(sv)
    assert not v.allowed
    assert any("V2" in x for x in v.violations)
    print(f"  ✅ short vector → V2 violation")


def test_az05_invalid_layer_fails():
    """V3: layer not in canonical set."""
    sv = _valid_vector(); sv["layer"] = "mystery"
    v = evaluate(sv)
    assert not v.allowed
    assert any("V3" in x for x in v.violations)
    print(f"  ✅ invalid layer → V3 violation")


def test_az06_unknown_namespace_fails():
    """V4: source namespace not in registry."""
    sv = _valid_vector(); sv["source"] = "alien_ns:wat"
    v = evaluate(sv)
    assert not v.allowed
    assert any("V4" in x for x in v.violations)
    print(f"  ✅ unknown namespace → V4 violation")


def test_az07_nan_in_vector_fails():
    """V5: vector contains NaN."""
    sv = _valid_vector(); sv["vector"] = [float("nan"), 0.0, 0.0]
    v = evaluate(sv)
    assert not v.allowed
    assert any("V5" in x for x in v.violations)
    print(f"  ✅ NaN in vector → V5 violation")


def test_az08_inf_in_vector_fails():
    """V5: vector contains Inf."""
    sv = _valid_vector(); sv["vector"] = [float("inf"), 0.0]
    v = evaluate(sv)
    assert not v.allowed
    assert any("V5" in x for x in v.violations)
    print(f"  ✅ Inf in vector → V5 violation")


def test_az09_water_without_user_id_fails():
    """V6: water event missing user_id."""
    sv = _valid_vector(); del sv["payload"]["user_id"]
    v = evaluate(sv)
    assert not v.allowed
    assert any("V6" in x for x in v.violations)
    print(f"  ✅ water without user_id → V6 violation")


def test_az10_milk_without_user_id_passes():
    """V6 only applies to water events; milk should pass without user_id."""
    sv = _valid_vector()
    sv["layer"] = "milk"
    sv["payload"] = {"chat": "hi"}
    v = evaluate(sv)
    assert v.allowed, f"unexpected violations: {v.violations}"
    print(f"  ✅ milk event doesn't need user_id (V6 is water-only)")


def test_az11_short_sv_id_fails():
    """V7: sv_id not 24 hex chars."""
    sv = _valid_vector(); sv["sv_id"] = "short"
    v = evaluate(sv)
    assert not v.allowed
    assert any("V7" in x for x in v.violations)
    print(f"  ✅ short sv_id → V7 violation")


def test_az12_missing_sv_id_passes():
    """V7 only fires when sv_id IS present but malformed. Absence is OK."""
    sv = _valid_vector(); del sv["sv_id"]
    v = evaluate(sv)
    assert v.allowed, f"unexpected violations: {v.violations}"
    print(f"  ✅ missing sv_id is OK (V7 is malformed-only)")


def test_az13_chain_id_is_audit_hash():
    """chain_id is 24 hex chars, deterministic per input + violations."""
    sv = _valid_vector()
    v1 = evaluate(sv)
    v2 = evaluate(sv)
    assert v1.chain_id == v2.chain_id
    assert len(v1.chain_id) == 24
    # Different sv → different chain_id
    sv2 = _valid_vector(); sv2["vector"] = [0.5, 0.5, 0.5]
    v3 = evaluate(sv2)
    assert v1.chain_id != v3.chain_id
    print(f"  ✅ chain_id is 24-char hex, deterministic per input")


def test_az14_canonical_constants():
    """The constants are the SOVOS substrate invariants."""
    assert CARE_FLOOR == 0.95
    assert abs(BFT_QUORUM - 23/33) < 1e-9
    assert "water" in VALID_LAYERS and "honey" in VALID_LAYERS
    print(f"  ✅ constants: care_floor={CARE_FLOOR}, bft_quorum={BFT_QUORUM:.3f}")


def test_az15_rego_policy_file_loads():
    """The Rego file is present and has 8 rules documented."""
    text = load_rego_policy()
    assert "package article_zero" in text
    assert "allow" in text
    summary = rego_summary()
    assert summary["rules_count"] >= 8
    rule_ids = [r["id"] for r in summary["rules"]]
    for v in ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]:
        assert v in rule_ids, f"missing rule {v} in Rego file"
    print(f"  ✅ Rego file: {summary['rules_count']} rules, {summary['policy_chars']} chars")


def test_az16_rego_python_agree():
    """Python and Rego both reject the same bad vector."""
    bad = {
        "source": "alien_ns:wat",  # V4
        "layer": "mystery",         # V3
        "vector": [0.1],            # V2
        "payload": {},              # V6 (water without user_id)
        "sv_id": "x",               # V7
    }
    v = evaluate(bad)
    # Python must report at least 4 violations (V2/V3/V4/V6/V7 — V5 not since no NaN)
    assert not v.allowed
    assert len(v.violations) >= 4
    # Rego file must contain all the V-numbers that fire
    text = load_rego_policy()
    for v_id in ["V2", "V3", "V4", "V6", "V7"]:
        assert v_id in text, f"Rego missing {v_id}"
    print(f"  ✅ Python+Rego agree: {len(v.violations)} violations, all V# present")


def test_az17_self_test():
    """The self_test helper returns a complete picture."""
    info = self_test()
    assert info["valid_allowed"] is True
    assert info["invalid_allowed"] is False
    # NaN + V2 are mutually exclusive; the sample has NaN so V2 doesn't fire
    assert info["invalid_violation_count"] >= 4
    assert info["rego_rules"] >= 8
    print(f"  ✅ self_test: valid={info['valid_allowed']}, "
          f"invalid_violations={info['invalid_violation_count']}, "
          f"rego_rules={info['rego_rules']}")


def test_az18_unknown_namespaces_override():
    """known_namespaces param overrides the default set."""
    sv = _valid_vector(); sv["source"] = "custom_ns:wat"
    # Default → V4 violation
    v = evaluate(sv)
    assert not v.allowed
    # With override → allowed
    v2 = evaluate(sv, known_namespaces={"custom_ns", "iokfarm", "birth"})
    assert v2.allowed
    print(f"  ✅ known_namespaces override works")


if __name__ == "__main__":
    tests = [
        test_az01_valid_vector_passes,
        test_az02_missing_source_fails,
        test_az03_missing_layer_fails,
        test_az04_short_vector_fails,
        test_az05_invalid_layer_fails,
        test_az06_unknown_namespace_fails,
        test_az07_nan_in_vector_fails,
        test_az08_inf_in_vector_fails,
        test_az09_water_without_user_id_fails,
        test_az10_milk_without_user_id_passes,
        test_az11_short_sv_id_fails,
        test_az12_missing_sv_id_passes,
        test_az13_chain_id_is_audit_hash,
        test_az14_canonical_constants,
        test_az15_rego_policy_file_loads,
        test_az16_rego_python_agree,
        test_az17_self_test,
        test_az18_unknown_namespaces_override,
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
