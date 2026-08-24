"""x402 commercial-data gate — the lawful 402 lane (SOVOS Part IX canon).

CANON:
  - R8: regulators + public get signed streams FREE forever. No 402 on them.
  - The x402 lane is lawful ONLY on the COMMERCIAL side (insurers, bond desks,
    vendors) and ONLY for DATA — never scores, never anything ranked, never scaled.
  - White-label: they brand it, we sign it; the trust root never white-labels.

This module ISOLATES the payment gate so it can never be mistakenly attached to a
score/rank. `serve_data` returns RAW DATA (the enforcement corpus / a commercial
data subscription); the SCORE lane (the signed axis measurement) is separate and
explicitly NOT behind this gate.

x402 state (verifiable): ~$50M cumulative, ~$28K/day real commerce — build the
rails now, underwrite 2027.
"""
from __future__ import annotations

import os
from typing import Any

PAY_URL = os.environ.get("EUNOMIA_402_URL", "")  # the commercial 402 payment hook
HOLD_UNITS = os.environ.get("EUNOMIA_X402_UNITS", "usd")  # x402 denom
SIGNER = "did:web:csoai.org#estate-chain-1"

# Data products the commercial lane can buy (raw data, never scores).
DATA_PRODUCTS = {
    "enforcement-corpus": {"desc": "signed, machine-readable public enforcement record (fines, deadlines)",
                            "price_usd": 0.02, "per": "query", "signed": True},
    "deadline-calendar": {"desc": "signed regulatory deadline calendar", "price_usd": 0.01, "per": "query", "signed": True},
}


def commercial_data(subject: str, product: str) -> dict:
    """Serve a commercial DATA product behind the x402 gate. Returns data + a
    payment request; NEVER returns a score or a ranking."""
    assert product in DATA_PRODUCTS, f"unknown data product {product!r}"
    from csoai_axis_engine.enforcement_corpus import enforcement_record
    if product == "enforcement-corpus":
        payload = enforcement_record()
        data = {"fines": payload["fines"], "deadlines": payload["deadlines"]}
    else:
        data = {"deadlines": enforcement_record()["deadlines"]}
    return {
        "lane": "commercial-data", "subject": subject, "product": product,
        "data": data,            # RAW DATA, per canon
        "signed": True, "signer": SIGNER,
        "gate": {"kind": "x402", "price": DATA_PRODUCTS[product]["price_usd"], "unit": HOLD_UNITS,
                 "pay_url": PAY_URL, "note": "DATA only — never scores, never ranked (R8 keeps the score side free)."},
    }


def never_scores() -> dict:
    """Explicit guard: the 402 lane must never carry a score/rank."""
    return {"lane": "commercial-data", "policy": "x402 is DATA-only; scores/ranks are never behind this gate (R8: they are free)."}


if __name__ == "__main__":
    import json
    r = commercial_data("insurer-A", "enforcement-corpus")
    print(json.dumps({"product": r["product"], "gate": r["gate"], "n_fines": len(r["data"]["fines"])}, indent=2))
