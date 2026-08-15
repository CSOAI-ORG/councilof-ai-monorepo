"""sovos-core/layer0.py — Layer 0 substrate.

Layer 0 is the substrate everything else sits on:
- CPOLink: a photonic interconnect channel (silicon photonics, 9W/link
  vs 30W for pluggable optics, ns latency)
- MCPTool: an MCP tool endpoint with a capability_vector for semantic
  routing
- A2AAgent: an agent (your GPU cluster, an edge node, a watchdog) with
  its own state_vector and a set of MCP tools it can call
- Layer0Fabric: the registry that holds all of the above and resolves
  "given this state_vector, which MCP tool should handle it?"

Honest scope:
- No real CPO hardware. CPOLink is a model with the published power/latency
  numbers from NVIDIA CPO datasheets (30W → 9W).
- No real A2A protocol implementation (Google's A2A spec needs study).
- Capability vectors are deterministic, not learned.
"""
from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# CPOLink — modeled after NVIDIA co-packaged optics datasheets
# ---------------------------------------------------------------------------
@dataclass
class CPOLink:
    """A photonic interconnect link between two agents / racks / cores.

    Honest numbers (from NVIDIA CPO publications 2026):
    - Conventional pluggable optical transceiver: ~30 W per 1.6T link
    - CPO (silicon photonics co-packaged): ~9 W per 1.6T link
    - Latency improvement: tens to hundreds of nanoseconds

    This is a MODEL with those numbers — not a hardware driver.
    """
    link_id: str
    source: str
    target: str
    bandwidth_gbps: float = 1600.0      # 1.6T
    is_quantum: bool = False            # hybrid classical + quantum
    power_w: float = 9.0                # CPO default
    latency_ns: float = 50.0

    def power_savings_vs_pluggable(self) -> Dict[str, float]:
        """Compare against 30 W pluggable baseline (NVIDIA CPO datasheet)."""
        baseline_w = 30.0
        saved_w = baseline_w - self.power_w
        return {
            "cpo_power_w": self.power_w,
            "pluggable_baseline_w": baseline_w,
            "power_saved_w": saved_w,
            "power_reduction_pct": 100.0 * saved_w / baseline_w,
        }


# ---------------------------------------------------------------------------
# MCPTool — capability-vector-routed MCP endpoint
# ---------------------------------------------------------------------------
@dataclass
class MCPTool:
    """An MCP tool the mind can call.

    capability_vector: a vector embedding the tool's function. The mind
    routes a state_vector to the tool with the highest cosine similarity.
    """
    tool_id: str
    name: str
    description: str
    capability_vector: List[float]   # normalised, length chosen by caller
    handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

    def match_score(self, query_vector: List[float]) -> float:
        """Cosine similarity between this tool and a query vector."""
        a = self.capability_vector
        b = list(query_vector)
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


# ---------------------------------------------------------------------------
# A2AAgent — agent registered on the fabric
# ---------------------------------------------------------------------------
@dataclass
class A2AAgent:
    """An agent (GPU cluster, edge node, watchdog, oracle) on the fabric.

    Every agent carries its own state_vector (its current internal state)
    and a list of MCP tools it can call. Messages between agents flow
    through the StateBus as StateVectors with layer='control'.
    """
    agent_id: str
    name: str
    role: str                       # "gpu-cluster" | "edge" | "watchdog" | "oracle" | ...
    state_vector: List[float]
    tools: List[str] = field(default_factory=list)   # tool_ids it can call
    endpoint: str = "local"        # where it lives ("local" | "remote:url")


# ---------------------------------------------------------------------------
# Layer0Fabric — the substrate registry
# ---------------------------------------------------------------------------
class Layer0Fabric:
    """The substrate. Holds CPOLinks, MCPTools, A2AAgents, and resolves
    routing: given a state_vector, which tool handles it best?"""
    def __init__(self):
        self.links: Dict[str, CPOLink] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.agents: Dict[str, A2AAgent] = {}
        self._total_cpo_savings = 0.0
        self._total_pluggable_baseline = 0.0

    def register_link(self, link: CPOLink) -> str:
        self.links[link.link_id] = link
        savings = link.power_savings_vs_pluggable()
        self._total_cpo_savings += savings["power_saved_w"]
        self._total_pluggable_baseline += savings["pluggable_baseline_w"]
        return link.link_id

    def register_tool(self, tool: MCPTool) -> str:
        self.tools[tool.tool_id] = tool
        return tool.tool_id

    def register_agent(self, agent: A2AAgent) -> str:
        self.agents[agent.agent_id] = agent
        return agent.agent_id

    def route(self, query_vector: List[float],
              allowed_tool_ids: Optional[List[str]] = None) -> Optional[MCPTool]:
        """Find the best-matching tool for `query_vector`."""
        candidates = []
        for tid, tool in self.tools.items():
            if allowed_tool_ids is not None and tid not in allowed_tool_ids:
                continue
            candidates.append((tool.match_score(query_vector), tool))
        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    def cpo_savings_summary(self) -> Dict[str, Any]:
        return {
            "n_links": len(self.links),
            "n_tools": len(self.tools),
            "n_agents": len(self.agents),
            "cumulative_power_saved_w": self._total_cpo_savings,
            "cumulative_baseline_w": self._total_pluggable_baseline,
            "reduction_pct": (
                100.0 * self._total_cpo_savings / self._total_pluggable_baseline
                if self._total_pluggable_baseline > 0 else 0.0
            ),
        }


__all__ = ["CPOLink", "MCPTool", "A2AAgent", "Layer0Fabric"]