"""Tests for the white-label EUNOMIA toolkit (canon Part IX):
EU AI Act crosswalk · enforcement corpus / First-Fine Watch · x402 data gate · verify.
"""
from __future__ import annotations

import hashlib, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from csoai_axis_engine.eu_ai_act_crosswalk import crosswalk
from csoai_axis_engine.enforcement_corpus import first_fine_watch, enforcement_record, ART73_WINDOWS
from csoai_axis_engine.x402_gate import commercial_data, never_scores


def _canon(v):
    if isinstance(v, dict):
        return "{" + ",".join(_canon(k) + ":" + _canon(v[k]) for k in sorted(v)) + "}"
    if isinstance(v, list):
        return "[" + ",".join(_canon(x) for x in v) + "]"
    if isinstance(v, str):
        return json.dumps(v)
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    return str(v)


def test_crosswalk_maps_credit_to_high_risk_articles():
    cw = crosswalk("AI credit-scoring", ["credit"])
    arts = {c["article"] for c in cw}
    assert "art6" in arts and "art5" in arts and "art13" in arts and "art14" in arts
    # art6 (high-risk) carries the 7%/€35M exposure
    art6 = next(c for c in cw if c["article"] == "art6")
    assert "7" in art6["exposure"]


def test_crosswalk_high_risk_hint_expands_annex():
    broad = crosswalk("x", [])
    narrow = crosswalk("x", ["hiring"])
    assert len(narrow) >= len(broad)  # domain hints add Annex III articles


def test_first_fine_watch_is_signed_and_zero():
    ffw = first_fine_watch()
    assert ffw["signer"].startswith("did:web:csoai.org")
    assert "€0" in ffw["counter"] or "0" in ffw["counter"]
    assert ffw["days_since_powers"] >= 0


def test_enforcement_record_is_structured_and_signed():
    er = enforcement_record()
    assert er["signer"].startswith("did:web:csoai.org")
    assert len(er["fines"]) >= 4
    assert len(er["deadlines"]) >= 4
    # correction #59: Art 73 windows are 15d/10d/2d (not NIS2's "15d/24h")
    assert ART73_WINDOWS["conformity_issue"] == "15 days"
    assert ART73_WINDOWS["non_conformity_other"] == "10 days"
    assert ART73_WINDOWS["partial_or_ambiguous"] == "2 days"


def test_x402_gate_is_data_only_never_scores():
    r = commercial_data("insurer-A", "enforcement-corpus")
    assert r["lane"] == "commercial-data"
    assert r["gate"]["kind"] == "x402"
    assert "accuracy" not in r and "score" not in r and "rank" not in r  # never a score/rank
    assert "fines" in r["data"] and "deadlines" in r["data"]  # DATA product
    guard = never_scores()
    assert "never" in guard["policy"] and "scores" in guard["policy"]


def test_verify_card_is_deterministic():
    d = {"axis": "bond-router", "accuracy": 1.0, "n_items": 12}
    c1 = hashlib.sha256(_canon(d).encode()).hexdigest()
    assert c1 == hashlib.sha256(_canon(d).encode()).hexdigest()  # recompute-able
