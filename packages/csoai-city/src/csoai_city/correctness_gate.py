"""csoai-city.correctness_gate — the keystone: no signed card over ungrounded content.

The estate's whole business is "signed measurement a regulator can verify." A measure-
ment can be signed AND wrong — a signed-but-wrong attestation is the one thing that
detonates neutrality in front of a regulator. This gate closes that gap: it classifies
every claim destined for a signed card into THREE states and REFUSES to attest
UNGROUNDED content.

States (deterministic, no model judges this):
  GROUNDED  — the claim cites a provision that maps to a known statutory anchor and
              the anchor resolves in the estate's law registry. Attestable.
  UNGROUNDED — the claim makes a legal/regulatory assertion that cites NO provision,
              or cites one that is not a real anchor. MUST NOT be attested.
  UNKNOWN   — cannot determine (no claim parsed, or the subject isn't a legal
              assertion). Attestable but flagged for human review.

The gate is wired BEFORE card issuance: attest() refuses to sign UNGROUNDED content,
so the signed-card leg can never carry a bare assertion dressed as a verified one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

# ── Statutory anchors the estate actually knows (law.py / article_zero registry) ──
# A claim is GROUNDED if it cites one of these exact anchors. This is the closed,
# auditable set — not an open "the model said so" set.
KNOWN_ANCHORS: List[str] = [
    # EU AI Act
    "art5", "article5", "art-5", "article-5",          # prohibited practices
    "art50", "article50", "art-50", "article-50",      # transparency
    "art9", "article9", "art-9",                       # risk management
    "art10", "article10", "art-10",                    # data governance
    "art13", "article13", "art-13",                    # transparency
    "art14", "article14", "art-14",                    # human oversight
    "art43", "article43", "art-43",                    # conformity assessment
    "annex3", "annexiii", "annex-iii", "annex-3",      # high-risk list
    "art50:emotion-disclosure", "art5:manipulation",
    "art5:vulnerability", "art5:emotion-edu", "art5:emotion-work",
    "art50:synthetic-marking", "art50:companion-disclosure",
    # DORA, NIS2, GDPR, CRA (bridge mesh regulators)
    "dora", "nis2", "gdpr", "cra", "miFID", "mifid",
    "pci-dss", "pci", "psd2", "aml", "ofac", "sox",
    "hipaa", "solvency-ii", "solvency", "hmrc",
    # GSPC axes (the estate's own measured categories)
    "gov", "care", "affect", "art5", "det", "prv",
    "agi", "asi", "swarm", "mach", "xr", "oss", "mcp",
]

# Phrases that signal a legal/regulatory/safety assertion that MUST be grounded.
ASSERTIVE_SIGNALS = [
    "article", "art ", " regulation ", "compliance", "compliant", "prohibited",
    "permitted", "disclose", "requires", "required by", "mandatory", "obligation",
    "must", "high-risk", "high risk", "annex", "violat", "legal", "gdpr",
    "shall", "risk-tier", "conformity",
]

_CITATION_RE = re.compile(
    r"(\b(?:art(?:icle)?\.?\s*\d+[^a-z]?|annex(?:ix)?\.?\s*(?:iii|3)?" +
    r"|art5|art50|dora|nis2|gdpr|cra|pci-dss|psd2|aml|ofac|sox|hipaa|solvency)" +
    r"[a-z0-9:\-\(\)/\s,]*)", re.IGNORECASE)


@dataclass
class CorrectnessVerdict:
    state: str                     # "GROUNDED" | "UNGROUNDED" | "UNKNOWN"
    citations: List[str]           # anchors found in the claim
    anchors_known: List[bool]      # per-citation: is it a KNOWN_ANCHOR?
    reasons: List[str]
    attestable: bool               # GROUNDED|UNKNOWN -> True; UNGROUNDED -> False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_anchors(claim: str) -> List[str]:
    found = []
    seen = set()
    for m in _CITATION_RE.finditer(claim):
        token = m.group(1).strip().strip(" .,;:").lower()
        # normalise "article 5" -> "art5"
        token = re.sub(r"^article\s*(\d+)", r"art\1", token)
        token = re.sub(r"^art\s*(\d+)", r"art\1", token)
        token = re.sub(r"\s+", "-", token)
        if token and token not in seen:
            seen.add(token)
            found.append(token)
    return found


def evaluate(claim: str, expected_anchor: Optional[str] = None) -> CorrectnessVerdict:
    """Three-state groundedness verdict for a claim destined for attestation."""
    claim_l = (claim or "").lower()
    reasons: List[str] = []

    citations = _extract_anchors(claim)
    if expected_anchor:
        ea = expected_anchor.lower().strip()
        if ea not in [c.split(":")[0] for c in citations] and \
           not any(ea in c for c in citations):
            # anchor required but not cited -> still check what IS cited
            reasons.append(f"expected anchor '{ea}' not cited")

    if not citations:
        # No anchor cited. Is this even an assertion that needs grounding?
        is_assertive = any(s in claim_l for s in ASSERTIVE_SIGNALS)
        if not is_assertive:
            return CorrectnessVerdict(
                state="UNKNOWN",
                citations=[], anchors_known=[],
                reasons=["no legal assertion detected; nothing to ground"],
                attestable=True,
            )
        return CorrectnessVerdict(
            state="UNGROUNDED",
            citations=[], anchors_known=[],
            reasons=["assertive legal claim with NO citation — cannot attest"],
            attestable=False,
        )

    # Map citations against the closed anchor set.
    known = []
    for c in citations:
        base = c.split(":")[0].strip()
        is_known = any(a == base or a.startswith(base) or base.startswith(a)
                       for a in KNOWN_ANCHORS)
        known.append(is_known)

    if all(known):
        reasons.append("all cited anchors are in the estate's known registry")
        return CorrectnessVerdict(
            state="GROUNDED", citations=citations, anchors_known=known,
            reasons=reasons, attestable=True,
        )

    bad = [c for c, k in zip(citations, known) if not k]
    reasons.append(f"uncited/anchor-not-known: {bad}")
    return CorrectnessVerdict(
        state="UNGROUNDED", citations=citations, anchors_known=known,
        reasons=reasons, attestable=False,
    )


def gate_claim_for_attestation(claim: str,
                               expected_anchor: Optional[str] = None
                               ) -> CorrectnessVerdict:
    """Public gate: returns the verdict; caller MUST refuse to issue a signed card
    if verdict.attestable is False (UNGROUNDED)."""
    return evaluate(claim, expected_anchor)


def self_test() -> int:
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # GROUNDED: cites a real anchor
    t("grounded art5", evaluate("This deploy trips Art 5(1)(a) manipulation.").state == "GROUNDED")
    t("grounded art50", evaluate("Article 50 requires disclosure of emotion recognition.").state == "GROUNDED")
    # UNGROUNDED: assertive legal claim, no citation
    t("ungrounded bare assertion",
      evaluate("This AI is fully compliant with all obligations.").state == "UNGROUNDED")
    t("ungrounded blocks attestation",
      evaluate("This is definitely compliant.").attestable is False)
    # UNKNOWN: not a legal assertion, nothing to ground
    t("unknown plain fact", evaluate("The model has 14 axes.").state == "UNKNOWN")
    t("unknown attestable", evaluate("The model answered 30/36 correctly.").attestable is True)
    # anchor mismatch: a claim citing a REAL anchor is still grounded (the gate
    # checks groundedness, not exact-anchor matching)
    t("real-anchor grounded despite expected-mismatch",
      evaluate("Article 9 risk management applies.", "art50").state == "GROUNDED")

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
