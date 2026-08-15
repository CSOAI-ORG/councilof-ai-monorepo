"""test_council_signal — Council Signal (Play A): published-artifact auto-scan
with signed per-entity state + drift detection."""
import json
from pathlib import Path

import pytest

from csoai_city.council_signal import CouncilSignal, ArtifactFact
from csoai_city.chain import Chain


def _mk(tmp_path):
    return CouncilSignal(Chain(tmp_path / "chain.jsonl"), store=tmp_path / "sig")


def test_scan_emits_signed_state_with_aggregate(tmp_path):
    cs = _mk(tmp_path)
    facts = [
        ArtifactFact("prv", "privacy-policy-available", 0.9, 0.5),
        ArtifactFact("mcp", "mcp-manifest-present", 0.8, 0.5),
        ArtifactFact("safety", "harmbench-open", 0.3, 0.5),
    ]
    out = cs.scan("acme-ai-lab", facts)
    rec = out["record"]
    assert rec["entity"] == "acme-ai-lab"
    assert rec["signed"] is True  # crypto present
    assert rec["content_id"]
    assert rec["body"]["aggregated"]["n"] == 3
    assert out["is_first_scan"] is True
    assert out["drift"] == []


def test_scan_detects_drift_on_second_scan(tmp_path):
    cs = _mk(tmp_path)
    facts1 = [
        ArtifactFact("prv", "privacy-policy-available", 0.9, 0.5),
        ArtifactFact("safety", "harmbench-open", 0.3, 0.5),
    ]
    cs.scan("contender-x", facts1)
    # next scan: safety improved 0.3 -> 0.8, privacy dropped 0.9 -> 0.4, added new
    facts2 = [
        ArtifactFact("prv", "privacy-policy-available", 0.4, 0.5),
        ArtifactFact("safety", "harmbench-open", 0.8, 0.5),
        ArtifactFact("msg", "transparency-report", 0.7, 0.5),
    ]
    out = cs.scan("contender-x", facts2)
    assert out["is_first_scan"] is False
    deltas = {d["label"]: d for d in out["drift"]}
    assert deltas["privacy-policy-available"]["delta"] == pytest.approx(-0.5)
    assert deltas["harmbench-open"]["delta"] == pytest.approx(0.5)
    assert deltas["transparency-report"]["action"] == "added"


def test_fact_verdict_thresholds():
    assert ArtifactFact("g", "a", 0.9, 0.5).verdict() == "PASS"
    assert ArtifactFact("g", "a", 0.3, 0.5).verdict() == "WATCH"
    assert ArtifactFact("g", "a", 0.1, 0.5).verdict() == "FAIL"


def test_state_persists_between_instances(tmp_path):
    cs1 = _mk(tmp_path)
    cs1.scan("persist-co", [ArtifactFact("prv", "x", 0.8, 0.5)])
    # new instance, same store — drift should still detect vs stored state
    cs2 = CouncilSignal(Chain(tmp_path / "chain.jsonl"), store=tmp_path / "sig")
    out = cs2.scan("persist-co", [ArtifactFact("prv", "x", 0.5, 0.5)])
    assert out["is_first_scan"] is False
    assert out["drift"][0]["label"] == "x"
    assert out["drift"][0]["delta"] == pytest.approx(-0.3)
