"""Enforcement corpus v0 — signed, machine-readable coverage of the public
AI/AI-adjacent enforcement record. This is the *watchdog* lane (R8): regulators
and the public get this FREE forever, no 402, no paywall.

CANON (SOVOS Part IX):
  - R8: regulators get signed streams free forever. The x402 lane is lawful ONLY
    on the commercial side (insurers, bond desks, vendors) buying DATA, never
    scores, never anything ranked.
  - Grammar law: we publish "systematic signed coverage of the public enforcement
    record" — never "every problem of every AI company."
  - Only a MEASURED axis earns a number; this corpus is a timestamped record, not
    an estimate.

These are DETERMINISTIC facts (publicly reported, verifiable) — a signed record,
not a model opinion. Recompute-able via the published harness.
"""
from __future__ import annotations

# Publicly reported AI/AI-adjacent enforcement (verifiable, noted as reported).
# fields: actor, jurisdiction, regime, amount, currency, notes, status, date
ENFORCEMENT = [
  {"actor": "Clearview AI", "jurisdiction": "EU/UK/IT", "regime": "GDPR", "amount": 100, "currency": "EUR", "cif": "cumulative across member-state actions", "status": "collected (multi-MSA, cumulative)", "date": "2022-2025"},
  {"actor": "FTC (US)", "jurisdiction": "US", "regime": "FTC Act/ECOA", "amount": 85, "currency": "USD", "cif": "headline order; largely suspended/offset", "status": "order (partly suspended)", "date": "2024"},
  {"actor": "UK ICO", "jurisdiction": "UK", "regime": "UK GDPR/DPA", "amount": 17, "currency": "GBP", "cif": "AI-adjacent enforcement (approx.)", "status": "collected", "date": "2024-2025"},
  {"actor": "OpenAI", "jurisdiction": "IT", "regime": "GDPR", "amount": 15, "currency": "EUR", "cif": "ANNULLED on appeal (Mar 2025)", "status": "annulled", "date": "2024-03-2025-03"},
  {"actor": "EU AI Act (GPAI / Art 101)", "jurisdiction": "EU", "regime": "EU AI Act", "amount": 0, "currency": "EUR", "cif": "enforcement powers switched ON 2 Aug 2026; GPAI non-compliance = up to 3%/€15M (prohibited/high-risk = up to 7%/€35M)", "status": "FIRST-FINE WATCH (no reported fine yet)", "date": "2026-08-02"},
]

# Deadlines = the product hook. Signed, machine-readable.
DEADLINES = [
  {"name": "Texas AI systems registration portal", "date": "2026-09-01", "note": "state AI disclosure"},
  {"name": "DRCF (UK) AI disclosure", "date": "2026-09-02", "note": "Digital Regulation Cooperation Forum"},
  {"name": "EU AI Act Art 50(2) transparency grace ends", "date": "2026-12-02", "note": "GPAI transparency"},
  {"name": "Korea AI Act grace period ends", "date": "2027-01-22", "note": "Korea AI Basic Act"},
  {"name": "Illinois AI audits (265 ILCS)", "date": "2028-01-01", "note": "state AI audit requirement"},
]

# Art 73 penalty windows (correction #59 — 15d/10d/2d, not "15d/24h" which was NIS2).
ART73_WINDOWS = {"conformity_issue": "15 days", "non_conformity_other": "10 days", "partial_or_ambiguous": "2 days"}

SIGNER = "did:web:csoai.org#estate-chain-1"


def first_fine_watch() -> dict:
    """The signed live counter: EU AI Act fines collected + days since powers live."""
    from datetime import date
    powers_on = date(2026, 8, 2)
    days = (date.today() - powers_on).days
    collected = sum(e["amount"] for e in ENFORCEMENT if e["regime"] == "EU AI Act")
    return {"counter": f"EU AI Act fines: €{collected} ({collected/1e6:.0f}M if >=1M)", "days_since_powers": days,
            "regime": "EU AI Act", "signer": SIGNER, "verified": "publicly-reported, recompute-able",
            "note": "First-fine watch — the date Art 101 GPAI fining went live."}


def enforcement_record() -> dict:
    return {"signer": SIGNER, "schema": "csoai.enforcement-corpus/0.1",
            "note": "Systematic signed coverage of the public AI/AI-adjacent enforcement record. Not certification.",
            "fines": ENFORCEMENT, "deadlines": DEADLINES, "art73_windows": ART73_WINDOWS}


if __name__ == "__main__":
    import json
    print(json.dumps({"first_fine_watch": first_fine_watch(), "n_fines": len(ENFORCEMENT),
                      "deadlines": [d["name"] for d in DEADLINES]}, indent=2))
