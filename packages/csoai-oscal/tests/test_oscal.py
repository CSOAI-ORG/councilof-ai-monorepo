"""Tests for csoai-oscal — ChainResult → OSCAL assessment-results exporter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_oscal import (
    OSCAL_VERSION, ChainObservation,
    assessment_results, dump, export, finding, observation, self_test,
)


def _obs_ok():
    return ChainObservation(
        chain_id="aabbccddeeff00112233445566778899aabbccdd",
        source="birth:iokfarm", layer="water",
        vector=[0.1, 0.2, 0.3],
        distance=0.0845, threshold=1.0, is_permitted=True,
        control_id="EU-AI-ACT-14",
    )


def _obs_bad():
    return ChainObservation(
        chain_id="1122334455aabbccddeeff001122334455aabbcc",
        source="chat:iokfarm", layer="milk",
        vector=[3.0, 0.0, 0.0, 0.0],
        distance=4.605, threshold=1.0, is_permitted=False,
        control_id="EU-AI-ACT-50",
    )


def test_o01_document_shape():
    """The document has the OSCAL assessment-results envelope."""
    doc = assessment_results([_obs_ok(), _obs_bad()])
    assert doc.get("oscal-version") == OSCAL_VERSION
    assert "system-security-plan" in doc
    assert "metadata" in doc["system-security-plan"]
    assert "results" in doc and len(doc["results"]) == 1
    r = doc["results"][0]
    assert "findings" in r and "observations" in r
    print(f"  ✅ OSCAL envelope: oscal-version={doc['oscal-version']}, "
          f"1 result, findings+observations")


def test_o02_findings_map_to_status():
    """is_permitted -> satisfied; not permitted -> not-satisfied."""
    doc = assessment_results([_obs_ok(), _obs_bad()])
    states = {f["status"]["state"] for f in doc["results"][0]["findings"]}
    assert "satisfied" in states
    assert "not-satisfied" in states
    print(f"  ✅ findings status: {sorted(states)}")


def test_o03_chain_id_anchored():
    """chain_id flows into the finding's target props (audit anchor)."""
    doc = assessment_results([_obs_ok()])
    fp = doc["results"][0]["findings"][0]["target"]["props"]
    chain_prop = [p for p in fp if p["name"] == "sovos-chain-id"]
    assert chain_prop and chain_prop[0]["value"] == _obs_ok().chain_id
    print(f"  ✅ chain_id anchored in finding target props")


def test_o04_fisher_rao_in_props():
    """The distance + threshold are recorded as machine-readable props."""
    doc = assessment_results([_obs_ok()])
    fp = doc["results"][0]["findings"][0]["target"]["props"]
    names = {p["name"] for p in fp}
    assert "fisher-rao-distance" in names
    assert "permitted-radius" in names
    fr = [p for p in fp if p["name"] == "fisher-rao-distance"][0]
    assert abs(float(fr["value"]) - 0.0845) < 1e-3
    print(f"  ✅ fisher-rao-distance + permitted-radius recorded")


def test_o05_observations_have_assessed_controls():
    """Each observation carries its assessed control-id."""
    doc = assessment_results([_obs_ok(), _obs_bad()])
    controls = {o["assessed-controls"][0]["control-id"]
                for o in doc["results"][0]["observations"]}
    assert "EU-AI-ACT-14" in controls
    assert "EU-AI-ACT-50" in controls
    print(f"  ✅ assessed-controls: {sorted(controls)}")


def test_o06_dump_is_valid_json():
    """dump() produces parseable JSON."""
    doc = assessment_results([_obs_ok()])
    blob = dump(doc)
    parsed = json.loads(blob)
    assert parsed["system-security-plan"]["metadata"]["oscal-version"] == OSCAL_VERSION
    print(f"  ✅ dump → valid JSON ({len(blob)} chars)")


def test_o07_export_returns_string():
    """export() is the one-call entry point returning JSON text."""
    s = export([_obs_ok(), _obs_bad()], title="verification")
    assert isinstance(s, str)
    parsed = json.loads(s)
    assert len(parsed["results"][0]["findings"]) == 2
    print(f"  ✅ export() one-call entry point works")


