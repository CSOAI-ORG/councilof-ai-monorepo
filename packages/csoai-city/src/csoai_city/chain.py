"""Signed, append-only ChainResults for a city run.

Every epoch produces one ChainResult: a sha256 content id over the canonical
JSON, chained to its predecessor, and Ed25519-signed.

The structural rule this module exists to enforce: **a record cannot claim to be
signed when it is not.** If no key is available, `signature` is None and `status`
is the literal string "UNSIGNED". There is no third path where an unsigned record
looks signed. Anyone can verify a chain offline with `verify_chain()`.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization
    CRYPTO = True
except Exception:  # pragma: no cover
    CRYPTO = False

GENESIS = "0" * 64


def canonical(obj: Any) -> bytes:
    """One byte-string per logical record, so ids are reproducible anywhere."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def content_id(body: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical(body)).hexdigest()


@dataclass
class ChainResult:
    epoch: int
    prev: str
    id: str
    body: Dict[str, Any]
    status: str                       # "SIGNED" | "UNSIGNED"
    signature: Optional[str] = None
    pubkey: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)


class Chain:
    """Append-only signed chain over a JSONL file."""

    def __init__(self, path: str | Path, key_path: Optional[str | Path] = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._load_key(key_path)

    # ── keys ────────────────────────────────────────────────────────────────
    @staticmethod
    def _load_key(key_path: Optional[str | Path]):
        if not CRYPTO:
            return None
        # ONE loader for the whole estate (ADR_ONE_SIGNER): fail-closed on the production identity,
        # generate only for explicit temp/test paths. See keystone.py.
        from .keystone import load_signing_key
        return load_signing_key(key_path)

    def _pubkey_hex(self) -> Optional[str]:
        if not self._key:
            return None
        return self._key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()

    # ── append ──────────────────────────────────────────────────────────────
    def tip(self) -> str:
        last = GENESIS
        for rec in self.read():
            last = rec.get("id", last)
        return last

    def append(self, epoch: int, body: Dict[str, Any]) -> ChainResult:
        prev = self.tip()
        stamped = dict(body, prev=prev, epoch=epoch)
        cid = content_id(stamped)
        sig = pub = None
        status = "UNSIGNED"
        if self._key is not None:
            try:
                sig = self._key.sign(cid.encode()).hex()
                pub = self._pubkey_hex()
                status = "SIGNED"
            except Exception:
                sig = pub = None
                status = "UNSIGNED"
        cr = ChainResult(epoch=epoch, prev=prev, id=cid, body=stamped,
                         status=status, signature=sig, pubkey=pub)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(cr.to_json() + "\n")
        return cr

    # ── read / verify ───────────────────────────────────────────────────────
    def read(self) -> Iterator[Dict[str, Any]]:
        if not self.path.exists():
            return iter(())
        def gen():
            with self.path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except Exception:
                            continue
        return gen()

    def verify(self) -> Dict[str, Any]:
        """Recompute every id and check every signature. Reports, never asserts."""
        prev, ok_ids, bad_ids, ok_sigs, unsigned, bad_sigs = GENESIS, 0, 0, 0, 0, 0
        for rec in self.read():
            body = rec.get("body", {})
            if body.get("prev") != prev or content_id(body) != rec.get("id"):
                bad_ids += 1
            else:
                ok_ids += 1
            prev = rec.get("id", prev)
            if rec.get("status") != "SIGNED" or not rec.get("signature"):
                unsigned += 1
            elif CRYPTO:
                try:
                    Ed25519PublicKey.from_public_bytes(bytes.fromhex(rec["pubkey"])).verify(
                        bytes.fromhex(rec["signature"]), rec["id"].encode())
                    ok_sigs += 1
                except Exception:
                    bad_sigs += 1
        return {"records": ok_ids + bad_ids, "hash_ok": ok_ids, "hash_broken": bad_ids,
                "signature_ok": ok_sigs, "signature_broken": bad_sigs, "unsigned": unsigned,
                "chain_intact": bad_ids == 0 and bad_sigs == 0,
                "crypto_available": CRYPTO}
