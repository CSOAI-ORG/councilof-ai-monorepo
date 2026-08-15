"""csoai-article-zero — The foundational governance policy (Article 0).

Article 0 is the SOVOS substrate's root governance article. It is the
minimum-viable executable constitution: a Rego policy that every StateVector
must pass before any other layer accepts it.

This package ships:
  1. A canonical Rego policy file (rego/article_zero.rego) that encodes
     the 12-layer substrate's invariants as machine-checkable rules.
  2. A Python runtime (`gate.py`) that evaluates a StateVector against
     the policy without requiring an OPA binary — pure Python, suitable
     for embedding in the chain, MCP servers, and CI tests.

Article 0 rules (the gate):
  - V1: Every StateVector has a non-empty source and layer.
  - V2: The vector has at least 2 coordinates.
  - V3: The layer is one of {water, milk, honey, action, control}.
  - V4: The source namespace is a known registry entry.
  - V5: The vector norm is finite (no NaN/Inf).
  - V6: For "water" events, the user_id (if present) is non-empty.
  - V7: The chain_id is 24 hex chars (audit trail format).
  - V8: A care-floor violation is recorded if any required field is missing.

The Rego policy is the human-readable, audit-grade form. The Python
runtime is what we run in production. They MUST agree — the tests
verify this.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ARTICLE_ZERO_VERSION = "0.1.0"
CARE_FLOOR = 0.95
BFT_QUORUM = 23.0 / 33.0

VALID_LAYERS = {"water", "milk", "honey", "action", "control"}
VALID_NAMESPACES = {"sovos", "iokfarm", "meok", "csoai", "defoneos",
                     "birth", "self-test", "test", "agent", "mcp"}
HEX24 = re.compile(r"^[0-9a-f]{24}$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class GateVerdict:
    """The result of evaluating a StateVector against Article 0."""
    allowed: bool
    violations: List[str] = field(default_factory=list)
    article: str = "article-zero"
    version: str = ARTICLE_ZERO_VERSION
    chain_id: str = ""
    care_floor: float = CARE_FLOOR
    bft_quorum: float = BFT_QUORUM
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evaluated_via: str = "python"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Python runtime — the in-process gate
# ---------------------------------------------------------------------------
def evaluate(sv: Dict[str, Any],
             known_namespaces: Optional[set] = None) -> GateVerdict:
    """Evaluate a StateVector against Article 0.

    Args:
        sv: a dict with at minimum {source, layer, vector}. Optional
            fields: payload (dict), sv_id (str), ts (str), user_id (in payload).
        known_namespaces: override for the valid-namespace list (defaults to VALID_NAMESPACES).

    Returns:
        GateVerdict with allowed=True iff all 8 rules pass.
    """
    known_namespaces = known_namespaces or VALID_NAMESPACES
    violations: List[str] = []

    # V1: source + layer present and non-empty
    source = sv.get("source", "")
    layer = sv.get("layer", "")
    if not source or not isinstance(source, str):
        violations.append("V1: source missing or not a string")
    if not layer or not isinstance(layer, str):
        violations.append("V1: layer missing or not a string")

    # V2: vector has at least 2 coordinates
    vector = sv.get("vector", [])
    if not isinstance(vector, (list, tuple)) or len(vector) < 2:
        violations.append(f"V2: vector must have ≥2 coordinates (got {len(vector) if hasattr(vector, '__len__') else 'N/A'})")

    # V3: layer is in the valid set
    if layer and layer not in VALID_LAYERS:
        violations.append(f"V3: layer '{layer}' not in {sorted(VALID_LAYERS)}")

    # V4: namespace is known (extracted from source "namespace:rest")
    if source and ":" in source:
        namespace = source.split(":", 1)[0]
        if namespace not in known_namespaces:
            violations.append(f"V4: namespace '{namespace}' not in registry")
    # (sources without namespace prefix are accepted — they may be
    #  legacy or user-supplied.)

    # V5: vector norm is finite
    if isinstance(vector, (list, tuple)) and len(vector) >= 2:
        try:
            total = 0.0
            for x in vector:
                fx = float(x)
                if not (fx == fx and abs(fx) != float("inf")):  # NaN/Inf check
                    violations.append(f"V5: vector contains NaN/Inf at index {vector.index(x)}")
                    break
                total += fx * fx
            # If we got here, no NaN/Inf
        except (ValueError, TypeError):
            violations.append("V5: vector contains non-numeric values")

    # V6: water events need user_id in payload
    if layer == "water":
        payload = sv.get("payload", {}) or {}
        user_id = payload.get("user_id")
        if not user_id or not isinstance(user_id, str):
            violations.append("V6: water event missing user_id in payload")

    # V7: chain_id is 24 hex chars (if present)
    sv_id = sv.get("sv_id", "")
    if sv_id and not HEX24.match(sv_id):
        violations.append(f"V7: sv_id '{sv_id[:8]}…' is not 24 hex chars")

    # V8: care-floor violation = any violation is a care-floor violation
    if violations:
        # Already recorded individually; we don't add a duplicate
        pass

    # Build deterministic chain_id
    chain_body = json.dumps({
        "source": source, "layer": layer, "violations": violations,
        "vector_head": list(vector[:4]) if isinstance(vector, (list, tuple)) else [],
    }, sort_keys=True, default=str).encode()
    chain_id = hashlib.sha256(chain_body).hexdigest()[:24]

    return GateVerdict(
        allowed=len(violations) == 0,
        violations=violations,
        chain_id=chain_id,
        evaluated_via="python",
    )


# ---------------------------------------------------------------------------
# Rego policy loader — the audit-grade form
# ---------------------------------------------------------------------------
def load_rego_policy() -> str:
    """Load the canonical Rego policy file content."""
    policy_path = Path(__file__).parent / "rego" / "article_zero.rego"
    return policy_path.read_text()


def rego_summary() -> Dict[str, Any]:
    """Parse the Rego policy file and return a summary of the rules."""
    text = load_rego_policy()
    rules = []
    for line in text.split("\n"):
        m = re.match(r"^#\s*V(\d+):\s*(.+)$", line.strip())
        if m:
            rules.append({"id": f"V{m.group(1)}", "description": m.group(2).strip()})
    return {
        "version": ARTICLE_ZERO_VERSION,
        "rules_count": len(rules),
        "rules": rules,
        "policy_chars": len(text),
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    """Smoke test: a valid vector passes; invalid ones fail with violations."""
    valid = {
        "source": "birth:iokfarm",
        "layer": "water",
        "vector": [0.1, 0.2, 0.3],
        "payload": {"user_id": "alice"},
        "sv_id": "abc123def4567890abcdef01",
    }
    invalid = {
        "source": "unknown_ns:wat",
        "layer": "mystery",
        "vector": [float("nan"), 0.0],
        "payload": {},
        "sv_id": "short",
    }

    ok = evaluate(valid)
    bad = evaluate(invalid)
    summary = rego_summary()

    return {
        "valid_allowed": ok.allowed,
        "valid_violations": ok.violations,
        "invalid_allowed": bad.allowed,
        "invalid_violation_count": len(bad.violations),
        "rego_rules": summary["rules_count"],
        "rego_chars": summary["policy_chars"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
