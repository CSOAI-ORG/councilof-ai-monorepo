#!/usr/bin/env python3
"""atomic_settlement — atomic delivery-vs-payment (DvP) for the bond router (Open 2).

The cash leg (SWIFT/COBOL, T+2) is the bottleneck. Tokenized bonds settle in seconds,
but cash still moves through legacy rails. This module executes the ESCROW:
LOCK bond token (buyer) + LOCK cash token (seller) -> VERIFY both -> RELEASE both
OR neither. All-or-nothing. Then sign the outcome (Ed25519) via attest.attest so an
A2A agent / regulator can verify the settlement offline.

The module is deterministic, offline, and purely the smart-contract logic. The
on-chain twin (AtomicDvP.sol) mirrors the same LOCK/VERIFY/RELEASE/OR-NEITHER.
Measurement, not certification.
"""
import json

MODES = ("settle", "not-settle", "escrow", "dispute")


def _leg(value):
    """Normalise a leg dict: {quantity|amount, currency, owner}."""
    return {
        "quantity": float((value or {}).get("quantity", value.get("amount", 0)) if value else 0),
        "currency": str((value or {}).get("currency", "")).upper(),
        "owner": str((value or {}).get("owner", "")),
    }


def escrow(bond_leg, cash_leg):
    """Lock both legs in the contract. Returns the escrow state (deterministic)."""
    return {
        "bond": _leg(bond_leg),
        "cash": _leg(cash_leg),
        "locked": bool(bond_leg and cash_leg),
    }


def verify(esc, compliance=None):
    """Verify both legs + an optional compliance gate. All gate conditions must hold."""
    bond_ok = esc["bond"]["quantity"] > 0
    cash_ok = esc["cash"]["quantity"] > 0
    same_ccy = not esc["bond"]["currency"] or not esc["cash"]["currency"] or esc["bond"]["currency"] == esc["cash"]["currency"]
    compliance_ok = compliance is not False  # default pass; a False blocks
    return {"bond_ok": bond_ok, "cash_ok": cash_ok, "currency_ok": same_ccy, "compliance_ok": compliance_ok,
            "all_ok": bool(bond_ok and cash_ok and same_ccy and compliance_ok)}


def finalize(esc, verified):
    """All-or-nothing: both release only if all_ok; otherwise both refund (atomic)."""
    if verified["all_ok"]:
        return {"status": "settled", "released": {"bond": "buyer", "cash": "seller"}, "reason": "atomic DvP complete"}
    return {"status": "not-settled", "released": "none", "reason": {k: v for k, v in verified.items() if not v}}


def settle(execution, compliance=None):
    """Run the full atomic DvP over one execution dict -> {status, escrow, verified, outcome}."""
    execd = execution or {}
    esc = escrow(execd.get("bond"), execd.get("cash"))
    verified = verify(esc, compliance)
    outcome = finalize(esc, verified)
    return {"escrow": esc, "verified": verified, "outcome": outcome}


def settle_attested(execution, key_path, compliance=None, signer="did:web:csoai.org#estate-chain-1"):
    """Atomic DvP + Ed25519 attestation (Proof-of-Weave). Reuses eunomia_bond_router.attest."""
    from .attest import attest
    result = settle(execution, compliance)
    card = attest({
        "schema": "csoai.atomic-dvp/0.1",
        "record_type": "measured-current-state",
        "not_a_certification": True,
        "execution": execution,
        "settlement": result["outcome"],
        "verified": result["verified"],
    }, key_path, signer)
    return {**result, "card": card}


if __name__ == "__main__":
    demo = {
        "bond": {"quantity": 1000000, "currency": "USD", "owner": "buyer"},
        "cash": {"quantity": 1025000, "currency": "USD", "owner": "seller"},
    }
    r = settle(demo)
    print("ATOMIC DVP:", json.dumps(r, indent=2))
    print("ALL_OR_NOTHING:", r["verified"]["all_ok"], "->", r["outcome"]["status"])
