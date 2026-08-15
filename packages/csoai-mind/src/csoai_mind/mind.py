"""sovos-core/mind.py — Unified Orchestrator (One Mind).

SovosMind is the facade. It holds the StateBus + Layer0Fabric + the
three pipeline stages (Water → Milk → Honey) and exposes one method:
`think(source_id, raw_payload)` runs the full pipeline and returns the
honey decision.

This is the file that turns the four modules into a usable system.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .state import StateBus, StateVector
from .layer0 import Layer0Fabric, MCPTool, A2AAgent, CPOLink
from .water import WaterIngestion, IngestionSource
from .milk import MilkProcessor, HiveConfig
from .honey import HoneyDistiller, Decision


@dataclass
class ThinkResult:
    """Result of one mind.think() call."""
    source_id: str
    water_sv_id: str
    milk_sv_id: str
    honey_sv_id: str
    decision: Decision
    bus_stats: Dict[str, int]


class SovosMind:
    """One mind. Water → Milk → Honey."""
    def __init__(self, fabric: Optional[Layer0Fabric] = None,
                 vector_dim: int = 8,
                 hive_config: Optional[HiveConfig] = None,
                 confidence_threshold: float = 0.1):
        self.bus = StateBus()
        self.fabric = fabric or Layer0Fabric()
        self.water = WaterIngestion(self.bus, vector_dim=vector_dim)
        self.milk = MilkProcessor(self.bus, config=hive_config)
        self.honey = HoneyDistiller(self.bus, self.fabric,
                                     confidence_threshold=confidence_threshold)

    # Convenience: register a source / tool / agent
    def register_source(self, source: IngestionSource) -> str:
        return self.water.register_source(source)

    def register_tool(self, tool: MCPTool) -> str:
        return self.fabric.register_tool(tool)

    def register_agent(self, agent: A2AAgent) -> str:
        return self.fabric.register_agent(agent)

    def register_link(self, link: CPOLink) -> str:
        return self.fabric.register_link(link)

    def think(self, source_id: str, raw_payload: Dict[str, Any]) -> ThinkResult:
        """Run the full pipeline: water → milk → honey → return decision."""
        # Auto-register unknown sources with a generic schema. Real callers
        # should call register_source() first to set description + schema.
        if source_id not in self.water.sources:
            self.water.register_source(IngestionSource(
                source_id=source_id, description="auto-registered",
                schema_hint="unknown",
            ))
        water_id = self.water.ingest(source_id, raw_payload)
        water_sv = self._by_id(water_id)
        milk_id = self.milk.process(water_sv)
        milk_sv = self._by_id(milk_id)
        honey_id = self.honey.distill(milk_sv)
        honey_sv = self._by_id(honey_id)
        decision = Decision(**honey_sv.payload["decision"])
        return ThinkResult(
            source_id=source_id,
            water_sv_id=water_id,
            milk_sv_id=milk_id,
            honey_sv_id=honey_id,
            decision=decision,
            bus_stats=self.bus.stats(),
        )

    def _by_id(self, sv_id: str) -> StateVector:
        for sv in self.bus.read_all():
            if sv.sv_id == sv_id:
                return sv
        raise KeyError(sv_id)

    def stats(self) -> Dict[str, Any]:
        return {
            "bus": self.bus.stats(),
            "fabric": self.fabric.cpo_savings_summary(),
        }


__all__ = ["ThinkResult", "SovosMind"]