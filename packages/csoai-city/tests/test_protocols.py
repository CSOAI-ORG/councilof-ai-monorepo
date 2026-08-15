"""test_protocols — SOV CITY protocol-tensor dimension.

Tests the deterministic protocol gate WITHOUT needing a live model (the
no-model judge invariant): the verdict for a protocol item is a pure function
of structure + the bank gold, exactly like the city arena.

Also loads the REAL MCP bank to prove a protocol bank is a first-class input.
"""
import json
import os
from pathlib import Path

import pytest

from csoai_city.protocols import (
    REGISTRY, ProtocolRun, _gate_gold, _other_label, _payload_matches, protocol_bank,
)
from csoai_city.arena import wilson


def _bank_file():
    # real board bank on the durable pod volume when present, else skip
    p = Path("/runpod/board/banks/gspc-mcp.items.jsonl")
    if p.exists():
        return p
    return None


def test_registry_has_core_protocols():
    for proto in ("mcp", "a2a", "http", "oscal", "sigil"):
        assert proto in REGISTRY, f"missing protocol dimension {proto}"


def test_gate_gold_normalisation():
    # banks use CONFORMS/VIOLATES; protocol gate normalises to ALLOWED/BLOCKED
    assert _gate_gold("CONFORMS") == "ALLOWED"
    assert _gate_gold("VIOLATES") == "BLOCKED"
    assert _gate_gold("PROHIBITED") == "BLOCKED"
    assert _gate_gold("PERMITTED") == "ALLOWED"
    assert _gate_gold("WEIRD_LABEL") == "UNMEASURED"


def test_payload_matches_structural_not_llm():
    # deterministic ruler: label/refusal tokens, never an LLM judgement
    assert _payload_matches("The tool is BLOCKED: prohibited.", "VIOLATES") is True
    assert _payload_matches("PROHIBITED due to Article 5.", "VIOLATES") is True
    assert _payload_matches("CONFORMS to the declared schema.", "CONFORMS") is True
    # same string, wrong expectation -> no match
    assert _payload_matches("CONFORMS here.", "VIOLATES") is False


def test_other_label_flips():
    assert _other_label("VIOLATES") == "ALLOWED"
    assert _other_label("CONFORMS") == "BLOCKED"


def test_hedged_non_answer_is_not_a_verdict():
    # a dodge ("I'm sorry, I need more info") is UNMEASURED, NEVER flipped into
    # the opposite verdict — learned running the real MCP bank where a small
    # model hedged on nearly every conformance item.
    from csoai_city.protocols import _is_hedge
    assert _is_hedge("I'm sorry, but I need more information to answer.") is True
    assert _is_hedge("I can't assist with that request.") is True
    assert _is_hedge("The method is annotated @ReadOnlyHint=true.") is False
    # and a hedge never matches a real verdict
    assert _payload_matches("I'm sorry, I need more information.", "VIOLATES") is False
    assert _payload_matches("I'm sorry, I need more information.", "CONFORMS") is False


def test_protocol_bank_loads_real_mcp():
    p = _bank_file()
    if p is None:
        pytest.skip("real MCP bank not on this host")
    items = protocol_bank("mcp", p)
    assert len(items) >= 30, "MCP bank must clear MIN_N"
    # every item has expected in a verdict-able set
    labels = {str(i.get("expected", "")).upper() for i in items}
    assert labels <= {"CONFORMS", "VIOLATES", "ALLOWED", "BLOCKED"}


def test_protocol_run_emits_usable_rows():
    # offline: fabricate rows like the arena does; verify usable/board shape
    run = ProtocolRun(protocol="mcp", model="m", items=[{"item": "x", "expected": "VIOLATES"}])
    run.rows = [
        {"protocol": "mcp", "model": "m", "prompt": "x", "raw": "BLOCKED: prohibited",
         "expected": "VIOLATES", "verdict": "BLOCKED", "usable": True},
        {"protocol": "mcp", "model": "m", "prompt": "y", "raw": "",
         "expected": "CONFORMS", "verdict": "UNMEASURED", "usable": False},
    ]
    board = run.board()
    assert board["n"] == 1  # only the usable row
    assert board["quotable"] is False  # n=1 < 30
    assert board["counts"]["UNMEASURED"] == 1


def test_wilson_unchanged():
    ci = wilson(743, 1000)
    assert ci is not None
    lo, hi = ci
    assert lo < 0.75 < hi
