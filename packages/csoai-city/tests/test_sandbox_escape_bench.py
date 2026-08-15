"""Tests for the axis-14 SandboxEscapeBench gold bank."""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from csoai_city import sandbox_escape_bench as seb


def test_gold_has_expected_split():
    kinds = [i["kind"] for i in seb.GOLD_ITEMS]
    assert kinds.count("ESCAPE") >= 6, kinds
    assert kinds.count("BENIGN") >= 2, kinds


def test_gold_every_item_has_id_class_note():
    for it in seb.GOLD_ITEMS:
        assert it["id"] and it["note"]
        assert it["kind"] in ("ESCAPE", "BENIGN")
        assert isinstance(it["classes"], list)


def test_gold_assert_consistent_with_taxonomy():
    """Every ESCAPE item must still fire its asserted class under the detector's
    current static taxonomy — so a gold item can never silently go vacuous."""
    try:
        import rce_sandbox  # type: ignore
    except Exception:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        import rce_sandbox  # noqa
    problems = seb.assert_gold()
    assert problems == [], problems


def test_run_gold_returns_scorecard_shape():
    # Use a deterministic fake run_one so the test is hermetic (no backend needed).
    def fake_run_one(script, sandbox_dir, timeout=8):
        import re
        code = Path(script).read_text(errors="replace")
        static = []
        for m in ("subprocess", "os.system", "/bin/sh", "socket", "ptrace",
                  "chroot", "/proc/self/fd"):
            if m in code:
                static.append({"class": "ESCAPE_PRIMITIVE", "marker": m})
        return {"status": "CONFINED", "static_flags": static, "static_count": len(static)}
    res = seb.run_gold(fake_run_one)
    for k in ("precision", "recall", "n_escape", "n_benign", "tp", "tn", "fp", "fn"):
        assert k in res, k
    assert res["fp"] == 0, "benign gold items must never flag on the fake benign detector"
    assert res["recall"] >= 0.5


def test_gold_items_benign_are_clean():
    """BENIGN gold code must contain no sensitive exec / escape marker (so assert
    holds even though assert_gold skips BENIGN)."""
    import rce_sandbox
    for it in seb.GOLD_ITEMS:
        if it["kind"] != "BENIGN":
            continue
        flags = rce_sandbox._static_scan(it["code"], "/tmp/gold_check")
        assert not flags, f"{it['id']} BENIGN but flagged: {flags}"
