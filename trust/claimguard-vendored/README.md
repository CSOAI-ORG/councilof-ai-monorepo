# ClaimGuard — vendored fixed copy (negation-aware certification rule)

Vendored from the shipped `CSOAI-ORG/claimguard` repo. This copy fixes a genuine
defect found 2026-08-25:

**Bug.** The `claim.certification` rule matched the regex `\bcertif(y|ied|ication)\b`
even when the word was negated. It therefore REJECTED the estate's own canonical
doctrine phrasing:
- "Measurement, not certification."
- "Never certifies. Measurement ≠ certification."
- "Certification is not provided."

That is a false positive against the doctrine the whole estate is built on
(measurement, NOT certification). It also made the earlier register claim
"evidence-pack ClaimGuard ALL-PASS" false when measured against the SHIPPED gate
(the local axis-engine publish-gate, which enforces `ALLOWED_FRAMING`, was always
correct — this bug was only in the standalone audit gate).

**Fix.** `_certif_negated(text)` now returns True only when every `certif*`
occurrence is negated (threshold: before/after token window + `≠` + copula-negator
forms). `claim.certification` fires only on *affirmative* certification
("we certify", "certified by", "the certificate of compliance").

**Validation (raw base, + 14-case matrix):** self-test PASS (now also asserts
negated doctrine does NOT trip claim.certification and affirmative DOES), live
board `check --live` PASS (13 measured of 14, site_attestation valid), repo test
exit 0, py_compile OK, 14/14 negation cases correct.

**Files**
- `claimguard.py`  — fixed gate (self-test + `check` CLI)
- `canonical.py`   — RFC 8785 canonicalisation dependency
- `test_negation.py` — regression test locking the negation-aware behaviour
- `LICENSE`        — original MIT

**Commit provenance:** `fix/certif-negation` @ e1f59cc (in the cloned repo;
NOT pushed to public origin — push is owner-gated "lanes propose, Nick disposes").

Run: `python3 claimguard.py --self-test` then `python3 test_negation.py`.
