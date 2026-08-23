#!/usr/bin/env python3
"""risk_probe — eunomia insurance engine (care-membrane-inspired underwriting probe).

Banks want to lend; insurers want to avoid risk. The friction between them is the
pricing signal. This module runs a deterministic ethics + risk probe over a policy
or risk description (care-membrane style, no LLM) and returns an underwriting
recommendation + a signed, quoteable risk attestation.

Measurement, not certification. Deterministic, offline.
"""
import re

AXES = {
    "care":   re.compile(r"human|wellbeing|dignity|vulnerab|consumer|patient|retail|care", re.I),
    "risk":   re.compile(r"fraud|claim|default|exposure|catastroph|concentration|disaster", re.I),
    "privacy":re.compile(r"personal|data|gdpr|consent|biometric|health record", re.I),
    "fairness":re.compile(r"non-discrim|bias|equal|protected|disparate|small|low-income", re.I),
    "viability":re.compile(r"solvenc|capital|reserve|reinsur|underwrit|cash|balance", re.I),
}


def probe(text):
    """Score a risk/policy description on the care-membrane axes (0..1 each)."""
    t = str(text or "").lower()
    out = {}
    for ax, rex in AXES.items():
        hits = rex.findall(t)
        out[ax] = {"hits": len(hits), "score": 1.0 if hits else 0.0}
    return out


def recommend(scores, coverage_threshold=0.5):
    """Underwriting recommendation from axis scores.

    0 axes hit -> 'insure' (clean); some risk+violates care -> 'flag'; severe -> 'decline'.
    Deterministic rule: any risk == True and care == False gets 'flag';
    care == False and risk scored high -> 'decline'.
    """
    risk = scores["risk"]["score"] >= 1.0
    care = scores["care"]["score"] >= 1.0
    privacy = scores["privacy"]["score"] >= 1.0
    if not risk and not privacy:
        return "insure"
    if risk and not care:
        return "decline"
    if care and (risk or privacy):
        return "flag"
    return "insure"


def underwrite(text, premium=None):
    """Full probe -> recommendation, deterministic and quoteable."""
    scores = probe(text)
    rec = recommend(scores)
    return {
        "recommendation": rec,
        "premium": premium,
        "scores": scores,
        "framing": "care-membrane ethics probe · measurement, not certification",
    }


if __name__ == "__main__":
    r = underwrite("Retail mortgage policy, non-discriminatory, human consumer, GDPR data handled, low default risk, solvent lender")
    import json
    print("UNDERWRITE:", json.dumps(r, indent=2))
