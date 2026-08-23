#!/usr/bin/env python3
"""attest — sign a bond/record JSON blob into an Ed25519 A2A attestation (Proof-of-Weave).

Every COBOL record the bridge emits gets signed so an A2A agent (bank, insurer, market maker)
can verify provenance offline — the trust that lets a Chinese insurer underwrite a UK SME.
"""
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

def canonical(v):
    if isinstance(v, dict): return "{" + ",".join(canonical(k)+":"+canonical(v[k]) for k in sorted(v)) + "}"
    if isinstance(v, list): return "[" + ",".join(canonical(x) for x in v) + "]"
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, bool): return "true" if v else "false"
    if v is None: return "null"
    return str(v)

def attest(record: dict, key_path: str, signer: str = "did:web:csoai.org#estate-chain-1") -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    body = {k: record[k] for k in sorted(record)}
    cbody = canonical(body)
    content_id = hashlib.sha256(cbody.encode()).hexdigest()
    key = Ed25519PrivateKey.from_private_bytes(Path(key_path).read_bytes()[:32])
    sig = key.sign(cbody.encode()).hex()
    return dict(body, content_id=content_id, signature="ed25519:"+sig, signer=signer,
                signed_at=datetime.now(timezone.utc).isoformat().replace("+00:00","Z"))
