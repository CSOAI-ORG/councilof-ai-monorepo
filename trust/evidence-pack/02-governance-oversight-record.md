# Governance & Oversight Record — CSOAI / Council of AI (EUNOMIA)

*Evidence pack doc 2 of 4. Measurement, not certification.*

## Ownership
CSOAI Ltd (UK, Companies House #16939677). The measurement body is independent:
it does not sell scores, never takes money for anything ranked, and has no
vendor affiliation on the measured models.

## Oversight structure
- **Measurement doctrine** (binding): the UI never interprets; it renders what the
  predicate did. Only a MEASURED axis earns a number; a status that cannot be
  checked cannot say LIVE (JL.5).
- **Referential integrity**: the trust root is `did:web:csoai.org#estate-chain-1`
  (stranger-resolvable); keys never leave the signing pod (GX.2); a stranger can
  recompute any card from the published frozen bank + harness.
- **Oversight of the measurement itself**: ClaimGuard gates every public claim
  (claim-vs-signed-artifact); a publish gate rejects absolutist over-claiming and
  certifying language; ops/banned-strings rejects codenames on public surfaces.

## Escalation
Determination stays with authorities. We measure behaviour; authorities determine
violation (JI.4). Fundamental-rights impact + human oversight are stated as
boundaries, never as autonomously-decided outcomes.

## Signing
Cards are Ed25519-signed (`did:web:csoai.org#estate-chain-1`). The signer never
white-labels; the trust root is fixed. Internal codenames never appear publicly.
