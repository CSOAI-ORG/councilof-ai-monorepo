"""sovos-core/data/honey.py — Distilled intents/decisions.

HoneyDistiller reads milk vectors from the bus, decides which MCP tool
should handle the underlying intent (via Layer0Fabric routing), and
produces a "honey" StateVector carrying the chosen tool + a confidence
score. The honey is what the caller acts on.

This is the "decision layer" — it turns task vectors into action plans.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .layer0 import Layer0Fabric
from .state import StateBus, StateVector


@dataclass
class Decision:
    """A distilled intent ready for execution."""
    target_tool_id: str
    confidence: float              # cosine similarity at routing time
    from_milk_sv_id: str
    reasoning: str = ""            # human-readable (debug)


class HoneyDistiller:
    """Routes milk vectors to a tool via the Layer0Fabric and writes
    the decision onto the bus as a 'honey' StateVector."""
    def __init__(self, bus: StateBus, fabric: Layer0Fabric,
                 confidence_threshold: float = 0.1):
        self.bus = bus
        self.fabric = fabric
        self.confidence_threshold = confidence_threshold

    def distill_all_milk(self) -> List[str]:
        """Process every milk vector on the bus. Returns sv_ids."""
        ids = []
        for m in self.bus.read_by_layer("milk"):
            ids.append(self.distill(m))
        return ids

    def distill(self, milk_sv: StateVector) -> str:
        """One milk → one honey."""
        # Pad/truncate milk vector to the routing dimension (the longest
        # tool capability vector registered on the fabric). This is what
        # makes routing work even when hive.transform changed dimensions.
        route_vec = self._canonical_vector(milk_sv.vector)
        tool = self.fabric.route(route_vec)
        if tool is None:
            target = "none"
            conf = 0.0
            reasoning = "no tool matched"
        else:
            target = tool.tool_id
            conf = tool.match_score(route_vec)
            reasoning = (f"tool '{tool.tool_id}' (capability '{tool.name}') "
                         f"matched with cosine={conf:.3f}")
        decision = Decision(
            target_tool_id=target,
            confidence=conf,
            from_milk_sv_id=milk_sv.sv_id,
            reasoning=reasoning,
        )
        sv = StateVector(
            source=milk_sv.source,
            layer="honey",
            vector=milk_sv.vector,    # carry the underlying vector through
            payload={
                "decision": decision.__dict__,
                "from_milk": milk_sv.sv_id,
            },
        )
        return self.bus.append(sv)

    def _canonical_vector(self, v: List[float]) -> List[float]:
        """Pad/truncate to the longest tool capability vector's dim.

        If no tools registered, returns v as-is.
        """
        if not self.fabric.tools:
            return v
        target_dim = max(len(t.capability_vector) for t in self.fabric.tools.values())
        if len(v) >= target_dim:
            return v[:target_dim]
        return v + [0.0] * (target_dim - len(v))


__all__ = ["Decision", "HoneyDistiller"]