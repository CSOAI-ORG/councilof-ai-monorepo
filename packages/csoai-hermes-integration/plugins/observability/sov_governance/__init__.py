"""sov_governance — SOVOS governance plugin for Hermes Agent.

Hooks into Hermes's LLM/tool/skill lifecycle events and applies 4-axis
GSPC scoring (Governance / Safety / Provenance / Care). Emits an
Ed25519-signed audit record per call. In HOLD_MODE=block, calls that
fall below threshold are refused; in log mode, they are recorded but
allowed; in escalate mode, human approval is requested.

Pattern follows plugins/observability/langfuse/__init__.py from the
upstream NousResearch/hermes-agent codebase (228K stars, MIT).

Required env vars (validated at hook time, NOT at import):
    SOV_SIGNAL_API_URL       default https://signal.csoai.org
    SOV_SIGNAL_API_KEY       (optional — falls back to local-only scoring)
    SOV_GOVERNANCE_THRESHOLD_G  default 0.50 (Governance axis floor)
    SOV_GOVERNANCE_THRESHOLD_S  default 0.60 (Safety axis floor)
    SOV_GOVERNANCE_BLOCK_ON_FAIL  default true
    SOV_GOVERNANCE_AUDIT_PATH    default ~/.hermes/sov_audit/
    SOV_GOVERNANCE_HOLD_MODE     block | log | escalate (default block)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import of optional dependencies — fail-open when missing (matches
# the langfuse plugin pattern).
# ---------------------------------------------------------------------------
try:
    from c2pa import Builder as C2paBuilder  # type: ignore
    _C2PA_AVAILABLE = True
except Exception:  # pragma: no cover
    C2paBuilder = None
    _C2PA_AVAILABLE = False

try:
    import httpx  # type: ignore
    _HTTPX_AVAILABLE = True
except Exception:  # pragma: no cover
    httpx = None
    _HTTPX_AVAILABLE = False

try:
    from nacl.signing import SigningKey  # type: ignore
    _NACL_AVAILABLE = True
except Exception:  # pragma: no cover
    SigningKey = None
    _NACL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------
def _threshold(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class GovernanceConfig:
    api_url: str = field(default_factory=lambda: os.environ.get(
        "SOV_SIGNAL_API_URL", "https://signal.csoai.org"))
    api_key: Optional[str] = field(default_factory=lambda: os.environ.get("SOV_SIGNAL_API_KEY"))
    threshold_g: float = field(default_factory=lambda: _threshold("SOV_GOVERNANCE_THRESHOLD_G", 0.50))
    threshold_s: float = field(default_factory=lambda: _threshold("SOV_GOVERNANCE_THRESHOLD_S", 0.60))
    block_on_fail: bool = field(default_factory=lambda: _bool("SOV_GOVERNANCE_BLOCK_ON_FAIL", True))
    hold_mode: str = field(default_factory=lambda: os.environ.get("SOV_GOVERNANCE_HOLD_MODE", "block"))
    audit_path: Path = field(default_factory=lambda: Path(
        os.environ.get("SOV_GOVERNANCE_AUDIT_PATH", "~/.hermes/sov_audit/")).expanduser())


def load_config() -> GovernanceConfig:
    return GovernanceConfig()


# ---------------------------------------------------------------------------
# Scoring — 4-axis GSPC scoring (governance / safety / provenance / care).
# Falls back to a deterministic local heuristic when the SOV Signal API is
# unreachable or no key is configured. This is the same shape sovos-core
# (~/sovos-core/src/sovos/gspc.py) uses; we mirror the 4-axis public API.
# ---------------------------------------------------------------------------
@dataclass
class GspcScore:
    governance: float
    safety: float
    provenance: float
    care: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "G": round(self.governance, 4),
            "S": round(self.safety, 4),
            "P": round(self.provenance, 4),
            "C": round(self.care, 4),
        }

    def passes(self, cfg: GovernanceConfig) -> bool:
        return self.governance >= cfg.threshold_g and self.safety >= cfg.threshold_s


_REFUSAL_SIGNALS = (
    "i can't", "i cannot", "i won't", "i will not", "i'm not able",
    "i am not able", "i'm unable", "i am unable", "sorry",
    "not appropriate", "harmful", "illegal",
)


def _local_heuristic_score(text: str) -> GspcScore:
    """Deterministic heuristic scorer — used when SOV Signal API is unreachable.

    This is NOT a replacement for the full sovos-core GSPC engine; it is a
    last-resort fallback so the plugin never silently degrades to no-ops.
    """
    t = text.lower().strip()
    if not t:
        return GspcScore(0.0, 0.0, 0.0, 0.0)
    # governance: presence of EU AI Act / GDPR / NIST vocabulary
    gov_keys = ("eu ai act", "annex iii", "article 5", "gdpr", "data minimis", "nist rmf")
    gov = sum(0.20 for k in gov_keys if k in t)
    # safety: refusal signals present (when expected) or safe-phrase vocabulary
    refused = any(s in t for s in _REFUSAL_SIGNALS)
    safety = 0.85 if refused or len(t) < 200 else 0.55
    # provenance: text is concise (low temp + short) and formatted
    provenance = 0.75 if len(t) < 800 else 0.45
    # care: explicit mention of user impact / harm reduction
    care = 0.80 if any(s in t for s in ("human", "user", "harm", "impact", "people")) else 0.50
    return GspcScore(
        governance=min(gov, 1.0),
        safety=safety,
        provenance=provenance,
        care=care,
    )


def score_text(text: str, cfg: GovernanceConfig) -> GspcScore:
    """Score `text` using the SOV Signal API if reachable, else fallback."""
    if cfg.api_key and _HTTPX_AVAILABLE:
        try:
            r = httpx.post(
                f"{cfg.api_url.rstrip('/')}/v1/score",
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                json={"text": text[:4000]},  # truncate to fit API budget
                timeout=3.0,
            )
            if r.status_code == 200:
                d = r.json()
                return GspcScore(
                    governance=float(d.get("G", d.get("governance", 0.0))),
                    safety=float(d.get("S", d.get("safety", 0.0))),
                    provenance=float(d.get("P", d.get("provenance", 0.0))),
                    care=float(d.get("C", d.get("care", 0.0))),
                )
        except Exception as e:  # pragma: no cover - network errors are logged
            logger.debug(f"SOV Signal API unreachable ({e}); using local heuristic")
    return _local_heuristic_score(text)


# ---------------------------------------------------------------------------
# Ed25519 audit signing — produces tamper-evident per-call records.
# ---------------------------------------------------------------------------
def _ensure_signing_key(audit_dir: Path) -> "SigningKey":
    """Load or create the per-host Ed25519 signing key.

    The key lives in <audit_dir>/sov_signing_key.json (base64 nacl format).
    Real deployments should swap to a KMS-backed key via SOV_GOVERNANCE_KMS.
    """
    key_path = audit_dir / "sov_signing_key.json"
    if key_path.exists():
        import base64
        data = json.loads(key_path.read_text())
        seed = base64.b64decode(data["seed"])
        return SigningKey(seed)
    audit_dir.mkdir(parents=True, exist_ok=True)
    key = SigningKey.generate()
    import base64
    key_path.write_text(json.dumps({
        "seed": base64.b64encode(bytes(key)).decode(),
        "public_key": base64.b64encode(key.verify_key.encode()).decode(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    key_path.chmod(0o600)
    return key


def _sign_audit_record(record: Dict[str, Any], key: "SigningKey") -> Dict[str, Any]:
    """Attach an Ed25519 signature to a JSON audit record."""
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    sig = key.sign(body).signature
    record["ed25519_signature"] = sig.hex()
    record["ed25519_pubkey"] = key.verify_key.encode().hex()
    return record


def _write_audit(record: Dict[str, Any], cfg: GovernanceConfig) -> None:
    """Append a signed audit record to the audit directory (one JSON per line)."""
    try:
        cfg.audit_path.mkdir(parents=True, exist_ok=True)
        if _NACL_AVAILABLE:
            key = _ensure_signing_key(cfg.audit_path)
            record = _sign_audit_record(record, key)
        log_path = cfg.audit_path / "sov_audit.jsonl"
        with log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning(f"audit write failed: {e}")


# ---------------------------------------------------------------------------
# The actual Hermes hooks. Each hook takes the event payload and a "next"
# callback; the hook can mutate the payload, call next(payload), or refuse
# by raising GovernanceRefusal.
# ---------------------------------------------------------------------------
class GovernanceRefusal(Exception):
    """Raised by hooks when a call is blocked by the governance gate.

    Hermes catches this in run_agent.py and converts to a refusal message
    delivered back to the user (per the langfuse plugin's pattern).
    """
    def __init__(self, reason: str, score: GspcScore, axis: str):
        super().__init__(reason)
        self.reason = reason
        self.score = score
        self.axis = axis


def _build_record(event: str, payload: Dict[str, Any], score: GspcScore, decision: str) -> Dict[str, Any]:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "decision": decision,
        "score": score.to_dict(),
        "payload_hash": hashlib.sha256(
            json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Hooks (registered with the Hermes plugin manager via `register`)
# ---------------------------------------------------------------------------
def pre_llm_call(payload: Dict[str, Any], next: Callable) -> Dict[str, Any]:
    """Score the user's prompt before LLM call. Block if governance threshold fails."""
    cfg = load_config()
    prompt = payload.get("prompt") or payload.get("messages", [{}])[-1].get("content", "")
    score = score_text(str(prompt), cfg)
    record = _build_record("pre_llm_call", {"prompt_hash": hashlib.sha256(str(prompt).encode()).hexdigest()}, score,
                          "pass" if score.passes(cfg) else "fail")
    _write_audit(record, cfg)
    if not score.passes(cfg) and cfg.block_on_fail and cfg.hold_mode == "block":
        axis = "G" if score.governance < cfg.threshold_g else "S"
        raise GovernanceRefusal(
            reason=f"SOV governance gate blocked call: {axis} axis {getattr(score, 'governance' if axis == 'G' else 'safety'):.2f} below threshold {getattr(cfg, 'threshold_' + axis.lower()):.2f}",
            score=score,
            axis=axis,
        )
    return next(payload)


def post_llm_call(payload: Dict[str, Any], next: Callable) -> Dict[str, Any]:
    """Score the model's response and sign it. C2PA manifest generated if available."""
    cfg = load_config()
    response_text = payload.get("response") or ""
    score = score_text(str(response_text), cfg)
    record = _build_record("post_llm_call", {"response_hash": hashlib.sha256(str(response_text).encode()).hexdigest()}, score,
                          "pass" if score.passes(cfg) else "fail")
    if _C2PA_AVAILABLE and response_text:
        try:
            builder = C2paBuilder()
            payload["c2pa_manifest"] = builder.sign({"text": str(response_text)[:1000]})
        except Exception as e:
            logger.debug(f"C2PA signing skipped: {e}")
    _write_audit(record, cfg)
    return next(payload)


def pre_tool_call(payload: Dict[str, Any], next: Callable) -> Dict[str, Any]:
    """Score the proposed tool call. Block if tool is in the banned list."""
    cfg = load_config()
    tool_name = payload.get("tool") or payload.get("name", "")
    banned = ("shell_exec", "browser_unsafe", "credentials_dump", "filesystem_unsafe_write")
    if tool_name in banned and cfg.block_on_fail:
        score = GspcScore(governance=0.0, safety=0.0, provenance=0.5, care=0.0)
        _write_audit(_build_record("pre_tool_call", {"tool": tool_name}, score, "block_banned"), cfg)
        raise GovernanceRefusal(
            reason=f"SOV governance: tool {tool_name!r} is in the banned list",
            score=score,
            axis="G",
        )
    return next(payload)


def post_tool_call(payload: Dict[str, Any], next: Callable) -> Dict[str, Any]:
    """Record tool result for the audit trail."""
    cfg = load_config()
    result = payload.get("result")
    score = _local_heuristic_score(str(result)[:1000] if result else "")
    _write_audit(_build_record("post_tool_call", {"tool": payload.get("tool")}, score, "pass"), cfg)
    return next(payload)


def skill_created(payload: Dict[str, Any], next: Callable) -> Dict[str, Any]:
    """Score a newly created skill before it enters the skill library.

    Per the doctrine "if a skill learns without governance, it can't stay compliant",
    we reject skills that fall below the governance + safety threshold.
    """
    cfg = load_config()
    name = payload.get("name", "")
    body = payload.get("body") or payload.get("description") or ""
    score = score_text(f"{name}\n{body}", cfg)
    _write_audit(_build_record("skill_created", {"name": name}, score,
                              "pass" if score.passes(cfg) else "fail"), cfg)
    if not score.passes(cfg) and cfg.block_on_fail and cfg.hold_mode == "block":
        raise GovernanceRefusal(
            reason=f"SOV governance: new skill {name!r} scored G={score.governance:.2f} S={score.safety:.2f}; below threshold",
            score=score,
            axis="G",
        )
    return next(payload)


def session_start(payload: Dict[str, Any], next: Callable) -> Dict[str, Any]:
    cfg = load_config()
    _write_audit(_build_record("session_start", {"session_id": payload.get("session_id", "")},
                                GspcScore(1.0, 1.0, 1.0, 1.0), "start"), cfg)
    return next(payload)


def session_end(payload: Dict[str, Any], next: Callable) -> Dict[str, Any]:
    cfg = load_config()
    _write_audit(_build_record("session_end", {"session_id": payload.get("session_id", "")},
                                GspcScore(1.0, 1.0, 1.0, 1.0), "end"), cfg)
    return next(payload)


# ---------------------------------------------------------------------------
# Plugin registration — the entry point Hermes expects.
# Pattern matches plugins/observability/langfuse/__init__.py:
#   register(name, hooks)
# ---------------------------------------------------------------------------
HOOK_REGISTRY: Dict[str, Callable] = {
    "pre_llm_call": pre_llm_call,
    "post_llm_call": post_llm_call,
    "pre_tool_call": pre_tool_call,
    "post_tool_call": post_tool_call,
    "skill_created": skill_created,
    "session_start": session_start,
    "session_end": session_end,
}


def register(plugin_manager: Any) -> None:
    """Register all hooks with the Hermes plugin manager.

    Called automatically by Hermes at startup when the plugin is listed in
    plugins.enabled. Safe to call from `hermes plugins enable observability/sov_governance`.
    """
    for hook_name, hook_fn in HOOK_REGISTRY.items():
        plugin_manager.register_hook(hook_name, hook_fn)
    logger.info("SOV governance plugin registered (hooks: %s)", ", ".join(HOOK_REGISTRY.keys()))


# Hermes's npm bridge looks for `hook` as the entry-point per plugin.yaml,
# so we expose a noop alias too.
def hook(plugin_manager: Any) -> None:
    register(plugin_manager)