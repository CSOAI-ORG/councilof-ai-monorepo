"""eu-ai-act-mcp tests (SCAFFOLD)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from eu_ai_act_mcp import eu_ai_act_query, ARTICLES


def test_articles_loaded():
    assert len(ARTICLES) >= 13, f"expected ≥13 articles, got {len(ARTICLES)}"
    print(f"  ✅ {len(ARTICLES)} articles loaded")


def test_query_prohibited():
    results = eu_ai_act_query("Article 5 prohibited")
    assert len(results) >= 1
    assert any("Art5" in r["id"] for r in results)
    print(f"  ✅ prohibited query → {len(results)} matches")


def test_query_human_oversight():
    results = eu_ai_act_query("human oversight")
    assert len(results) >= 1
    assert any("Art14" in r["id"] for r in results)
    print(f"  ✅ human oversight query → {len(results)} matches")


def test_query_empty():
    assert eu_ai_act_query("") == []
    assert eu_ai_act_query("   ") == []
    print("  ✅ empty query → empty result")


def test_nist_crosswalk():
    results = eu_ai_act_query("risk management")
    assert len(results) >= 1
    assert "nist_rmf" in results[0]
    assert results[0]["nist_rmf"].startswith("MANAGE") or results[0]["nist_rmf"].startswith("GOVERN")
    print(f"  ✅ crosswalk → NIST {results[0]['nist_rmf']}")


def main():
    tests = [test_articles_loaded, test_query_prohibited, test_query_human_oversight,
             test_query_empty, test_nist_crosswalk]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  � FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())