"""Tests for csoai-invariants — the sovereign substrate primitives."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_invariants import (
    normalize_name, normalize_owem, validate_care_floor,
    care_score, validate_tally, SOVEREIGN_DID, CARE_FLOOR,
)


def test_i01_normalize_name():
    """normalize_name: strip + lowercase (whitespace preserved as-is)."""
    assert normalize_name("Hello   World  ") == "hello   world"
    assert normalize_name("FOO Bar") == "foo bar"
    assert normalize_name("") == ""
    print("  PASS i01 normalize_name (strip + lower, preserves ws)")


def test_i02_care_floor_enforced():
    """CARE floor >= CARE_FLOOR (0.95 by default). Below raises."""
    assert validate_care_floor(0.95) == 0.95
    assert validate_care_floor(1.0) == 1.0
    try:
        validate_care_floor(0.7)
        assert False, "should have raised"
    except ValueError:
        pass
    print(f"  PASS i02 validate_care_floor (>= {CARE_FLOOR})")


def test_i03_care_score_nonneg():
    """care_score is bounded [0, 1]."""
    for text in ["abc def ghi", "good helpful kind", "", "x" * 1000]:
        s = care_score(text)
        assert 0.0 <= s <= 1.0, f"care_score({text!r})={s} out of [0,1]"
    print("  PASS i03 care_score returns [0,1]")


def test_i04_normalize_owem():
    """OWEM names validated against OWEM_GROUPS whitelist."""
    assert normalize_owem("compliance") == "compliance"
    assert normalize_owem("defense") == "defense"
    print("  PASS i04 normalize_owem")


def test_i05_validate_tally():
    """BFT tally: approve/amend/reject totalling BFT_COUNCIL_SIZE."""
    valid_tally = {"approve": 30, "amend": 2, "reject": 1}
    assert validate_tally(valid_tally) == valid_tally
    # missing a field → raises
    try:
        validate_tally({"approve": 1, "reject": 0})
        assert False, "should have raised"
    except ValueError:
        pass
    print("  PASS i05 validate_tally")


def test_i06_sovereign_did_format():
    """SOVEREIGN_DID is set and well-formed (did:csoai:…)."""
    assert isinstance(SOVEREIGN_DID, str)
    assert SOVEREIGN_DID.startswith("did:"), SOVEREIGN_DID
    print(f"  PASS i06 SOVEREIGN_DID={SOVEREIGN_DID}")


def main():
    tests = [
        test_i01_normalize_name,
        test_i02_care_floor_enforced,
        test_i03_care_score_nonneg,
        test_i04_normalize_owem,
        test_i05_validate_tally,
        test_i06_sovereign_did_format,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{'OK' if passed == len(tests) else 'PARTIAL'} "
          f"{passed}/{len(tests)} PASSED")


if __name__ == "__main__":
    main()
