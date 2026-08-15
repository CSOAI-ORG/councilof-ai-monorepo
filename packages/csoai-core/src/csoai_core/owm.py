"""SOVOS OOWM layer - Outer World Model orchestration.

Implements the OpenRouter-provided Nemotron 3 Ultra integration from the
NEMOTRON_OWM_INTERRATION guide, adapted to the SOVOS dependency-light,
deterministic core. The OWMRouter selects *dream depth* by task urgency and
importance:

    CRITICAL / DEEP  -> Nemotron 3 Ultra (cloud, 1M context, deep thinking)
    FAST             -> local fast dream (Gemma 4 class)
    INSTINCT         -> rule-based local reaction (SOV3 class, <1ms)

Free-tier reality is enforced (dream quotas) and local fallback is
mandatory so SOVOS never hard-wires a recurring mission to one :free
endpoint. No API key is needed to import, test, or run the local paths.
Purchasing credits and spending remain owner-gated.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .gspc import GSPCScore, score_gspc


class DreamDepth(str, Enum):
    INSTINCT = "local_sov3"
    FAST = "gemma4_local"
    DEEP = "nemotron_ultra"
    CRITICAL = "nemotron_ultra_deep"


@dataclass
class DreamOutcome:
    scenario_id: str
    description: str
    probability: float
    gspc: Dict[str, float]
    recommended_action: Optional[str]
    risk_level: str


@dataclass
class OWMState:
    epoch: int = 0
    scale: int = 1
    active_nodes: List[Dict] = field(default_factory=list)
    recent_events: List[Dict] = field(default_factory=list)
    gspc_current: Dict[str, float] = field(default_factory=dict)
    pending_tasks: List[str] = field(default_factory=list)

    @property
    def g(self) -> float:
        return float(self.gspc_current.get("G", 0.0))

    @property
    def s(self) -> float:
        return float(self.gspc_current.get("S", 0.0))


def _select_best_future(futures: List[DreamOutcome]) -> DreamOutcome:
    """Weighted GSPC selection: G 40% / S 30% / P 20% / C 10%."""
    def score(f: DreamOutcome) -> float:
        g = f.gspc.get("G", 0.0)
        s = f.gspc.get("S", 0.0)
        p = f.gspc.get("P", 0.0)
        c = f.gspc.get("C", 0.0)
        return g * 0.4 + s * 0.3 + p * 0.2 + c * 0.1
    return max(futures, key=score)


def _fallback_outcome(state: OWMState, label: str = "fallback_1") -> DreamOutcome:
    """Local/instinct fallback dream - never depends on the network."""
    return DreamOutcome(
        scenario_id=label,
        description="Local fallback: maintain course with caution.",
        probability=1.0,
        gspc=dict(state.gspc_current),
        recommended_action="MAINTAIN_COURSE",
        risk_level="MEDIUM",
    )


class NemotronOWM:
    """Nemotron 3 Ultra via OpenRouter (deep dream engine).

    stdlib-only HTTP client (urllib) - no OpenAI SDK, no pydantic coupling,
    no broken native-module risk in the Hermes environment. 1M-context model,
    free tier with hard quotas (50/day free, 1000/day after $10 credits).
    """

    BASE = "https://openrouter.ai/api/v1/chat/completions"
    MODEL_FREE = "nvidia/nemotron-3-ultra-550b-a55b:free"

    def __init__(self, api_key: str | None = None, max_free: int = 50):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = self.MODEL_FREE
        self.dream_count = 0
        self.max_free_dreams = max_free

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _build_prompt(self, state: OWMState) -> str:
        p = [f"[SOVOS WORLD SIMULATION - EPOCH {state.epoch}]", "", "CURRENT STATE:"]
        p.append(f"- Scale: {state.scale}")
        g = state.gspc_current
        p.append(f"- G-Score: {g.get('G', 0.0):.2f}")
        p.append(f"- S-Score: {g.get('S', 0.0):.2f}")
        p.append(f"- P-Score: {g.get('P', 0.0):.2f}")
        p.append(f"- C-Score: {g.get('C', 0.0):.2f}")
        p.append("")
        p.append(f"ACTIVE NODES ({len(state.active_nodes)}):")
        for node in state.active_nodes[:20]:
            p.append(f"- {node.get('id', 'unknown')}: {node.get('type', 'agent')} | "
                     f"G={node.get('g', 0.0):.2f} | Energy={node.get('energy', 0.0):.1f}")
        p.append("")
        p.append(f"RECENT EVENTS ({len(state.recent_events)}):")
        for event in state.recent_events[-10:]:
            p.append(f"- [{event.get('timestamp', '?')}] {event.get('type', 'unknown')}: {event.get('summary', '')[:80]}")
        p.append("")
        p.append(f"PENDING DECISIONS: {', '.join(state.pending_tasks)}")
        p.append("")
        p.append("[SIMULATION INSTRUCTIONS] Simulate 5 plausible futures for the next 10 seconds. "
                 "For each: scenario_id, description, probability, gspc (G/S/P/C), "
                 "recommended_action, risk_level. Return strict JSON with futures, best_future.")
        return "\n".join(p)

    def dream(self, state: OWMState, deep: bool = True) -> List[DreamOutcome]:
        if not self.available:
            return [_fallback_outcome(state, label="fallback_no_key")]
        if self.dream_count >= self.max_free_dreams:
            return [_fallback_outcome(state, label="fallback_quota")]
        try:
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are the Outer World Model of SOVOS."},
                    {"role": "user", "content": self._build_prompt(state)},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            }
            if deep:
                body["reasoning"] = {"enabled": True, "budget_tokens": 4096}
            req = urllib.request.Request(
                self.BASE,
                data=json.dumps(body).encode(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://csoai.org",
                    "X-Title": "SOVOS",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            self.dream_count += 1
            content = data["choices"][0]["message"].get("content", "")
            start = content.find("{")
            end = content.rfind("}") + 1
            payload = json.loads(content[start:end]) if 0 <= start < end else json.loads(content)
            futures = []
            for f in payload.get("futures", []):
                futures.append(DreamOutcome(
                    scenario_id=f.get("scenario_id", "f?"),
                    description=f.get("description", ""),
                    probability=float(f.get("probability", 0.0)),
                    gspc={k: float(v) for k, v in f.get("gspc", {}).items()},
                    recommended_action=f.get("recommended_action"),
                    risk_level=f.get("risk_level", "MEDIUM"),
                ))
            return futures or [_fallback_outcome(state)]
        except Exception:
            return [_fallback_outcome(state, label="fallback_error")]


class OWMRouter:
    """Routes each task to the right dream depth and applies the G-block gate.

    A `local_engine` (OllamaEngine) may be injected so FAST dreams call real
    local inference (e.g. on sov-brain-2) rather than a stub.
    """

    def __init__(self, owm: Optional[NemotronOWM] = None, max_deep: int = 50,
                 local_engine=None):
        self.owm = owm or NemotronOWM()
        self.daily_deep_dreams = 0
        self.max_deep_dreams = max_deep
        self.local_engine = local_engine

    def route(self, state: OWMState, urgency: float, importance: float) -> DreamDepth:
        # Governance/security below threshold -> escalate to (deep) Nemotron.
        if state.g < 0.8 or state.s < 0.8:
            return DreamDepth.CRITICAL
        if importance > 0.8 and urgency < 0.5:
            return DreamDepth.DEEP
        if importance > 0.5:
            return DreamDepth.FAST
        return DreamDepth.INSTINCT

    def select_action(self, state: OWMState, task: str) -> Dict:
        urgency = self._assess_urgency(task)
        importance = self._assess_importance(task)
        depth = self.route(state, urgency, importance)

        if depth in (DreamDepth.DEEP, DreamDepth.CRITICAL):
            if self.daily_deep_dreams < self.max_deep_dreams:
                self.daily_deep_dreams += 1
            futures = self.owm.dream(state, deep=(depth == DreamDepth.CRITICAL))
            best = _select_best_future(futures)
            budget_exceeded = self.owm.available and self.owm.dream_count >= self.owm.max_free_dreams
            if budget_exceeded:
                depth = DreamDepth.FAST  # fell back but report intent honestly
        elif depth == DreamDepth.FAST:
            if self.local_engine is not None:
                try:
                    best = self.local_engine.dream(prompt=f"[SOVOS FAST dream] {task}", state=state)
                except Exception:
                    best = _fallback_outcome(state, label="fast_local")
            else:
                best = _fallback_outcome(state, label="fast_local")
        else:
            best = _fallback_outcome(state, label="instinct")

        # G-block: governance score too low -> hard block, escalate to human.
        if best.gspc.get("G", 0.0) < 0.5:
            return {
                "action": "BLOCKED",
                "reason": "Governance score too low",
                "gspc": best.gspc,
                "fallback": "ESCALATE_TO_HUMAN",
                "depth": depth.value,
            }
        return {
            "action": best.recommended_action or "NO_ACTION",
            "scenario_id": best.scenario_id,
            "probability": best.probability,
            "gspc": best.gspc,
            "depth": depth.value,
        }

    @staticmethod
    def _assess_urgency(task: str) -> float:
        t = task.lower()
        if any(k in t for k in ("security", "breach", "incident")):
            return 1.0
        if any(k in t for k in ("humanoid", "robot")):
            return 0.9
        if "compliance" in t:
            return 0.7
        return 0.3

    @staticmethod
    def _assess_importance(task: str) -> float:
        t = task.lower()
        if any(k in t for k in ("governance", "certification", "audit")):
            return 1.0
        if any(k in t for k in ("revenue", "customer", "contract")):
            return 0.8
        return 0.5


def governed_score(state: OWMState) -> GSPCScore:
    """Stamp the OWM state's governance record with a full GSPC score."""
    record = {k.lower(): v for k, v in state.gspc_current.items()}
    return score_gspc(record)


__all__ = [
    "DreamDepth", "DreamOutcome", "OWMState",
    "NemotronOWM", "OWMRouter", "select_best_future",
    "_select_best_future", "governed_score",
]
