"""csoai-engine tests: status/diagnose/fix against the real signed boards."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # .../SOVOS
sys.path.insert(0, str(ROOT / "packages" / "csoai-engine" / "src"))

from csoai_engine import EngineRegistry, AXIS_LABELS


def test_registry_has_14_engines():
    reg = EngineRegistry()
    assert len(reg.engines) == 14, f"expected 14 axes, got {len(reg.engines)}"


def test_measured_engines_have_board_and_manifest():
    reg = EngineRegistry()
    for axis in AXIS_LABELS:
        eng = reg.engines[axis]
        # honest contract: an engine may be registered without a board on disk
        # (e.g. pqc greenfield). Only measured engines must have both.
        if eng.board is not None:
            assert eng.manifest is not None, f"{axis} has board but no manifest"


def test_gov_measured():
    reg = EngineRegistry()
    s = reg.engines["gov"].status()
    assert s["axis"] == "gov"
    assert s["bank_items"] == 237, s
    assert s["board_status"] == "MEASURED", s


def test_all_status_returns_14():
    reg = EngineRegistry()
    assert len(reg.all_status()) == 14


def test_diagnose_finds_gaps():
    reg = EngineRegistry()
    gaps = reg.engines["gov"].diagnose()["gaps"]
    assert isinstance(gaps, list)


def test_fix_records_signed_delta():
    reg = EngineRegistry()
    fix = reg.engines["gov"].fix("test delta: extend bank", sign_py=None)
    assert fix["axis"] == "gov"
    assert fix["delta"] == "test delta: extend bank"
    assert fix["promoted"] is None  # owner decides
    assert fix["reverted"] is None


def test_jail_diagnose_uses_gold_bank():
    reg = EngineRegistry()
    d = reg.engines["jail"].diagnose()
    assert "gaps" in d
    # jail board is MEASURED with 30/30 precision 1.0 → gap should note completeness
    if reg.engines["jail"].board and reg.engines["jail"].board.get("precision") == 1.0:
        assert any("gold bank complete" in g for g in d["gaps"])
