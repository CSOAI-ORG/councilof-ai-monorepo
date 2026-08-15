"""csoai-city.telemetry — self-instrumentation: SIGNED telemetry about the engine.

Catapult item #22: the engine emits SIGNED telemetry about its own operation —
cards issued, axes run, drift flags, verification results. The SAFE version of
"measure our own usage": operational facts, deterministic, no self-awareness
claims, no "consciousness" framing. Every telemetry frame is Ed25519-signed
through the same spine so an outside auditor can trust the estate's self-reports
exactly as much as its measurements.

Design:
  * emit(metric, value, **ctx) -> signed telemetry frame
  * frame = { kind: "sovos.telemetry", ts, metric, value, context, content_id, sig }
  * accumulates into a local JSONL log; the latest N frames can be re-signed/
    verified with the same Chain machinery
  * the frame itself is wrapped with cose_wrapper for external verifiability

Honesty rules:
  * telemetry describes OPERATION (what happened, when, counts) — never
    consciousness, emotion, or "state of mind"
  * unsigned telemetry (no key available) is marked "unsigned" and never
    presented as trusted
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    CRYPTO = True
except Exception:  # pragma: no cover
    CRYPTO = False

DEFAULT_LOG = Path("/var/log/sovos/telemetry.jsonl")


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _load_key(key_path: Optional[str] = None, generate: bool = True):
    # ONE loader (ADR_ONE_SIGNER): fail-closed on the production identity; `generate` gates
    # generation for an explicit temp/test path. Honest-unsigned (None) on a missing key.
    from .keystone import load_signing_key
    try:
        return load_signing_key(key_path, allow_generate=generate)
    except Exception:
        return None


@dataclass
class TelemetryFrame:
    kind: str
    ts: str
    metric: str
    value: Any
    context: Dict[str, Any]
    content_id: str
    signature: Optional[str]
    signed: bool
    signer: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SovosTelemetry:
    """Self-instrumentation sink. Append-only, signed, honest."""

    def __init__(self, log_path: Path = DEFAULT_LOG, key_path: Optional[Any] = None,
                 generate_key: bool = True):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.key = _load_key(str(key_path) if key_path else None, generate=generate_key)

    def emit(self, metric: str, value: Any, **ctx: Any) -> TelemetryFrame:
        """Emit one signed telemetry frame (append-only)."""
        frame_body = {
            "kind": "sovos.telemetry",
            "ts": datetime.now(timezone.utc).isoformat(),
            "metric": metric,
            "value": value,
            "context": ctx,
        }
        cid = __import__("hashlib").sha256(canonical(frame_body)).hexdigest()
        sig = pub = None
        signed = False
        if self.key is not None:
            try:
                sig = self.key.sign(cid.encode()).hex()
                pub = self.key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw).hex()
                signed = True
            except Exception:
                sig = pub = None
                signed = False

        frame = TelemetryFrame(
            kind="sovos.telemetry", ts=frame_body["ts"],
            metric=metric, value=value, context=ctx,
            content_id=cid, signature=sig, signed=signed, signer=pub,
        )
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(frame.to_dict()) + "\n")
        return frame

    def read(self, n: Optional[int] = None) -> list:
        frames = []
        if self.log_path.exists():
            for line in self.log_path.read_text().splitlines():
                line = line.strip()
                if line:
                    try:
                        frames.append(json.loads(line))
                    except Exception:
                        continue
        return frames[-n:] if n else frames

    def verify_frame(self, frame: Dict[str, Any]) -> bool:
        """Recompute + verify a frame's signature (no secret needed)."""
        if not frame.get("signature") or not frame.get("signer"):
            return False
        body = {"kind": frame["kind"], "ts": frame["ts"], "metric": frame["metric"],
                "value": frame["value"], "context": frame["context"]}
        cid = __import__("hashlib").sha256(canonical(body)).hexdigest()
        if cid != frame.get("content_id"):
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(frame["signer"])).verify(
                bytes.fromhex(frame["signature"]), cid.encode())
            return True
        except Exception:
            return False


def self_test() -> int:
    import tempfile
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    tmp = Path(tempfile.mkdtemp(prefix="telemetry-selftest-"))
    tel = SovosTelemetry(log_path=tmp / "t.jsonl", key_path=tmp / "key.pem")

    # 1. emit signs (key generated on the fly)
    f = tel.emit("cards_issued", 3, axis="art5", model="sov6-logic-v3-light")
    t("emit signs", f.signed is True)
    t("content_id set", len(f.content_id) == 64)

    # 2. verify round-trip
    t("frame verifies", tel.verify_frame(f.to_dict()) is True)
    # 3. tamper detection
    tampered = f.to_dict()
    tampered["value"] = 99
    t("tampered frame fails", tel.verify_frame(tampered) is False)

    # 4. append-only read
    tel.emit("axes_run", 14)
    frames = tel.read()
    t("frames accumulated", len(frames) == 2)

    # 5. unsigned honesty (no key -> signed False, never trusted)
    tel2 = SovosTelemetry(log_path=tmp / "u.jsonl", key_path=tmp / "nonexistent.pem",
                          generate_key=False)
    f2 = tel2.emit("drift_flags", 0)
    t("no-key frame honest unsigned", f2.signed is False)

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
