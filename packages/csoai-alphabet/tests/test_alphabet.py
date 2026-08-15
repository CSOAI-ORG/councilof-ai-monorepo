"""Tests for csoai-alphabet v0.1.0 SCAFFOLD.

12 tests covering:
- All 26 checks exist (A-Z)
- Empty record → mostly UNKNOWN
- Well-documented record → mostly PASS
- Each check returns valid AuditResult
- drum_spine() cycles through the alphabet correctly
- summary() counts PASS/FAIL/UNKNOWN
- X is always UNKNOWN (intrinsic)
- FAIL surfaces when explicit failure indicator present
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_alphabet import (
    Status, AuditResult, CHECKS, audit, drum_spine, summary,
)


def test_01_all_26_letters_exist():
    """Exactly 26 checks (A-Z)."""
    assert len(CHECKS) == 26
    letters = [c.__name__.split("_")[1] for c in CHECKS]
    assert letters == list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    print(f"  ✅ {len(CHECKS)} checks: {' '.join(letters)}")


def test_02_empty_record_yields_mostly_unknown():
    """An empty record should produce mostly UNKNOWN — NOT silent PASSes."""
    results = audit({})
    s = summary(results)
    assert s["UNKNOWN"] >= 20, f"empty record should have many UNKNOWNs; got {s}"
    assert s["PASS"] == 0, f"empty record should have ZERO PASSes; got {s}"
    # X is always UNKNOWN
    x_result = [r for r in results if r.letter == "X"][0]
    assert x_result.status == Status.UNKNOWN
    print(f"  ✅ empty record → {s}")


def test_03_well_documented_record_yields_mostly_pass():
    """A record with all keys set should produce mostly PASS."""
    well_doc = {
        "architecture": True, "behavior_spec": True, "coherence": True,
        "data_source": True, "explicit_goals": True, "fail_safe": True,
        "governance": True, "human_review": True, "interpretability": True,
        "jurisdiction": True, "key_management": True, "logging": True,
        "model_card": True, "seed_control": True, "outcome_metrics": True,
        "provenance": True, "post_quantum": True, "red_team": True,
        "supply_chain": True, "tests": True, "unknown_handling": True,
        "git": True, "watchdog": True, "yield_rate": 0.95,
        "null_test": True,
    }
    results = audit(well_doc)
    s = summary(results)
    # Most checks should PASS (X is always UNKNOWN, Y depends on yield)
    assert s["PASS"] >= 20, f"well-documented should have many PASSes; got {s}"
    assert s["FAIL"] == 0
    print(f"  ✅ well-documented record → {s}")


def test_04_drum_spine_cycles():
    """drum_spine(tick=0) → A, tick=25 → Z, tick=26 → A again."""
    r0 = drum_spine({}, tick=0)
    r25 = drum_spine({}, tick=25)
    r26 = drum_spine({}, tick=26)
    assert r0.letter == "A"
    assert r25.letter == "Z"
    assert r26.letter == "A", f"tick=26 should wrap to A; got {r26.letter}"
    print(f"  ✅ drum_spine cycles: tick 0→{r0.letter}, 25→{r25.letter}, 26→{r26.letter} (wraps)")


def test_05_x_factor_always_unknown():
    """X must always be UNKNOWN (intrinsically unmeasurable from a record)."""
    for record_variant in [{}, {"x_factor": True}, {"x_factor": "covered"}, {"x_factor": False}]:
        results = audit(record_variant)
        x = [r for r in results if r.letter == "X"][0]
        assert x.status == Status.UNKNOWN, f"X must be UNKNOWN even with {record_variant}; got {x.status}"
    print("  ✅ X-factor is always UNKNOWN (intrinsic)")


def test_06_fail_explicit_for_drift():
    """A record with drift_detected=True should FAIL the Coherence check (C)."""
    record = {"drift_detected": True, "coherence": True}
    results = audit(record)
    c = [r for r in results if r.letter == "C"][0]
    assert c.status == Status.FAIL, f"drift_detected should FAIL C; got {c.status}"
    assert "drift" in c.evidence.lower()
    print(f"  ✅ C: drift_detected=True → FAIL (evidence: '{c.evidence}')")


def test_07_fail_low_yield():
    """A record with yield_rate < 0.5 should FAIL the Yield check (Y)."""
    record = {"yield_rate": 0.3}
    results = audit(record)
    y = [r for r in results if r.letter == "Y"][0]
    assert y.status == Status.FAIL
    print(f"  ✅ Y: yield_rate=0.3 → FAIL (got {y.status})")


def test_08_pass_high_yield():
    """A record with yield_rate >= 0.9 should PASS the Yield check."""
    record = {"yield_rate": 0.95}
    results = audit(record)
    y = [r for r in results if r.letter == "Y"][0]
    assert y.status == Status.PASS
    print(f"  ✅ Y: yield_rate=0.95 → PASS")


def test_09_summary_counts_correct():
    """summary() should return {PASS, FAIL, UNKNOWN} counts."""
    record = {"drift_detected": True, "yield_rate": 0.95, "coherence": True}
    results = audit(record)
    s = summary(results)
    assert "PASS" in s
    assert "FAIL" in s
    assert "UNKNOWN" in s
    assert s["PASS"] + s["FAIL"] + s["UNKNOWN"] == 26
    print(f"  ✅ summary: PASS={s['PASS']}, FAIL={s['FAIL']}, UNKNOWN={s['UNKNOWN']} (total=26)")


def test_10_to_dict_serializable():
    """Every AuditResult should serialize to JSON without errors."""
    import json
    results = audit({"coherence": True, "tests": True})
    serialized = json.dumps([r.to_dict() for r in results])
    assert len(serialized) > 100
    print(f"  ✅ all 26 results serialize ({len(serialized)} bytes)")


def test_11_invalid_tick_raises():
    """Negative tick should raise."""
    try:
        drum_spine({}, tick=-1)
        assert False, "should have raised"
    except ValueError:
        pass
    print("  ✅ negative tick → ValueError")


def test_12_check_letter_names_unique():
    """Each check should have a unique letter (A-Z) and unique name."""
    letters = [c.__name__.split("_")[1] for c in CHECKS]
    assert len(set(letters)) == 26, "letters should be unique"
    results = audit({})
    names = [r.name for r in results]
    assert len(set(names)) == 26, f"names should be unique; got {names}"
    print(f"  ✅ 26 unique letters + 26 unique names")


def main():
    tests = [
        test_01_all_26_letters_exist,
        test_02_empty_record_yields_mostly_unknown,
        test_03_well_documented_record_yields_mostly_pass,
        test_04_drum_spine_cycles,
        test_05_x_factor_always_unknown,
        test_06_fail_explicit_for_drift,
        test_07_fail_low_yield,
        test_08_pass_high_yield,
        test_09_summary_counts_correct,
        test_10_to_dict_serializable,
        test_11_invalid_tick_raises,
        test_12_check_letter_names_unique,
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
