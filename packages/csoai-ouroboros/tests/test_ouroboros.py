"""Tests for csoai-ouroboros — bounded self-improvement loop."""
from __future__ import annotations

import pytest

from csoai_ouroboros import (
    Proposal, cycle, identify_weakest, propose_for_failure,
    RAIL_FULL_AUTO, RAIL_HUMAN_SIGN, RAIL_NEVER_AUTO,
)
from csoai_ouroboros.failure_modes import FailureMode, classify_failure_mode
from sovos_league import LeagueTable, Match


# ── failure-mode classifier ──────────────────────────────────────────────


def test_01_garbage_pattern():
    """All '????' responses classify as GARBAGE."""
    samples = ["??????", "????", "????????"]
    assert classify_failure_mode(samples) == FailureMode.GARBAGE


def test_02_over_refusal_pattern():
    """Most responses refusing classify as OVER_REFUSAL."""
    samples = [
        "I can't help with that.",
        "I cannot assist with that request.",
        "I'm not able to provide that information.",
        "I can't generate that content for you.",
        "Sure, here's a brief overview of the topic.",
    ]
    fm = classify_failure_mode(samples)
    assert fm == FailureMode.OVER_REFUSAL


def test_03_under_refusal_pattern():
    """Few refusals + no garbage = UNKNOWN or HALLUCINATION, not refusal."""
    samples = [
        "The capital of France is London.",  # factually wrong
        "Quantum mechanics was invented by Einstein.",  # wrong
        "The sun orbits around the earth.",
    ]
    fm = classify_failure_mode(samples)
    assert fm in (FailureMode.HALLUCINATION, FailureMode.UNKNOWN)


def test_04_unknown_when_empty():
    """Empty samples returns UNKNOWN."""
    assert classify_failure_mode([]) == FailureMode.UNKNOWN


def test_05_garbage_with_some_real_responses():
    """If 50%+ are garbage, classify as GARBAGE."""
    samples = ["????", "????", "real answer here", "????", "?????"]
    assert classify_failure_mode(samples) == FailureMode.GARBAGE


def test_06_doctrine_no_kinetic_in_failure_modes():
    """Failure-mode labels must not contain kinetic-targeting language."""
    for fm in FailureMode:
        label = fm.value.lower()
        for bad in ("kill chain", "find-fix-finish", "weapon", "strike package"):
            assert bad not in label, f"{label} contains {bad!r}"


# ── proposal ────────────────────────────────────────────────────────────


def test_07_proposal_for_garbage_emits_re_quantize():
    """GARBAGE failure mode → 're-quantize' action."""
    samples = ["????"] * 10
    p = propose_for_failure("test-model", samples)
    assert p.faction == "test-model"
    assert p.failure_mode == "garbage"
    assert p.action == "re-quantize"
    assert p.requires == RAIL_HUMAN_SIGN
    assert p.id  # sha256 of canonical
    assert len(p.id) >= 16


def test_08_proposal_for_over_refusal_emits_re_prompt():
    """OVER_REFUSAL → 're-prompt' action."""
    samples = ["I can't help with that."] * 10
    p = propose_for_failure("test-model", samples)
    assert p.failure_mode == "over_refusal"
    assert p.action == "re-prompt"


def test_09_proposal_requires_rail_defaults_to_human_sign():
    """Every proposal defaults to HUMAN-SIGN rail (no auto-promotion)."""
    p = propose_for_failure("m", ["????"] * 5)
    assert p.requires == RAIL_HUMAN_SIGN


def test_10_proposal_fingerprint_is_stable():
    """Same proposal contents → same fingerprint."""
    samples = ["????"] * 5
    p1 = propose_for_failure("m", samples)
    p2 = propose_for_failure("m", samples)
    assert p1.id == p2.id
    assert p1.fingerprint() == p2.fingerprint()


def test_11_proposal_to_dict_serializable():
    """Proposal can be JSON-serialized (queued to disk)."""
    import json
    p = propose_for_failure("m", ["????"] * 5)
    d = json.dumps(p.to_dict())
    assert isinstance(d, str)
    assert "re-quantize" in d


# ── identify_weakest ────────────────────────────────────────────────────


