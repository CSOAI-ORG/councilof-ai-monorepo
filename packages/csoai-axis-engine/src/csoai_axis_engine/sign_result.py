#!/usr/bin/env python3
"""sign_result — sign an axis measurement result into an Ed25519-signed card (EAT box 3).

Canonicalises the result (sorted-key JCS-ish), computes content_id = SHA-256(canonical),
signs it with the estate Ed25519 key, and writes a signed card. Offline-verifiable.
"""
import json, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def canonical(v):
    if isinstance(v, dict):
        return "{" + ",".join(canonical(k) + ":" + canonical(v[k]) for k in sorted(v)) + "}"
    if isinstance(v, list):
        return "[" + ",".join(canonical(x) for x in v) + "]"
    if isinstance(v, str): return json.dumps(v)
    if v is True: return "true"
    if v is False: return "false"
    if v is None: return "null"
    return str(v)

def sign_result(result_path, key_path, out_path=None, signer="did:web:csoai.org#estate-chain-1", ts=None):
    result = json.loads(Path(result_path).read_text())
    body = {k: result[k] for k in sorted(result)}
    cbody = canonical(body)
    content_id = hashlib.sha256(cbody.encode()).hexdigest()
    key = Ed25519PrivateKey.from_private_bytes(Path(key_path).read_bytes()[:32])
    sig = key.sign(cbody.encode()).hex()
    pub = key.public_key().public_bytes_raw().hex()
    card = dict(body,
                content_id=content_id,
                signature="ed25519:" + sig,
                signer=signer,
                signed_at=ts or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    out = out_path or (result_path + ".signed.json")
    Path(out).write_text(json.dumps(card, indent=2))
    print(f"signed card at {out}")
    print(f"  content_id: {content_id[:16]}…")
    print(f"  signer: {signer}")
    print(f"  pubkey: {pub[:16]}…")
    return card

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python3 sign_result.py <result.json> <ed25519.key> [out.json]"); sys.exit(1)
    sign_result(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
