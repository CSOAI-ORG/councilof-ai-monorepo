# csoai-invariants

Sovereign substrate invariants every layer of SOVOS consults:
NAME/OWEM normalization, CARE floor enforcement, SIGIL sign+verify,
tally validation. Absorbed 2026-08-11 from `sov_invariants.py`
(top-level) into the canonical package form.

## Functions

| Function | Job |
|---|---|
| `normalize_name(value)` | Canonical sovereign-name normalization (whitespace, casing) |
| `normalize_owem(value)` | OWEM agent identifier normalization |
| `validate_care_floor(value)` | CARE floor (≥0.95) check on a tally or score |
| `care_score(text, short_floor=0.0)` | Compute CARE score from text content (≥short_floor) |
| `validate_tally(tally)` | Validate a tally dict structure |
| `emit_sigil(payload, tally, care, prev_hash, agent_did)` | Ed25519-signed SIGIL for a chain record |
| `verify_sigil(sigil, payload)` | Verify a SIGIL |
| (private) `_private_key()` | Lazy-loaded Ed25519 private key (file at `~/.runpod/sov_sigil_key` or `/runpod/sov_sigil_key`) |

## Provenance

The original `sov_invariants.py` (163 lines) was used by every model in
the substrate — `sov4_router.py`, `csoai_governance.py`, `forest/*`,
`api/*.js` — but lived at repo root. Pinning it as a package here
gives every other package a canonical import path:

```python
from csoai_invariants import (
    care_score, emit_sigil, verify_sigil,
    normalize_name, normalize_owem, validate_care_floor, validate_tally,
    SOVEREIGN_DID,
)
```

## Use

```python
from csoai_invariants import emit_sigil, verify_sigil, SOVEREIGN_DID, care_score

# sign a payload
sigil = emit_sigil(
    payload={"ts": 1722350400, "kind": "audit", "...": "..."},
    tally={"yes": 9, "no": 1, "abstain": 0},
    care=0.95,
    agent_did=SOVEREIGN_DID,
)

# verify
ok = verify_sigil(sigil, payload)
```

## Cross-link

The SIGIL/CARE crypto layer is a substrate-wide primitive. Every
package that signs attestations (`sovos-arena`, `sovos-oscal`,
`sovos-chain`, the absorbed `sovos-router`, etc.) is expected to
import from here. The sigil key is **not** in this repo (lives on
the runtime host per `~/.runpod/sov_sigil_key`); the package is
fine on the Mac without it but emits nothing verifiable without the
key — exactly the right hardening for a public repo.