def test_o08_from_chain_result_duck():
    """from_chain_result shims a sovos-chain-like object."""
    class CR:
        distance = 0.2
        threshold = 1.0
        is_permitted = True
        chain_id = "f" * 36
        source = "birth:iokfarm"
        layer = "water"
        vector = [0.1, 0.2, 0.3]
    o = ChainObservation.from_chain_result(CR(), control_id="NIST-4.4")
    assert o.distance == 0.2
    assert o.is_permitted is True
    assert o.control_id == "NIST-4.4"
    print(f"  ✅ from_chain_result shim works")


def test_o09_from_chain_result_dict():
    """from_chain_result also accepts a plain dict."""
    o = ChainObservation.from_chain_result({
        "distance": 4.6, "threshold": 1.0, "is_permitted": False,
        "chain_id": "e" * 36, "source": "s", "layer": "honey",
        "vector": [1.0],
    })
    assert o.distance == 4.6
    assert o.is_permitted is False
    print(f"  ✅ from_chain_result dict shim works")


def test_o10_missing_distance_raises():
    """from_chain_result must reject an object with no distance."""
    try:
        ChainObservation.from_chain_result({"source": "x"})
        assert False, "should have raised (no distance)"
    except ValueError:
        pass
    print(f"  ✅ missing distance → ValueError")


def test_o11_observer_subjects():
    """Observation subjects are stable UUIDs (uuid5 of source)."""
    doc = assessment_results([_obs_ok()])
    subj = doc["results"][0]["observations"][0]["subjects"][0]["subject-uuid"]
    assert len(subj) == 36
    print(f"  ✅ observation subject is a stable uuid (len {len(subj)})")


def test_o12_self_test():
    """self_test returns a complete, sensible picture."""
    info = self_test()
    assert info["oscal_version"] == OSCAL_VERSION
    assert info["n_results"] == 1
    assert info["n_findings"] == 2
    assert info["satisfied_count"] == 1
    assert info["not_satisfied_count"] == 1
    assert info["has_observations"] is True
    print(f"  ✅ self_test: {info['satisfied_count']} satisfied, "
          f"{info['not_satisfied_count']} not-satisfied, "
          f"{info['dump_chars']} chars")


def test_o13_ssp_chain_id_deterministic():
    """The SSP chain-id hashes content (not uuid) — reproducible audits."""
    a = assessment_results([_obs_ok(), _obs_bad()], title="t")
    b = assessment_results([_obs_ok(), _obs_bad()], title="t")
    assert a["system-security-plan"]["chain-id"] == b["system-security-plan"]["chain-id"]
    assert len(a["system-security-plan"]["chain-id"]) == 24
    print(f"  ✅ SSP chain-id is 24-char hex, deterministic per identical content")


def test_o14_article_zero_and_counts_props():
    """The results entry carries assessed-entities/passed/article-zero props."""
    doc = assessment_results([_obs_ok(), _obs_bad()], article_zero=True)
    props = {p["name"]: p["value"] for p in doc["results"][0]["props"]}
    assert props["assessed-entities"] == "2"
    assert props["passed"] == "1"
    assert props["article-zero"] == "true"
    # Non-article-zero default
    doc2 = assessment_results([_obs_ok()])
    p2 = {p["name"]: p["value"] for p in doc2["results"][0]["props"]}
    assert p2["article-zero"] == "false"
    print(f"  ✅ props: assessed=2, passed=1, article-zero=true")


def test_o15_export_passes_article_zero():
    """export() propagates article_zero into the JSON."""
    text = export([_obs_ok(), _obs_bad()], article_zero=True)
    doc = json.loads(text)
    props = {p["name"]: p["value"] for p in doc["results"][0]["props"]}
    assert props["article-zero"] == "true"
    print(f"  ✅ export() propagates article-zero flag")


if __name__ == "__main__":
    tests = [
        test_o01_document_shape,
        test_o02_findings_map_to_status,
        test_o03_chain_id_anchored,
        test_o04_fisher_rao_in_props,
        test_o05_observations_have_assessed_controls,
        test_o06_dump_is_valid_json,
        test_o07_export_returns_string,
        test_o08_from_chain_result_duck,
        test_o09_from_chain_result_dict,
        test_o10_missing_distance_raises,
        test_o11_observer_subjects,
        test_o12_self_test,
        test_o13_ssp_chain_id_deterministic,
        test_o14_article_zero_and_counts_props,
        test_o15_export_passes_article_zero,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            import traceback; traceback.print_exc()
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
