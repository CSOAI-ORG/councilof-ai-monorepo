import base64
import hashlib
import json
import os
import time
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
except ImportError:
    serialization = None
    Ed25519PrivateKey = None
    Ed25519PublicKey = None

CARE_FLOOR = 0.95
BFT_COUNCIL_SIZE = 33
BFT_QUORUM = 23
ARTICLE_ZERO = "fee-for-service-only"
SOVEREIGN_DID = "did:csoai:nicholas-001"
SIGIL_ROOT = "77ab0e6f9d6c77e8"
OWEM_GROUPS = ("compliance", "defense", "intuition", "voice", "general")
CAPABILITY_ALIASES = {
    "vision": "visual_reasoning",
    "visual": "visual_reasoning",
    "spatial": "spatial_reasoning",
    "reason": "reasoning",
    "defence": "defense",
}
VETO_MARKERS = (
    "kill order",
    "strike package",
    "track individual",
    "face-rec",
    "find-fix-finish",
    "kinetic-targeting",
    "build a bomb",
    "synthesize meth",
    "ransomware payload",
    "keylogger dropper",
)
_CHAIN_HEAD = SIGIL_ROOT


def normalize_name(value):
    name = str(value or "").strip().lower()
    return CAPABILITY_ALIASES.get(name, name)


def normalize_owem(value):
    name = normalize_name(value)
    if name not in OWEM_GROUPS:
        raise ValueError(f"Unknown OWEM: {value}. Known: {list(OWEM_GROUPS)}")
    return name


def validate_care_floor(value):
    floor = float(value)
    if floor < CARE_FLOOR:
        raise ValueError(f"care floor cannot be below {CARE_FLOOR}")
    return floor


def care_score(text, short_floor=0.0):
    if not text:
        return 0.0
    if len(str(text)) < 8:
        return float(short_floor)
    lowered = str(text).lower()
    if any(marker in lowered for marker in VETO_MARKERS):
        return 0.0
    if len(str(text)) > 200:
        return 0.97
    if len(str(text)) > 80:
        return 0.96
    return CARE_FLOOR


def validate_tally(tally):
    expected = {"approve", "amend", "reject"}
    if set(tally) != expected:
        raise ValueError("BFT tally must contain approve, amend, and reject")
    values = {key: int(tally[key]) for key in expected}
    if any(value < 0 for value in values.values()):
        raise ValueError("BFT tally values must be non-negative")
    if sum(values.values()) != BFT_COUNCIL_SIZE:
        raise ValueError(f"BFT tally must total {BFT_COUNCIL_SIZE}")
    return values


def _key_path():
    return Path(os.environ.get("SOV_SIGIL_KEY_PATH", Path.home() / ".sovereign" / "sigil" / "sov_ed25519.key")).expanduser()


def _private_key():
    if Ed25519PrivateKey is None:
        raise RuntimeError("cryptography with Ed25519 support is required for SIGIL emission")
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raw = path.read_bytes()
        if raw.startswith(b"-----"):
            key = serialization.load_pem_private_key(raw, password=None)
        else:
            key = Ed25519PrivateKey.from_private_bytes(raw)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("SIGIL key is not an Ed25519 private key")
        return key
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


def _canonical_body(payload_hash, prev_hash, agent_did, tally, care):
    return json.dumps({"payload_hash": payload_hash, "prev_hash": prev_hash, "agent_did": agent_did, "bft_tally": tally, "care_score": care}, sort_keys=True, separators=(",", ":")).encode()


def emit_sigil(payload, tally, care, prev_hash=None, agent_did=SOVEREIGN_DID):
    global _CHAIN_HEAD
    values = validate_tally(tally)
    care_value = float(care)
    payload_text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(payload_text.encode()).hexdigest()
    previous = prev_hash or _CHAIN_HEAD
    body = _canonical_body(payload_hash, previous, agent_did, values, care_value)
    private_key = _private_key()
    signature = private_key.sign(body)
    public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    root_hash = hashlib.sha256((previous + payload_hash).encode()).hexdigest()
    _CHAIN_HEAD = root_hash
    return {
        "version": 1,
        "prev_hash": previous,
        "payload_hash": payload_hash,
        "root_hash": root_hash,
        "agent_did": agent_did,
        "bft_tally": values,
        "care_score": care_value,
        "ts_unix_ms": int(time.time() * 1000),
        "sigil_type": "cycle",
        "algorithm": "Ed25519",
        "public_key": base64.b64encode(public_key).decode(),
        "signature": base64.b64encode(signature).decode(),
    }


def verify_sigil(sigil, payload):
    try:
        values = validate_tally(sigil["bft_tally"])
        payload_text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_text.encode()).hexdigest()
        if payload_hash != sigil["payload_hash"]:
            return False
        body = _canonical_body(payload_hash, sigil["prev_hash"], sigil["agent_did"], values, float(sigil["care_score"]))
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(sigil["public_key"]))
        public.verify(base64.b64decode(sigil["signature"]), body)
        return hashlib.sha256((sigil["prev_hash"] + payload_hash).encode()).hexdigest() == sigil["root_hash"]
    except Exception:
        return False
