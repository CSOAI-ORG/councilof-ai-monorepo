#!/usr/bin/env python3
"""keystone.py — the ONE place the estate's signing identity is read (ADR_ONE_SIGNER_2026-08-14).

Before this, five modules each hardcoded their own key-path default (some `~/.sovos`, some
`/root/.sovos`) and several silently AUTO-GENERATED a fresh key when the file was missing — the
exact way a rogue second identity gets minted. This is the single loader they all now call:
one canonical path, one fail-closed rule.

Rules:
  • ONE default path: $SOVOS_CITY_KEY, else ~/.sovos/city_ed25519 (== /root/.sovos/... on the pod).
  • FAIL-CLOSED on the production identity: a missing canonical key path RAISES — it is never
    auto-generated (a generated key is an unpublished second identity = no identity).
  • Generation is allowed ONLY for an explicit non-production (temp/test) key_path, and only when
    allow_generate=True. Callers wanting honest-unsigned wrap the call in try/except -> None.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DEFAULT_KEY_PATH = os.environ.get("SOVOS_CITY_KEY") or str(Path.home() / ".sovos" / "city_ed25519")


def _prod_paths() -> set:
    prod = {Path("/root/.sovos/city_ed25519"), Path.home() / ".sovos" / "city_ed25519"}
    env = os.environ.get("SOVOS_CITY_KEY")
    if env:
        prod.add(Path(env))
    return prod


def load_signing_key(key_path: Optional[str | Path] = None, *, allow_generate: bool = True):
    """Load THE Ed25519 signing key. Fail-closed on the production identity; generate only for an
    explicit non-production path when allow_generate. Raises FileNotFoundError on a missing prod key.
    Returns None only if the crypto library is unavailable (never a silently-generated prod key)."""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except Exception:
        return None
    # read the default fresh each call so $SOVOS_CITY_KEY set at runtime is honoured
    default = os.environ.get("SOVOS_CITY_KEY") or str(Path.home() / ".sovos" / "city_ed25519")
    p = Path(key_path or default)
    if p.exists():
        return serialization.load_pem_private_key(p.read_bytes(), password=None)
    if p in _prod_paths() or key_path is None:
        raise FileNotFoundError(
            f"production signing key missing at {p} — refusing to auto-generate a rogue identity "
            "(one-key doctrine, ADR_ONE_SIGNER_2026-08-14). Provision the keystone key, or pass an "
            "explicit temp key_path for tests.")
    if not allow_generate:
        return None
    k = Ed25519PrivateKey.generate()                       # explicit non-prod path (tests/temp)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(k.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    p.chmod(0o600)
    return k


def keystone_pubkey_hex(key_path: Optional[str | Path] = None) -> Optional[str]:
    """The public key hex of the signing identity (public only — never touches the private key)."""
    from cryptography.hazmat.primitives import serialization
    k = load_signing_key(key_path)
    if k is None:
        return None
    return k.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()
