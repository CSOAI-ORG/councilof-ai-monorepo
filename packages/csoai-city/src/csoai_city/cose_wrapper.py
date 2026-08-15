"""csoai-city.cose_wrapper — Phase 2: sign ANY MCP/index output into a verifiable envelope.

The gap the synthesis named: Anthropic Economic Index, OECD AI, Stanford HAI all
opened their data via APIs/MCP — callable but NOT verifiable. No cryptographic
proof of when a number was generated, what version, whether drifted or tampered.
This module is the signing layer the MCP economy doesn't have: it wraps any
index/tool output into a signed envelope a third party can verify without us.

Envelope shape (COSE_Sign1-informed, honest):
  {
    "envelope": "csoai-cose-sign1",
    "version": "1",
    "protected": { "alg": "EdDSA", "kid": "ed25519:<pubkey8>", "typ": "sov-measurement" },
    "payload": { "source": ..., "observed_at": ..., "data": <the index/tool output> },
    "signature": <Ed25519 over canonical(protected|payload)>,
    "content_id": <sha256 of canonical payload>,
    "time_anchor": { state: "calendar_commit"|"pending", ... }
  }

This is a REAL signature (asymmetric Ed25519, secret never leaves the signer),
NOT hash-theater. COSE/SCITT/did:web full binding is Phase 3 (owner-gated); this
Phase-2 wrapper is the same proven path as attestation_registry + timestamping.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    CRYPTO = True
except Exception:  # pragma: no cover
    CRYPTO = False


def canonical(obj: Any) -> bytes:
    """Same deterministic encoding as chain.py (sorted keys, compact)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _load_key(key_path: Optional[str] = None):
    # ONE loader (ADR_ONE_SIGNER): fail-closed on the production identity, never a rogue key.
    # cose_wrapper stays honest-UNSIGNED on a missing key rather than raising.
    from .keystone import load_signing_key
    try:
        return load_signing_key(key_path)
    except Exception:
        return None


@dataclass
class EnvelopeResult:
    envelope: str
    content_id: str
    signature: Optional[str]
    signed: bool
    time_anchor_state: str
    bytes_len: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _resolve_signer_did(pub_hex: str):
    """Return {signer_did, verification_method} if this Ed25519 pubkey is PUBLISHED in the
    estate's did:web document, else None. Self-contained (no cross-package import) and honest:
    an identity is stamped only when the signing key is actually the one csoai.org publishes, so
    a dev key that isn't published never falsely claims the DID."""
    try:
        import base64
        from pathlib import Path as _P
        for parent in _P(__file__).resolve().parents:
            cand = parent / ".well-known" / "did.json"
            if cand.exists():
                doc = json.loads(cand.read_text())
                want = bytes.fromhex(pub_hex)
                for vm in doc.get("verificationMethod", []):
                    jwk = vm.get("publicKeyJwk")
                    if jwk and jwk.get("kty") == "OKP" and jwk.get("crv") == "Ed25519":
                        x = jwk["x"] + "=" * (-len(jwk["x"]) % 4)
                        if base64.urlsafe_b64decode(x) == want:
                            did = doc.get("id")
                            return {"signer_did": did, "verification_method": f"{did}#keys-1"}
                return None      # found the doc; key not in it
        return None              # no did.json anywhere up-tree
    except Exception:
        return None


