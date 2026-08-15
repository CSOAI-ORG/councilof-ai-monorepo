"""HMAC-SHA256 signing for agent responses.

Every agent response gets a signature so other agents (and humans) can
verify the response wasn't tampered with in transit.

This is a stripped-down version of the SOV3 sigil pattern:
- HMAC-SHA256 with a shared secret (in production: per-agent Ed25519 key)
- Signature included in every response as `_sig`
- Verify by recomputing the HMAC over the canonical JSON of all other fields

For demo purposes, all three agents share the same secret. In production
each agent would have its own keypair.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict


# Shared demo secret — REPLACE in production
DEMO_SECRET = b"sovos-a2a-demo-2026-do-not-use-in-prod"


def canonical_json(payload: Dict[str, Any]) -> bytes:
    """Canonical JSON: sort keys, no whitespace, UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_response(payload: Dict[str, Any], secret: bytes = DEMO_SECRET) -> str:
    """Compute the HMAC-SHA256 signature for a response payload.

    The signature covers every field EXCEPT `_sig` itself.
    Returns hex digest (64 chars).
    """
    # Strip _sig if present (so we can sign existing responses)
    to_sign = {k: v for k, v in payload.items() if k != "_sig"}
    msg = canonical_json(to_sign)
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    return sig


def attach_signature(payload: Dict[str, Any], secret: bytes = DEMO_SECRET) -> Dict[str, Any]:
    """Return a new payload with `_sig` set."""
    signed = dict(payload)
    signed["_sig"] = sign_response(payload, secret)
    return signed


def verify_response(payload: Dict[str, Any], secret: bytes = DEMO_SECRET) -> bool:
    """Verify that the `_sig` in a response is valid."""
    if "_sig" not in payload:
        return False
    given_sig = payload["_sig"]
    expected_sig = sign_response(payload, secret)
    # Constant-time comparison
    return hmac.compare_digest(given_sig, expected_sig)


# ── PRODUCTION SIGNER (Wire 5, 2026-08-14) ──────────────────────────────────
# The estate's A2A surface now signs with REAL asymmetric Ed25519 through the
# COSE wrapper — the same spine as the signed cards. HMAC above is the LEGACY
# demo path (shared secret = verifiable by anyone holding the secret = not a
# real signature). Production callers use sign_cose/verify_cose.

def sign_cose(payload: Dict[str, Any], source: str = "a2a-agent") -> Dict[str, Any]:
    """Wrap a payload in a csoai-cose-sign1 Ed25519 envelope (real signature)."""
    try:
        from sovos_city.cose_wrapper import wrap
        r = wrap(payload, source=source)
        if r.signed:
            import json
            return {
                "envelope": json.loads(r.envelope),
                "_signer_kind": "ed25519-cose",
                "_content_id": r.content_id,
            }
    except Exception:
        pass
    # honest fallback: keep the legacy HMAC path, labelled as such
    out = attach_signature(payload)
    out["_signer_kind"] = "hmac-demo-legacy"
    return out


def verify_cose(envelope: Dict[str, Any]) -> bool:
    """Verify a csoai-cose-sign1 envelope (no secret needed)."""
    try:
        from sovos_city.cose_wrapper import verify
        return bool(verify(envelope).get("valid"))
    except Exception:
        return False


__all__ = ["sign_response", "attach_signature", "verify_response", "DEMO_SECRET",
           "canonical_json", "sign_cose", "verify_cose"]
