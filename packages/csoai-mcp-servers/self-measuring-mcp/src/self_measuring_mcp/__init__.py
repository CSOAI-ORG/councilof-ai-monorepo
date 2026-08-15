"""self_measuring_mcp — signed measurement an agent calls on ITSELF.

The Layer-1 discovery + forcing-function surface: an MCP server exposing a
`self_measure` tool that runs deterministic transparency checks on the caller's
own metrics, emits an Ed25519-signed card via the sovos-city Chain, and returns
it. Lists an agent card + llms.txt + .well-known for machine discovery.

Design:
  * DSELF  Deterministic self-measurement (no LLM judge — the ruler is code).
  * Imports sovos-city CouncilSignal/Chain rather than duplicating them.
  * Lawful: measures what the caller *provides* (self-attested public metrics)
    or public artifacts; never a private/surprise scan.
  * Forcing function: returns a signed card an agent/CI/marketplace can REQUIRE.

This is a standalone scaffold (matches the estate's lightweight MCP packages):
`python -m self_measuring_mcp` runs a local demo; the real stdio/HTTP binding
is wired per hosting.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from sovos_city.council_signal import CouncilSignal, ArtifactFact
    from sovos_city.chain import Chain
    HAS_SOVOS = True
except Exception:  # pragma: no cover — standalone mode without sovos-city
    HAS_SOVOS = False

# The transparent self-measurement schema: what an agent can assert about itself.
# Each key maps to a deterministic predicate an agent can truthfully fill in.
SELF_METRICS = [
    "license_declared",      # is an open-source license declared?
    "model_card_present",    # does a model/agent card exist?
    "provenance_declared",   # is provenance/marking declared (Art 50)?
    "logs_retained",         # are agent logs retained (Art 12)?
    "oversight_enabled",     # is human oversight possible (Art 14)?
    "eval_open",             # is an eval/benchmark published?
]

TOOL_SCHEMA = {
    "name": "self_measure",
    "description": "Run a deterministic, signed self-measurement and return a "
                   "verifiable card the caller can present to a CI gate, "
                   "marketplace, or insurer. Lawful: measures the tentative "
                   "metrics you provide; no surprise scans.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "entity": {"type": "string", "description": "caller's name/id"},
            "metrics": {
                "type": "object",
                "description": "0..1 per SELF_METRICS key: self-attested score",
                "additionalProperties": {"type": "number"},
            },
        },
        "required": ["entity", "metrics"],
    },
}


def self_measure(entity: str, metrics: Dict[str, Any],
                 chain_path: Path = Path("/tmp/sovos-measure-chain.jsonl"),
                 store: Path = Path("/tmp/sovos-measure-store")) -> Dict[str, Any]:
    """Run the deterministic measurement and emit a signed card."""
    if not HAS_SOVOS:
        # offline fallback: still compute verdicts + a pseudo content_id
        facts = [_fact(k, metrics.get(k)) for k in SELF_METRICS]
        return {
            "entity": entity,
            "signed": False,
            "standalone": True,
            "facts": [{"axis": f.axis, "label": f.label, "score": f.score,
                       "verdict": f.verdict()} for f in facts],
            "note": "sovos-city not importable; unsigned standalone card",
        }
    cs = CouncilSignal(Chain(chain_path), store=store)
    facts = [_fact(k, metrics.get(k)) for k in SELF_METRICS]
    out = cs.scan(entity, facts)
    rec = out["record"]
    return {
        "entity": entity,
        "signed": rec["signed"],
        "content_id": rec["content_id"],
        "facts": [{"axis": f["axis"], "label": f["label"], "score": f["score"],
                   "verdict": f["verdict"]} for f in rec["body"]["facts"]],
        "aggregated": rec["body"]["aggregated"],
        "drift": out["drift"],
        "signature": rec["signature"],
    }


def _fact(key: str, val: Any) -> ArtifactFact:
    score = 0.0
    if val is not None:
        try:
            score = float(val)
        except (TypeError, ValueError):
            score = 1.0 if val else 0.0
    # axis mapping for legibility
    axis = {"license_declared": "oss", "model_card_present": "gov",
            "provenance_declared": "prv", "logs_retained": "gov",
            "oversight_enabled": "gov", "eval_open": "swarm"}.get(key, "gov")
    return ArtifactFact(axis, key, score, 0.5, source="self_measure")


def list_tools() -> List[Dict[str, Any]]:
    return [TOOL_SCHEMA]


def main() -> None:
    """Entry point for `python -m self_measuring_mcp` — local demo."""
    print("self-measuring-mcp v0.1.0 (Layer-1 discovery + forcing function)")
    print("tools:", [t["name"] for t in list_tools()])
    # demo: a "compliant" agent self-measures
    m = {"license_declared": 1.0, "model_card_present": 1.0,
         "provenance_declared": 0.8, "logs_retained": 1.0,
         "oversight_enabled": 1.0, "eval_open": 0.9}
    card = self_measure("demo-agent", m)
    print(json.dumps(card, indent=2)[:900])


if __name__ == "__main__":
    main()

__all__ = ["self_measure", "list_tools", "TOOL_SCHEMA", "SELF_METRICS", "main"]