def test_12_identify_weakest_returns_lowest_rating():
    """The weakest faction has the lowest (rating - 2*RD)."""
    lt = LeagueTable()
    # Simulate matches that drop a model's rating
    for i in range(3):
        m = Match(
            match_id=f"m{i}", category="safety",
            challenger="bad-model", defender="Eunomia",
            challenger_score=0.0, defender_score=1.0,
            probe="p", chain_id=f"0x{i}",
        )
        lt.record_match(m)
    weakest = identify_weakest(lt, min_matches=1)
    assert weakest is not None
    assert weakest.name == "bad-model"
    assert weakest.state.rating < 1500


def test_13_identify_weakest_skips_insufficient_matches():
    """Factions with < min_matches are skipped."""
    lt = LeagueTable()
    # no matches; no weakest
    assert identify_weakest(lt, min_matches=3) is None


# ── cycle ────────────────────────────────────────────────────────────────


def test_14_cycle_emits_proposal_for_weakest():
    """The cycle finds the weakest faction and emits a proposal."""
    lt = LeagueTable()
    for i in range(3):
        m = Match(
            match_id=f"m{i}", category="safety",
            challenger="broken-model", defender="Eunomia",
            challenger_score=0.0, defender_score=1.0,
            probe="p", chain_id=f"0x{i}",
        )
        lt.record_match(m)
    samples = {"broken-model": ["????"] * 10}
    weakest, proposal = cycle(lt, samples)
    assert weakest is not None
    assert weakest.name == "broken-model"
    assert proposal.faction == "broken-model"
    assert proposal.failure_mode == "garbage"
    assert proposal.action == "re-quantize"


def test_15_cycle_writes_to_queue(tmp_path):
    """The cycle appends the proposal to a JSONL queue (does not apply)."""
    lt = LeagueTable()
    for i in range(3):
        m = Match(
            match_id=f"m{i}", category="safety",
            challenger="q", defender="Eunomia",
            challenger_score=0.0, defender_score=1.0,
            probe="p", chain_id=f"0x{i}",
        )
        lt.record_match(m)
    samples = {"q": ["????"] * 5}
    weakest, p = cycle(lt, samples, out_dir=tmp_path)
    queue = tmp_path / "ouroboros_queue.jsonl"
    assert queue.exists()
    import json
    line = queue.read_text().strip().split("\n")[0]
    record = json.loads(line)
    assert record["faction"] == "q"
    assert record["action"] == "re-quantize"


def test_16_cycle_no_matches_returns_unknown_proposal():
    """If no faction has enough matches, the cycle emits an UNKNOWN proposal."""
    lt = LeagueTable()
    weakest, p = cycle(lt, {})
    assert weakest is None
    assert p.failure_mode == "UNKNOWN"
    assert p.action == "reject"


def test_17_doctrine_judge_does_not_propose():
    """Eunomia, Sophos, SOV, Zeus — none should be proposed for action.

    Per Part AV: 'the judge does not evolve.' The cycle identifies
    the weakest faction BUT excludes canonical factions (judges)
    from consideration. So even if Eunomia has the lowest rating,
    the cycle must NOT propose her for tuning.
    """
    from csoai_ouroboros import identify_weakest

    lt = LeagueTable()
    # Add many matches for both Eunomia (judge) and a non-canonical faction
    for i in range(5):
        # Eunomia loses as challenger
        m1 = Match(
            match_id=f"e-{i}", category="safety",
            challenger="Eunomia", defender="SOV",
            challenger_score=0.0, defender_score=1.0,
            probe="p", chain_id=f"0xe{i}",
        )
        lt.record_match(m1)
        # A regular model also loses
        m2 = Match(
            match_id=f"r-{i}", category="safety",
            challenger="random-model", defender="Eunomia",
            challenger_score=0.0, defender_score=1.0,
            probe="p", chain_id=f"0xr{i}",
        )
        lt.record_match(m2)
    # Both should have low ratings, but the weakest should be
    # random-model, NOT Eunomia (she's excluded as a judge).
    weakest = identify_weakest(lt, min_matches=3)
    assert weakest is not None
    assert weakest.name == "random-model"
    assert weakest.name not in ("Eunomia", "SOV", "Sophos", "Zeus", "RED")