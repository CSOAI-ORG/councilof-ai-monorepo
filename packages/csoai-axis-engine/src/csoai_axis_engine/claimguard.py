"""ClaimGuard — the publish gate (SOVOS Part IX grammar law).

The white-label toolkit must never publish absolutist claims. ClaimGuard rejects
statements that would fail the grammar law: we publish "systematic signed coverage
of the public enforcement record" — never "every problem of every AI company",
never "guaranteed", never a certification.

This is the gate every public headline/page/quote must pass before publish.
"""
from __future__ import annotations

import re

# Forbidden absolutist / over-claiming phrasings (ClaimGuard hard-rejects).
FORBIDDEN = [
    r"\bevery problem\b", r"\bevery AI company\b", r"\ball companies\b",
    r"\bguaranteed\b", r"\b100% compliance\b", r"\bfully compliant\b",
    r"\bwill prevent\b", r"\bno risk\b", r"\bperfect\b", r"\bcertified\b",
    r"\bimpossible to fail\b",
]

# Canonical, allowed framing (must be present or the statement is weak).
ALLOWED_FRAMING = [r"systematic signed coverage", r"measurement, not certification",
                   r"not certification", r"signed", r"does not certify"]

# The fixed signer that the gate enforces (trust root never white-labels).
SIGNER_RE = r"did:web:csoai\.org#estate-chain-1"


def guard(statement: str, signed_by: str = "") -> dict:
    """Check a publishable statement against the ClaimGuard grammar law."""
    forbidden = [p for p in FORBIDDEN if re.search(p, statement, re.I)]
    ok_framing = any(re.search(p, statement, re.I) for p in ALLOWED_FRAMING)
    signed = bool(re.search(SIGNER_RE, signed_by)) if signed_by else False
    passed = not forbidden and ok_framing
    # If a signer is provided it MUST be the estate root; else reject.
    if signed_by and not signed:
        return {"pass": False, "reason": "untrusted signer — the trust root never white-labels",
                "forbidden": forbidden, "framing_ok": ok_framing}
    return {"pass": passed, "reason": "PASS" if passed else "ClaimGuard rejected",
            "forbidden": forbidden, "framing_ok": ok_framing, "signed": signed}


# Canonical safe statements (examples that pass).
CANONICAL = [
    "Systematic signed coverage of the public enforcement record. Measurement, not certification.",
    "The signed First-Fine Watch: EU AI Act fines collected to date. Not certification, not an estimate.",
]


if __name__ == "__main__":
    import json
    good = guard(CANONICAL[0], "did:web:csoai.org#estate-chain-1")
    bad = guard("We find every problem for every AI company and guarantee 100% compliance.", "did:web:csoai.org#estate-chain-1")
    print("good:", good["pass"], "| bad:", bad["pass"], "| bad forbidden:", bad["forbidden"])
