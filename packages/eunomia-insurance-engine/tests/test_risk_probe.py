#!/usr/bin/env python3
"""test_risk_probe — eunomia insurance engine."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from eunomia_insurance_engine.risk_probe import probe, recommend, underwrite


def test_clean_insures():
    r = underwrite("Retail mortgage, human consumer, GDPR data, low default risk, solvent")
    assert r["recommendation"] in ("insure", "flag"), r
    assert "care" in r["scores"]


def test_risk_without_care_declines():
    # genuinely care-negative risky scenario (no "human/retail/patient" care words)
    r = underwrite("Fraudulent claim, default exposure, high risk concentration, opaque model, no safeguard")
    assert r["recommendation"] == "decline"


def test_care_hit_flags_appetite():
    r = underwrite("Human retail insured, KYC/AML, non-discriminatory, flood risk concentration")
    assert r["recommendation"] == "flag", r


if __name__ == "__main__":
    test_clean_insures(); print("ok: clean insures")
    test_risk_without_care_declines(); print("ok: risk w/o care declines")
    test_care_hit_flags_appetite(); print("ok: care hit flags")
    print("ALL INSURANCE ENGINE TESTS PASS")
