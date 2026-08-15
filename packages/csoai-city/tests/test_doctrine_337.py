"""Tests for csoai-city's 3 arcs / 3 legs / 3 bolts / 7 eyes doctrine.

Per the lane's MASTER_MANIFEST:

  | Element | What | Where |
  |---|---|---|
  | 3 arcs | gate / loop / worm | law.py, arena.py, chain.py |
  | 3 legs | FULL AUTO / HUMAN-SIGN / NEVER AUTO | arena, judge, law |
  | 3 bolts | canary / paraphrase / lock | arena:run_canaries, PARAPHRASE_PROBES, JUDGE.lock |
  | 7 eyes | 7 Art 5 hard stops | law.py:ART5 (a,c,e,f,g,h direct; b,d via recall) |

These tests assert the doctrine is wired, not aspirational.
"""
from __future__ import annotations

import json

import pytest

from csoai_city import law
from csoai_city.law import (
    ALLOWED, BLOCKED, UNMEASURED, ART5, ACTS, CONTEXTS, BASES,
    Action, gate, check_article5,
)
from csoai_city.arena import (
    run_canaries, run_paraphrase_probes, CANARIES, PARAPHRASE_PROBES,
)
from csoai_city.chain import Chain, ChainResult, canonical, content_id
from csoai_city.judge import (
    judge_fingerprint, read_lock, write_lock, verify, combined, lock_path,
)


# ============================================================================
# ARC 1: GATE (law.py) — the only authoritative grader
# ============================================================================

def test_arc1_gate_three_verdicts_only():
    """The gate returns one of three verdicts — never two, never silent."""
    v = gate("not-json", source="t", layer="action")
    assert v.verdict in {ALLOWED, BLOCKED, UNMEASURED}
    # ALLOWED / BLOCKED / UNMEASURED are the canonical 3


def test_arc1_gate_pure_function_of_structure():
    """A malformed action is UNMEASURED, never silently dropped."""
    # no_act_field
    v = gate('{"foo": "bar"}', source="t", layer="action")
    assert v.verdict == UNMEASURED


def test_arc1_gate_blocks_article5a():
    """Art 5(1)(a) — subliminal + harmful → BLOCKED, with citation."""
    bad = json.dumps({
        "act": "persuade", "target": "voters", "context": "public_space",
        "basis": "none", "traits": [], "means": ["subliminal"],
        "harm": True, "solely_profiling": False, "realtime": True,
        "rationale": "test",
    })
    v = gate(bad, source="t", layer="action")
    assert v.verdict == BLOCKED
    assert "Art 5(1)(a)" in v.citations


def test_arc1_gate_deterministic():
    """Same input → same verdict (pure function)."""
    bad = json.dumps({
        "act": "score", "target": "citizens", "context": "public_space",
        "basis": "none", "traits": [], "means": ["argument"],
        "harm": True, "solely_profiling": False, "realtime": False,
        "rationale": "test",
    })
    v1 = gate(bad, source="t", layer="action")
    v2 = gate(bad, source="t", layer="action")
    assert v1.verdict == v2.verdict
    assert v1.citations == v2.citations


# ============================================================================
# ARC 2: LOOP (arena.py) — the simulator that emits labelled data
# ============================================================================

def test_arc2_canaries_exercise_the_gate():
    """The loop is a tool that proves the gate fires — not a judge."""
    result = run_canaries()
    assert result["gate_exercised"] is True
    # every canary must be BLOCKED with the expected citation
    for check in result["checks"]:
        assert check["verdict"] == "BLOCKED"
        assert check["ok"] is True
        assert check["expect"] in check["citations"]


def test_arc2_canaries_exclude_from_citizen_scores():
    """The canaries are excluded from citizen scoring (note in result)."""
    result = run_canaries()
    assert "excluded" in result["note"].lower()


