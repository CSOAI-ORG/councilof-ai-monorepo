"""Regression test for the negation-aware claim.certification rule (validate_negation).

The shipped `CSOAI-ORG/claimguard` gate once rejected the estate's own canonical
doctrine phrasing — "Measurement, not certification." / "Never certifies." —
because the CLAIM_RULES regex `\bcertif(y|ied|ication)\b` matched the word even
inside a negation. This test locks in the corrected behaviour:

  * NEGATED doctrine phrasing  -> claim.certification must NOT fail (PASS)
  * AFFIRMATIVE certification -> claim.certification must FAIL

Run: python3 test_negation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import claimguard


def _verdict(findings) -> str:
    f = [x for x in findings if x.code == "claim.certification"]
    if not f:
        return "PASS"
    return f[0].status.name


def main() -> int:
    board = {
        "totals": {"axes": 14, "measured_axes": 13, "quotable_axes": 14},
        "axes": [{"axis": "jail", "separation": "UNTESTED"}],
    }
    cases = [
        # Negated doctrine framing — MUST pass.
        ("Measurement, not certification.", "PASS"),
        ("Never certifies. Measurement ≠ certification. Determination stays with authorities.", "PASS"),
        ("We measure and sign; we never certify.", "PASS"),
        ("Certification is not provided.", "PASS"),
        ("Does not certify; the regulator decides.", "PASS"),
        ("Reference index; measurement, not certification.", "PASS"),
        ("This system does not certify and never claims certification.", "PASS"),
        ("No certificate of compliance is issued by us.", "PASS"),
        # Affirmative certification — MUST fail.
        ("We certify that this system is compliant.", "FAIL"),
        ("Certified by the Council of AI.", "FAIL"),
        ("This is a certification, not a measurement.", "FAIL"),
        ("We are a certified notified body.", "FAIL"),
        ("The verdict is the certificate of compliance.", "FAIL"),
        ("This ruling certifies the model.", "FAIL"),
    ]
    bad = 0
    for text, expect in cases:
        got = _verdict(claimguard.check_claims(board, [text]))
        ok = got == expect
        if not ok:
            bad += 1
        print(f"{'OK ' if ok else '!! '}[{got:4s}] expect {expect:4s} | {text}")
    print(f"\n{'ALL PASS' if bad == 0 else f'{bad} MISMATCH'} ({len(cases)} cases)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
