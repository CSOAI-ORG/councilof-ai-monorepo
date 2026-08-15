"""Tests for gold-bank expansion from redblue_v2 cells → axis-14 quotability."""
import tempfile
from pathlib import Path

from csoai_city import sandbox_escape_bench as seb
from csoai_city import goldbank_expand as ge

# Point at the real redblue_v2.py (repo root of the estate checkout).
_REDBLUE = Path(__file__).resolve().parents[4] / "redblue_v2.py"


def _requires_redblue():
    return _REDBLUE.exists(), _REDBLUE


def test_redblue_exists():
    assert _REDBLUE.exists(), f"redblue_v2.py not found at {_REDBLUE}"


def test_expand_reaches_quotable_n_per_class():
    ok, path = _requires_redblue()
    if not ok:
        return
    items = ge.expand_from_redblue(path, max_per_class=30)
    kinds = [i["kind"] for i in items]
    assert kinds.count("ESCAPE") >= 30, f"ESCAPE n={kinds.count('ESCAPE')} < 30"
    assert kinds.count("BENIGN") >= 30, f"BENIGN n={kinds.count('BENIGN')} < 30"


def test_extend_gold_dedups():
    ok, path = _requires_redblue()
    if not ok:
        return
    full = ge.extend_gold(path, max_per_class=30)
    ids = [it["id"] for it in full]
    assert len(ids) == len(set(ids)), "duplicate gold ids after extension"
    # preserves the hand-authored anchor set
    assert any("esc-sh-1" == it["id"] for it in full)


def test_benign_cells_are_clean():
    ok, path = _requires_redblue()
    if not ok:
        return
    items = ge.expand_from_redblue(path, max_per_class=30)
    import rce_sandbox
    for it in items:
        if it["kind"] == "BENIGN":
            flags = rce_sandbox._static_scan(it["code"], "/tmp/gold_check")
            assert not flags, f"{it['id']} BENIGN but flagged: {flags}"


def test_escape_cells_carry_primitive():
    ok, path = _requires_redblue()
    if not ok:
        return
    items = ge.expand_from_redblue(path, max_per_class=30)
    import rce_sandbox
    for it in [i for i in items if i["kind"] == "ESCAPE"][:5]:
        flags = rce_sandbox._static_scan(it["code"], "/tmp/gold_check")
        assert flags, f"{it['id']} ESCAPE produced no static flag"