#!/usr/bin/env python3
"""test_compliance_bridge — eunomia bond router compliance route."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from eunomia_bond_router.compliance_bridge import compliance_route, required_for


def test_uk_route():
    r = compliance_route("UK Gilt", "UK")
    assert any(f["framework"] == "dora" for f in r["route"])
    assert any(f["framework"] == "mifid2" for f in r["route"])
    assert "not_a_certification" in r["compliance"]


def test_eu_route_has_mica():
    r = compliance_route("Tokenised bond", "EU")
    assert any(f["framework"] == "mica" for f in r["route"])
    assert not any(f["framework"] == "dora" for f in r["route"])


def test_all_include_ai_act():
    for j in ("UK", "EU", "US"):
        assert any(f["framework"] == "eu-ai-act" for f in compliance_route("t", j)["route"])


if __name__ == "__main__":
    test_uk_route(); print("ok: uk route")
    test_eu_route_has_mica(); print("ok: eu route has mica")
    test_all_include_ai_act(); print("ok: all include ai act")
    print("ALL COMPLIANCE BRIDGE TESTS PASS")