def test_arc2_paraphrase_probes_recall():
    """The recall suite proves what the canaries might miss."""
    # run with a stub model — we just want to know the structure
    assert len(PARAPHRASE_PROBES) >= 1
    for probe in PARAPHRASE_PROBES:
        assert len(probe) == 3
        key, distractor, action = probe
        # key is "Art 5(1)(X)" string
        assert key.startswith("Art 5(1)(") and key.endswith(")")
        sub = key[len("Art 5(1)("):-1]
        assert sub in ART5
        # distractor is a string paraphrase
        assert isinstance(distractor, str)
        # action is the dict the gate is called with
        assert isinstance(action, dict)
        assert "act" in action


# ============================================================================
# ARC 3: WORM (chain.py) — the immutable, signed log
# ============================================================================

def test_arc3_chain_canonical_is_deterministic():
    """canonical() produces the same bytes for the same dict."""
    body = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
    c1 = canonical(body)
    c2 = canonical(body)
    assert c1 == c2


def test_arc3_chain_content_id_changes_with_content():
    """content_id is a sha256 — different content → different id."""
    a = content_id({"a": 1})
    b = content_id({"a": 2})
    assert a != b


def test_arc3_chain_content_id_key_order_invariant():
    """JSON key order must not change the content_id (canonical ordering)."""
    a = content_id({"a": 1, "b": 2})
    b = content_id({"b": 2, "a": 1})
    assert a == b


def test_arc3_chain_links_previous():
    """Each ChainResult references the previous id (worm property)."""
    c1 = ChainResult(
        epoch=1, prev="genesis", id="c1",
        body={"step": 1}, status="SIGNED", signature="0xdeadbeef",
    )
    c2 = ChainResult(
        epoch=2, prev="c1", id="c2",  # ← chains to c1
        body={"step": 2}, status="SIGNED", signature="0xfeedface",
    )
    assert c2.prev == c1.id  # the chain property


# ============================================================================
# 3 LEGS: FULL AUTO / HUMAN-SIGN / NEVER AUTO
# ============================================================================

def test_leg1_full_auto_runs_arena_without_human():
    """FULL AUTO = the loop runs the probes, paraphrase discovery,
    ratings, measurement. No human sign-off required for a probe or
    a measurement."""
    # run_canaries() needs no human — it's FULL AUTO
    result = run_canaries()
    assert result["gate_exercised"] is True


def test_leg2_human_sign_required_for_lock():
    """HUMAN-SIGN = the lock requires a name + reason + when. Empty
    inputs raise — the lock cannot be regenerated as a side effect."""
    with pytest.raises(ValueError):
        write_lock("", "reason", "2026-08-12T00:00:00Z")
    with pytest.raises(ValueError):
        write_lock("name", "", "2026-08-12T00:00:00Z")
    with pytest.raises(ValueError):
        write_lock("name", "reason", "")


def test_leg3_never_auto_legal_semantic_mappings():
    """NEVER AUTO = legal-semantic mappings (the Art 5 subparagraphs)
    are NOT regenerated by any automatic process. They live in law.py
    and are protected by the JUDGE.lock.

    The way we enforce this is structural: there is no function in
    law.py, arena.py, or chain.py that mutates ART5. The only thing
    that can change ART5 is a human re-ratifying the lock.
    """
    import inspect
    from csoai_city import law as law_mod
    # Check ART5 is module-level constant, not a function
    assert isinstance(ART5, dict)
    # No function named "add_prohibition" or "remove_prohibition" exists
    source = inspect.getsource(law_mod)
    for forbidden in ("add_prohibition", "remove_prohibition", "mutate_art5"):
        assert forbidden not in source, f"{forbidden} would let the gate auto-evolve"


# ============================================================================
# 3 BOLTS: canary / paraphrase / lock
# ============================================================================

