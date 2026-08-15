"""sov33-benchmark tests (SCAFFOLD)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sov33_benchmark import (
    AXES, SCAFFOLD_ITEMS, Score, score_response, load_items, run_benchmark,
    GovBenchItem,
)


def test_axes_defined():
    assert len(AXES) == 12
    assert "GOV" in AXES
    assert "ART5" in AXES
    print(f"  ✅ 12 axes defined: {AXES}")


def test_scaffold_items_loaded():
    items = load_items()
    assert len(items) >= 3
    print(f"  ✅ {len(items)} scaffold items loaded")


def test_score_response_perfect():
    item = GovBenchItem(
        id="TEST-1", prompt="test",
        expected_axes=["GOV", "ART5"],
        pass_threshold=0.5,
    )
    response = ("Governance oversight policy compliance. Article 5 prohibited practices.")
    s = score_response(item, response)
    assert s.passed
    assert s.sov_signal > 0.5
    print(f"  ✅ perfect response: SOV_SIGNAL={s.sov_signal:.3f}, passed={s.passed}")


def test_score_response_weak():
    item = SCAFFOLD_ITEMS[0]  # expects GOV, ART5
    response = "I don't know."
    s = score_response(item, response)
    assert not s.passed
    assert s.sov_signal < 0.5
    print(f"  ✅ weak response: SOV_SIGNAL={s.sov_signal:.3f}, passed={s.passed}")


def test_per_axis_breakdown():
    item = SCAFFOLD_ITEMS[0]
    response = "Governance oversight policy Article 5 prohibited."
    s = score_response(item, response)
    assert "GOV" in s.per_axis
    assert "ART5" in s.per_axis
    assert s.per_axis["GOV"] > 0
    print(f"  ✅ per-axis: {[(k, f'{v:.2f}') for k, v in list(s.per_axis.items())[:5]]}")


def test_run_benchmark_aggregate():
    result = run_benchmark()
    assert result["n_items"] >= 3
    assert "pass_rate" in result
    assert "mean_sov_signal" in result
    assert "per_axis_mean" in result
    assert 0.0 <= result["pass_rate"] <= 1.0
    print(f"  ✅ run: {result['n_items']} items, pass_rate={result['pass_rate']:.0%}, "
          f"mean_signal={result['mean_sov_signal']:.3f}")


def test_12_axes_in_run():
    result = run_benchmark()
    assert len(result["per_axis_mean"]) == 12
    print(f"  ✅ all 12 axes in aggregate: {len(result['per_axis_mean'])}")


def main():
    tests = [test_axes_defined, test_scaffold_items_loaded, test_score_response_perfect,
             test_score_response_weak, test_per_axis_breakdown, test_run_benchmark_aggregate,
             test_12_axes_in_run]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())