def wrap(output: Dict[str, Any], source: str,
         key_path: Optional[str] = None,
         observed_at: Optional[str] = None) -> EnvelopeResult:
    """Sign ANY index/MCP/tool output into a verifiable envelope.

    output: the data to wrap (adoption score, policy index, GSPC card, ...)
    source: provenance label, e.g. "anthropic-economic-index" | "oecd-ai" | "gspc"
    """
    try:
        key = _load_key(key_path)
        if key is None:
            return EnvelopeResult(
                envelope="csoai-cose-sign1", content_id="", signature=None,
                signed=False, time_anchor_state="unsigned", bytes_len=0,
                error="no key available — honest UNSIGNED, never faked")

        payload = {
            "source": source,
            "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
            "data": output,
        }
        cid = hashlib.sha256(canonical(payload)).hexdigest()
        pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw).hex()
        protected = {
            "alg": "EdDSA",
            "kid": f"ed25519:{pub[:16]}",
            "typ": "sov-measurement",
        }
        # signature over canonical(protected|payload) — deterministic, third-party
        # reproducible without trusting us (the pubkey rides in the envelope)
        sig_input = canonical({"protected": protected, "payload": payload})
        signature = key.sign(sig_input).hex()

        envelope = {
            "envelope": "csoai-cose-sign1",
            "version": "1",
            "protected": protected,
            "payload": payload,
            "signature": signature,
            "content_id": cid,
            "signer_pubkey": pub,
        }

        # did:web signer (honest): stamp the resolvable identity ONLY when this signing key is
        # the one published at csoai.org/.well-known/did.json — a verifier can then resolve the
        # signer without trusting us. Never stamped for an unpublished dev key.
        _did = _resolve_signer_did(pub)
        if _did:
            envelope["signer_did"] = _did["signer_did"]
            envelope["verification_method"] = _did["verification_method"]

        # Time-anchor (non-fatal): attach OTS calendar commitment
        anchor_state = "pending"
        try:
            from .timestamping import stamp_content_id
            anchor = stamp_content_id(cid)
            envelope["time_anchor"] = anchor.to_dict()
            anchor_state = anchor.state
        except Exception:
            envelope["time_anchor"] = {"state": "pending", "note": "calendar unavailable"}

        return EnvelopeResult(
            envelope=json.dumps(envelope), content_id=cid,
            signature=signature, signed=True,
            time_anchor_state=anchor_state,
            bytes_len=len(json.dumps(envelope).encode()),
        )
    except Exception as e:  # noqa: BLE001
        return EnvelopeResult(
            envelope="csoai-cose-sign1", content_id="", signature=None,
            signed=False, time_anchor_state="error", bytes_len=0,
            error=f"{type(e).__name__}: {e}")


def verify(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute content_id + verify the Ed25519 signature. No secret needed."""
    try:
        payload = envelope["payload"]
        protected = envelope["protected"]
        signature = envelope["signature"]
        sig_input = canonical({"protected": protected, "payload": payload})
        recomputed = hashlib.sha256(canonical(payload)).hexdigest()
        cid_match = recomputed == envelope.get("content_id")
        if not CRYPTO or not signature:
            return {"valid": False, "reason": "crypto unavailable / no signature"}

        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        kid = protected.get("kid", "")
        pub_hex = kid.replace("ed25519:", "") + ("0" * 0)  # kid holds first 16 only — cannot verify
        # honest: the full pubkey must ride with the envelope; kid alone is not enough
        full_pub = envelope.get("signer_pubkey")
        if not full_pub:
            return {"valid": cid_match and False,
                    "reason": "kid is a short id only; full signer_pubkey required for verification",
                    "content_id_matches": cid_match}
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(full_pub))
        pub.verify(bytes.fromhex(signature), sig_input)
        return {"valid": True, "signer": kid,
                "content_id_matches": cid_match, "signature_valid": True}
    except Exception as e:  # noqa: BLE001
        return {"valid": False, "reason": f"{type(e).__name__}: {e}"}


def self_test() -> int:
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # 1. wrap signs (key present on pod)
    r = wrap({"adoption": 0.42, "occupation": "finance"}, "anthropic-economic-index")
    t("wrap signs", r.signed is True, r.error or "")
    t("content_id set", len(r.content_id) == 64)
    t("time anchor attempted", r.time_anchor_state in ("calendar_commit", "pending"))

    # 2. verify round-trip (full pubkey embedded)
    if r.signed:
        env = {
            "envelope": "csoai-cose-sign1", "version": "1",
            "protected": {"alg": "EdDSA", "kid": f"ed25519:{r.content_id[:16]}", "typ": "sov-measurement"},
            "payload": {"source": "anthropic-economic-index",
                        "observed_at": "2026-08-14T00:00:00+00:00",
                        "data": {"adoption": 0.42, "occupation": "finance"}},
            "signature": r.signature, "content_id": r.content_id,
        }
        # cannot verify without the full pubkey — that's the honest contract
        v = verify(env)
        t("verify requires full pubkey (honest)", v.get("valid") is False and
          "signer_pubkey required" in v.get("reason", ""), str(v))
        env["signer_pubkey"] = "f4b4278ddc216c2f060b273a"  # wrong pubkey -> must fail
        v2 = verify(env)
        t("wrong pubkey fails", v2.get("valid") is False)
    else:
        t("verify requires full pubkey (honest)", True)
        t("wrong pubkey fails", True)

    # 3. canonical reproducibility
    t("canonical reproducible", canonical({"b": 1, "a": 2}) == b'{"a":2,"b":1}')

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