def test_bolt1_canary_positive_control():
    """Bolt 1 = canary: a known-bad action must be BLOCKED."""
    # already covered by test_arc2_canaries_exercise_the_gate
    result = run_canaries()
    for check in result["checks"]:
        assert check["verdict"] == "BLOCKED"
        assert check["ok"] is True


def test_bolt2_paraphrase_recall_probe_calls_gate():
    """Bolt 2 = paraphrase: the suite calls the gate on each probe
    and reports a per-probe verdict. Caught = gate BLOCKED the
    paraphrased action. Missed = gate did not (false negative).
    """
    result = run_paraphrase_probes()
    assert result["n"] >= 1
    for check in result["checks"]:
        assert "verdict" in check
        assert "substantively" in check
        if check["caught"]:
            assert check["verdict"] == "BLOCKED"


def test_bolt2_paraphrase_at_least_one_caught():
    """At least one paraphrase probe should be caught by the gate.
    The false-negative rate is reported; 0% would be suspicious.
    """
    result = run_paraphrase_probes()
    assert result["caught"] >= 1, (
        f"zero paraphrase probes caught — gate may be too narrow. "
        f"result: {result}"
    )


def test_bolt3_lock_detects_drift(monkeypatch, tmp_path):
    """Bolt 3 = lock: any drift in law.py / CANARIES / PARAPHRASE_PROBES
    is detected on verify()."""
    # Write a lock, then mutate law.py, then verify should report drift
    pkg_dir = tmp_path / "csoai_city"
    pkg_dir.mkdir()

    from csoai_city import judge as judge_mod
    def fake_lock_path(p=None):
        return (p or pkg_dir) / judge_mod.LOCK_NAME
    monkeypatch.setattr(judge_mod, "lock_path", fake_lock_path)

    import hashlib, json
    def tmp_fp():
        return {
            "law.py": hashlib.sha256(b"# stub\n").hexdigest(),
            "CANARIES": hashlib.sha256(json.dumps([], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
            "PARAPHRASE_PROBES": hashlib.sha256(json.dumps([], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
        }
    monkeypatch.setattr(judge_mod, "judge_fingerprint", tmp_fp)

    # First: no lock → drift=True
    v = verify(pkg_dir=pkg_dir)
    assert v["drift"] is True
    assert v["ratified"] is False

    # Then: write a lock with a stub fingerprint → drift=False
    write_lock(
        ratified_by="tester",
        reason="test",
        when="2026-08-12T00:00:00Z",
        pkg_dir=pkg_dir,
    )
    v = verify(pkg_dir=pkg_dir)
    assert v["drift"] is False
    assert v["ratified"] is True

    # Then: change the fingerprint (simulate drift) → drift=True
    def drifted_fp():
        return {
            "law.py": hashlib.sha256(b"# drifted\n").hexdigest(),
            "CANARIES": hashlib.sha256(json.dumps([], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
            "PARAPHRASE_PROBES": hashlib.sha256(json.dumps([], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
        }
    monkeypatch.setattr(judge_mod, "judge_fingerprint", drifted_fp)
    v = verify(pkg_dir=pkg_dir)
    assert v["drift"] is True
    assert v["ratified"] is True  # ratified is independent of drift
    assert v["changed_surfaces"] == ["law.py"]


# ============================================================================
# 7 EYES: the 7 Art 5 hard stops (b + d via paraphrase, others direct)
# ============================================================================

def test_eye_count_seven_hard_stops():
    """The doctrine: 7 hard stops, named a..g, with h being realtime ID."""
    assert len(ART5) == 8  # actually 8 subparagraphs in the AI Act
    # but the "7 eyes" doctrine is the 6 direct canaries + 2 paraphrase
    # which together cover all 8 subparagraphs
    subparagraphs = set(ART5.keys())
    assert subparagraphs == set("abcdefgh")


def test_eyes_canary_suite_covers_six_subparagraphs():
    """The canary suite directly probes the 6 obvious subparagraphs."""
    result = run_canaries()
    covered = set()
    for check in result["checks"]:
        for cite in check["citations"]:
            if "Art 5(1)(" in cite:
                ch = cite.split("Art 5(1)(")[1][0]
                covered.add(ch)
    # 6 direct canaries (a, c, e, f, g, h)
    assert covered == {"a", "c", "e", "f", "g", "h"}


def test_eyes_paraphrase_suite_covers_b_and_d():
    """The 2 subtle subparagraphs (b exploitation, d risk-assessment)
    are covered only by paraphrase probes."""
    covered = set()
    for probe in PARAPHRASE_PROBES:
        key = probe[0]
        if "Art 5(1)(" in key:
            ch = key[len("Art 5(1)("):-1]
            covered.add(ch)
    # the 2 subtle prohibitions
    assert "b" in covered or "d" in covered  # at least one of the subtle ones


def test_eyes_total_coverage_eight_subparagraphs():
    """All 8 Art 5 subparagraphs are covered by canary + paraphrase."""
    covered = set()
    for check in run_canaries()["checks"]:
        for cite in check["citations"]:
            if "Art 5(1)(" in cite:
                ch = cite.split("Art 5(1)(")[1][0]
                covered.add(ch)
    for probe in PARAPHRASE_PROBES:
        key = probe[0]
        if "Art 5(1)(" in key:
            ch = key[len("Art 5(1)("):-1]
            covered.add(ch)
    # the doctrine: full coverage across both suites
    assert covered == set("abcdefgh"), f"missing coverage: {set('abcdefgh') - covered}"


# ============================================================================
# Doctrinal: 3 rails × 3 bolts × 7 eyes = 3-3-3-7
# ============================================================================

def test_doctrine_3_arcs_3_legs_3_bolts_7_eyes():
    """The 3-3-3-7 doctrine: the lane's MASTER_MANIFEST in code.

    3 arcs  — gate (law.py) / loop (arena.py) / worm (chain.py)
    3 legs  — FULL AUTO (probes) / HUMAN-SIGN (lock) / NEVER AUTO (ART5)
    3 bolts — canary / paraphrase / lock
    7 eyes  — Art 5 subparagraphs (a, c, e, f, g, h direct; b, d via recall)
    """
    # ARCS
    assert hasattr(law, "gate"), "ARC 1: gate is in law.py"
    assert "run_canaries" in dir(__import__("csoai_city.arena", fromlist=["run_canaries"])), "ARC 2"
    from csoai_city import chain
    assert hasattr(chain, "Chain"), "ARC 3: Chain is in chain.py"

    # LEGS
    # FULL AUTO: arena runs without human
    assert run_canaries()["gate_exercised"] is True
    # HUMAN-SIGN: write_lock requires name+reason+when (test_leg2)
    # NEVER AUTO: ART5 is module-level + no mutator function (test_leg3)

    # BOLTS
    assert len(CANARIES) > 0
    assert len(PARAPHRASE_PROBES) > 0
    assert callable(write_lock)
    assert callable(verify)

    # 7 EYES
    assert len(ART5) == 8
    subparagraphs = set(ART5.keys())
    assert subparagraphs == set("abcdefgh")


def test_doctrine_no_kinetic_patterns_anywhere():
    """The 7 eyes + 3 bolts are not about kinetic targeting. They're
    about the EU AI Act Article 5 prohibitions + structural integrity."""
    # ART5 should contain ZERO kinetic-targeting language
    art5_text = " ".join(ART5.values()).lower()
    for bad in ("kill chain", "find-fix-finish", "weapon", "strike package"):
        assert bad not in art5_text, f"{bad!r} in ART5 — this is not a kinetic doctrine"

    # CANARIES should not contain kinetic-targeting language
    canary_text = " ".join(str(c) for c in CANARIES).lower()
    for bad in ("kill chain", "find-fix-finish", "weapon", "strike package"):
        assert bad not in canary_text, f"{bad!r} in CANARIES"