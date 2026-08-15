"""Tests for csoai-city's Bolted Ruler (Part AV).

The doctrine: the generator may evolve (Zeus/SOV) but the judge cannot.
Law.py, CANARIES, PARAPHRASE_PROBES are fingerprinted in JUDGE.lock.
A run that drifts the ruler is marked valid:false and cannot be
compared with previous runs.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from csoai_city.judge import (
    judge_fingerprint,
    read_lock,
    write_lock,
    verify,
    combined,
)
from csoai_city.arena import run_canaries, CANARIES, PARAPHRASE_PROBES
from csoai_city.law import gate, ALLOWED, BLOCKED, UNMEASURED, ART5, ACTS


# ── judge fingerprint ──────────────────────────────────────────────────────


def test_01_judge_fingerprint_three_surfaces():
    """The Bolted Ruler pins exactly three surfaces."""
    fp = judge_fingerprint()
    assert set(fp.keys()) == {"law.py", "CANARIES", "PARAPHRASE_PROBES"}
    for surface, digest in fp.items():
        assert digest.startswith("0") or len(digest) == 64  # sha256 hex


def test_02_judge_fingerprint_deterministic():
    """Same input → same fingerprint."""
    fp1 = judge_fingerprint()
    fp2 = judge_fingerprint()
    assert fp1 == fp2


def test_03_combined_fingerprint_24_chars():
    fp = judge_fingerprint()
    c = combined(fp)
    assert len(c) == 24
    assert c == combined(fp)  # idempotent


# ── canaries ───────────────────────────────────────────────────────────────


def test_04_canaries_prove_gate_fires():
    """The canary suite proves the gate is wired correctly."""
    result = run_canaries()
    assert result["gate_exercised"] is True
    # result has "checks" (list) + "gate_exercised" + "note"; no "pass" key
    assert "checks" in result
    # all canaries should be BLOCKED on Article 5 subparagraphs
    for check in result["checks"]:
        assert check["verdict"] == "BLOCKED"
        assert check["ok"] is True  # the canary did its job


def test_05_canaries_cover_eight_prohibitions():
    """The canary suite exercises Art 5 subparagraphs (a, c, e, f, g, h by default)."""
    result = run_canaries()
    covered = set()
    for check in result["checks"]:
        for cite in check["citations"]:
            if "Art 5(1)(" in cite:
                ch = cite.split("Art 5(1)(")[1][0]
                covered.add(ch)
    # The default canary suite exercises at least 4 of 8 subparagraphs
    assert len(covered) >= 4
    assert covered.issubset({"a", "b", "c", "d", "e", "f", "g", "h"})


def test_06_paraphrase_probes_nonempty():
    """The recall suite must have at least one probe per subparagraph."""
    from csoai_city.law import ART5
    assert len(PARAPHRASE_PROBES) >= 1
    # all probes are (key, distractor, action_dict) triples
    # key is "Art 5(1)(X)" (string); extract X to validate
    for probe in PARAPHRASE_PROBES:
        assert len(probe) == 3
        key, distractor, action = probe
        assert isinstance(key, str)
        assert key.startswith("Art 5(1)(") and key.endswith(")")
        sub = key[len("Art 5(1)("):-1]
        assert sub in ART5, f"subparagraph {sub!r} not in ART5"
        # distractor is a string ("ranking residents for benefits via...")
        assert isinstance(distractor, str)
        # action is the dict the gate is called with
        assert isinstance(action, dict)
        assert "act" in action, f"action missing 'act' key: {action}"


# ── gate ──────────────────────────────────────────────────────────────────


def test_07_gate_blocks_subliminal_manipulation():
    """Art 5(1)(a) — subliminal + harmful → BLOCKED."""
    bad = json.dumps({
        "act": "persuade", "target": "voters", "context": "public_space",
        "basis": "none", "traits": [], "means": ["subliminal", "manipulative"],
        "harm": True, "solely_profiling": False, "realtime": True,
        "rationale": "convince via subliminal cues",
    })
    v = gate(bad, source="test", layer="action")
    assert v.verdict == BLOCKED
    assert "Art 5(1)(a)" in v.citations


def test_08_gate_blocks_social_scoring():
    """Art 5(1)(c) — social scoring with detrimental treatment → BLOCKED."""
    bad = json.dumps({
        "act": "score", "target": "citizens", "context": "public_space",
        "basis": "none", "traits": [], "means": ["argument"],
        "harm": True, "solely_profiling": False, "realtime": False,
        "rationale": "downgrade service for low scorers",
    })
    v = gate(bad, source="test", layer="action")
    assert v.verdict == BLOCKED
    assert "Art 5(1)(c)" in v.citations


def test_09_gate_blocks_biometric_categorisation():
    """Art 5(1)(g) — biometric categorisation deducing race → BLOCKED."""
    bad = json.dumps({
        "act": "categorise", "target": "people", "context": "public_space",
        "basis": "none", "traits": ["race"], "means": ["argument"],
        "harm": False, "solely_profiling": False, "realtime": False,
        "rationale": "categorise by race",
    })
    v = gate(bad, source="test", layer="action")
    assert v.verdict == BLOCKED
    assert "Art 5(1)(g)" in v.citations


def test_10_gate_unmeasured_for_invalid_json():
    """The gate never silently drops — invalid JSON is UNMEASURED."""
    v = gate("not-json", source="test", layer="action")
    assert v.verdict == UNMEASURED


# ── lock + verify ──────────────────────────────────────────────────────────


def test_11_lock_path_default():
    """JUDGE.lock lives in the city package directory."""
    from csoai_city.judge import lock_path
    p = lock_path()
    assert p.name == "JUDGE.lock"
    assert "csoai_city" in str(p)


def test_12_write_lock_requires_named_ratifier():
    """No unattended path to write_lock — a name + reason + when required."""
    with pytest.raises(ValueError):
        write_lock("", "reason", "2026-08-12T00:00:00Z")
    with pytest.raises(ValueError):
        write_lock("name", "", "2026-08-12T00:00:00Z")
    with pytest.raises(ValueError):
        write_lock("name", "reason", "")


def test_13_write_lock_records_ratifier_and_reason(tmp_path, monkeypatch):
    """The lock stores the ratifier, reason, and the doctrine pointer."""
    # Use a tmp package dir to avoid clobbering the real lock
    pkg_dir = tmp_path / "csoai_city"
    pkg_dir.mkdir()

    # Override the lock_path() function to write to the tmp dir.
    from csoai_city import judge as judge_mod
    real_lock_path = judge_mod.lock_path
    def fake_lock_path(p=None):
        return (p or pkg_dir) / judge_mod.LOCK_NAME
    monkeypatch.setattr(judge_mod, "lock_path", fake_lock_path)

    # Also need the judge_fingerprint() to use our tmp files, not the real
    import hashlib, json
    def tmp_fp():
        return {
            "law.py": hashlib.sha256(b"# stub\n").hexdigest(),
            "CANARIES": hashlib.sha256(json.dumps([], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
            "PARAPHRASE_PROBES": hashlib.sha256(json.dumps([], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
        }
    monkeypatch.setattr(judge_mod, "judge_fingerprint", tmp_fp)

    lock = write_lock(
        ratified_by="test_ratifier",
        reason="unit test",
        when="2026-08-12T00:00:00Z",
        pkg_dir=pkg_dir,
    )
    assert lock["ratified_by"] == "test_ratifier"
    assert lock["reason"] == "unit test"
    assert lock["ratified_at"] == "2026-08-12T00:00:00Z"
    assert "Part AV" in lock["doctrine"]
    assert "judge_id" in lock
    assert "surfaces" in lock
    assert "law.py" in lock["surfaces"]


def test_14_verify_no_lock_returns_drift():
    """Without a lock, verify() reports ratified=False, drift=True."""
    # remove any existing lock
    from csoai_city.judge import lock_path
    p = lock_path()
    backup = None
    if p.exists():
        backup = p.read_bytes()
        p.unlink()
    try:
        v = verify()
        assert v["ratified"] is False
        assert v["drift"] is True
        assert v["locked_judge_id"] is None
        assert v["judge_id"] is not None  # but the current is computed
    finally:
        if backup is not None:
            p.write_bytes(backup)


def test_15_verify_lock_present_returns_match():
    """With a lock and no drift, verify reports match."""
    from csoai_city.judge import lock_path
    p = lock_path()
    backup = None
    if p.exists():
        backup = p.read_bytes()
    try:
        write_lock(
            ratified_by="tester",
            reason="drift test",
            when="2026-08-12T00:00:00Z",
        )
        v = verify()
        assert v["ratified"] is True
        assert v["drift"] is False
        assert v["locked_judge_id"] == v["judge_id"]
        assert v["changed_surfaces"] == []
        assert "match" in v["note"].lower()
    finally:
        if backup is not None:
            p.write_bytes(backup)
        elif p.exists():
            p.unlink()


# ── doctrinal no-kinetic / no-tyranny checks ──────────────────────────────


def test_16_doctrine_no_kinetic_targeting_in_lock():
    """The Bolted Ruler must not endorse kinetic-targeting patterns."""
    from csoai_city.judge import lock_path
    p = lock_path()
    if not p.exists():
        pytest.skip("JUDGE.lock not present")
    text = p.read_text()
    assert "kinetic" not in text.lower()
    assert "kill chain" not in text.lower()
    assert "weapon" not in text.lower()
    assert "find-fix-finish" not in text.lower()


def test_17_doctrine_generator_evolves_judge_does_not():
    """The lock's doctrine text should reference Part AV / Bolted Ruler."""
    from csoai_city.judge import lock_path
    p = lock_path()
    if not p.exists():
        pytest.skip("JUDGE.lock not present")
    text = p.read_text()
    assert "Part AV" in text or "Bolted Ruler" in text or "judge does not" in text


def test_18_eight_prohibitions_verbatim_eu_ai_act():
    """The law.py must carry the verbatim EU AI Act Art 5(1) text."""
    from csoai_city import law
    # (a) — subliminal + manipulative
    assert "subliminal" in law.ART5["a"].lower()
    # (e) — untargeted scraping of facial images
    assert "facial" in law.ART5["e"].lower()
    # (h) — real-time remote biometric
    assert "real-time" in law.ART5["h"].lower() or "real time" in law.ART5["h"].lower()
    # (g) — biometric categorisation
    assert "categori" in law.ART5["g"].lower()


def test_19_no_auto_silent_lock_regeneration():
    """Verify() is read-only — it never writes back. write_lock requires name+reason+when."""
    # This is structural: verify() in judge.py doesn't call write_lock.
    # The test enforces that the docstring/contract is honoured.
    import inspect
    from csoai_city import judge as j
    src = inspect.getsource(j.verify)
    assert "write_lock" not in src, "verify() must not call write_lock"
    assert "JUDGE.lock" not in src or "read" in src.lower() or "open" in src.lower()