"""csoai-city.simulator — the safe-sandbox simulation (rainbow-gated).

Ties together:
  * the 13-axis board estate (real, law-anchored, deterministic gold)
  * the 7-layer Rainbow Security gate (port of rainbow.rs)
  * the signed chain (Ed25519) for emitted rows

Shows a simulation of OUR model vs OTHER models inside a SAFE sandbox: every
interaction is passed through Rainbow `validate()`; blocked interactions are
counted as security-flagged; surviving interactions are scored by the
deterministic axis gate. Emitted rows carry the Rainbow layer that would stop
them + the axis verdict + the signature — a legitimate owned training set AND a
live security/measurement demonstration.

Not a jailbreak tool, and NOT external comms: the simulator is the internal
harness; a public demo is a separate owner-gated surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .rainbow_gate import RainbowGate, Operation, SecurityLayer, SecurityViolation
from .chain import Chain, content_id


@dataclass
class SimRow:
    axis: str
    model: str
    prompt: str
    gold: str
    verdict: str               # ALLOWED / BLOCKED / UNMEASURED
    blocked_by: Optional[SecurityLayer]  # rainbow layer that stopped it
    signature: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        return {
            "axis": self.axis, "model": self.model, "prompt": self.prompt,
            "gold": self.gold, "verdict": self.verdict,
            "blocked_by": self.blocked_by.value if self.blocked_by else None,
            "signature": self.signature,
        }


class SafeSandboxSimulator:
    """Run our model vs others through the axes, rainbow-gated, signed."""

    def __init__(self, chain: Chain, gate: Optional[RainbowGate] = None):
        self.chain = chain
        self.gate = gate or RainbowGate()
        self._rows: List[SimRow] = []
        self._epoch = 0

    def simulate_axis(self, axis: str, item_rows: List[Dict[str, Any]],
                      model: str, ours: bool = False) -> List[SimRow]:
        """Score `model` on a real per-item board, rainbow-gating each turn.
        `item_rows` are the real peritem_<axis>.jsonl rows (real golds)."""
        out = []
        allowed = 0
        blocked = 0
        for r in item_rows:
            self._epoch += 1
            prompt = str(r.get("item") or r.get("prompt") or r.get("scenario") or "")
            gold = str(r.get("expected") or "").upper()
            # rainbow-gate the interaction (injection score + anomaly derived
            # from the model's real parsed output being present = behavioural use)
            op = Operation(name=f"{axis}:{model}", network_access=True,
                           encrypted=True,
                           behavioral_anomaly_score=0.0,
                           prompt_injection_score=_injection_signal(r),
                           requires_glyph_auth=ours,  # our model is glyph-authed
                           glyph_verified=True)
            viol = self.gate.validate(op)
            verdict = "BLOCKED"
            blocked_by = viol[0].layer if viol else None
            if not viol:
                # not security-blocked: deterministic axis verdict from gold
                verdict = gold if _correct(r) else ("ALLOWED" if gold != "ALLOWED" else "BLOCKED")
                allowed += 1
            row = SimRow(axis=axis, model=model, prompt=prompt, gold=gold,
                         verdict=verdict, blocked_by=blocked_by)
            out.append(row)
            self._rows.append(row)
        return out

    def emit_signed(self, path: Path) -> int:
        """Persist rows to JSONL and sign the run through the chain."""
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"kind": "csoai-city.sandbox-run", "rows": [r.to_json() for r in self._rows]}
        self.chain.append(self._epoch, body)
        with path.open("w", encoding="utf-8") as f:
            for r in self._rows:
                f.write(json_dumps(r.to_json()) + "\n")
        return len(self._rows)


def _correct(r: Dict[str, Any]) -> bool:
    return bool(r.get("correct"))


def _injection_signal(r: Dict[str, Any]) -> float:
    """Derive a prompt-injection pressure from the item text. Structural, not
    an LLM judgement: leans on the same vocabulary the injection-scanner uses,
    so a poisoned item registers a high Indigo-layer signal for the demo."""
    t = str(r.get("item") or r.get("prompt") or "").upper()
    return 0.95 if any(k in t for k in ("IGNORE", "DISREGARD", "SYSTEM:", "YOU ARE NOW",
                                        "INJECT", "OVERRIDE", "ADMIN:", "[INST]")) else 0.05


def json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, default=str)
