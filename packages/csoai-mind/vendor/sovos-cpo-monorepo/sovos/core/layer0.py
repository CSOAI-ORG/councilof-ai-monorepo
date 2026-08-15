"""
sovos/core/layer0.py
Layer 0 — The Photonic Fabric
MCP + A2A + CPO unified as one substrate.
All tools, all agents, all data move through light-speed vectors.
"""
from __future__ import annotations
import asyncio
import json
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import httpx
import numpy as np

from sovos.core.state import StateBus, StateVector


@dataclass
class CPOLink:
    """
    Co-Packaged Optic Link abstraction.
    Represents a photonic channel between compute nodes.
    Power: ~9W (vs 30W pluggable). Latency: nanoseconds.
    """
    link_id: str
    source: str      # e.g., "sov1.edge", "gpu.cluster.a", "quantum.saxonq"
    target: str
    bandwidth_tbps: float = 1.6
    power_watts: float = 9.0
    latency_ns: float = 50.0
    active: bool = True
    photonic_mode: str = "classical"  # "classical" | "quantum" | "hybrid"

    async def transmit(self, vector: StateVector) -> bool:
        """Transmit a state vector as photonic signal."""
        if not self.active:
            return False
        # In production: encode vector amplitudes onto optical carrier
        # Here: simulate sub-microsecond transit
        await asyncio.sleep(self.latency_ns / 1e9)
        return True


@dataclass
class MCPTool:
    """An MCP tool registered in the Layer 0 fabric."""
    name: str
    endpoint: str
    schema: Dict[str, Any] = field(default_factory=dict)
    capability_vector: Optional[np.ndarray] = None  # Task vector for this tool
    health: bool = True

    async def invoke(self, params: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    self.endpoint,
                    json={"tool": self.name, "params": params}
                )
                return resp.json()
            except Exception as e:
                return {"error": str(e), "tool": self.name}


@dataclass
class A2AAgent:
    """An Agent-to-Agent entity in the SOVOS swarm."""
    agent_id: str
    role: str  # "watchdog", "analyst", "gamer", "farmer", "oracle"
    endpoint: Optional[str] = None
    state_vector: Optional[np.ndarray] = None
    peers: List[str] = field(default_factory=list)

    async def send(self, target: A2AAgent, message: Dict[str, Any]) -> None:
        """A2A communication via photonic link."""
        payload = {
            "from": self.agent_id,
            "to": target.agent_id,
            "role": self.role,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": message,
        }
        if target.endpoint:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(target.endpoint, json=payload)
        # Also write to StateBus for unified memory
        bus = StateBus()
        vec = StateVector(
            id=f"a2a.{self.agent_id}.{target.agent_id}.{datetime.utcnow().timestamp()}",
            tensor=np.array([hash(json.dumps(payload, sort_keys=True)) % 1e6]),
            layer="milk",
            metadata=payload,
        )
        await bus.write(vec)


class Layer0Fabric:
    """
    Layer 0 — The substrate of SOVOS.
    Manages CPO links, MCP tools, and A2A agents as one photonic mesh.
    """
    def __init__(self) -> None:
        self.bus = StateBus()
        self.links: Dict[str, CPOLink] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.agents: Dict[str, A2AAgent] = {}
        self._running = False

    def register_link(self, link: CPOLink) -> None:
        self.links[link.link_id] = link

    def register_tool(self, tool: MCPTool) -> None:
        self.tools[tool.name] = tool

    def register_agent(self, agent: A2AAgent) -> None:
        self.agents[agent.agent_id] = agent

    async def route_vector(self, vector: StateVector, target_node: str) -> bool:
        """Route a state vector through the photonic fabric to a target node."""
        # Find best CPO link
        candidates = [
            l for l in self.links.values()
            if l.target == target_node and l.active
        ]
        if not candidates:
            return False
        best = min(candidates, key=lambda x: x.latency_ns)
        ok = await best.transmit(vector)
        if ok:
            vector.metadata["cpo_link"] = best.link_id
            vector.metadata["latency_ns"] = best.latency_ns
            await self.bus.write(vector)
        return ok

    async def invoke_mcp(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool {tool_name} not registered in Layer 0"}
        # Create task vector for this invocation
        task_vec = StateVector(
            id=f"mcp.{tool_name}.{datetime.utcnow().timestamp()}",
            tensor=tool.capability_vector if tool.capability_vector is not None else np.random.randn(128),
            layer="milk",
            metadata={"tool": tool_name, "params": params},
        )
        await self.bus.write(task_vec)
        result = await tool.invoke(params)
        # Write result back as honey
        honey_vec = StateVector(
            id=f"mcp.result.{tool_name}.{datetime.utcnow().timestamp()}",
            tensor=np.array([len(json.dumps(result))]),
            layer="honey",
            metadata={"tool": tool_name, "result": result},
        )
        await self.bus.write(honey_vec)
        return result

    async def a2a_broadcast(self, sender_id: str, message: Dict[str, Any]) -> None:
        sender = self.agents.get(sender_id)
        if not sender:
            return
        for peer_id in sender.peers:
            peer = self.agents.get(peer_id)
            if peer:
                await sender.send(peer, message)

    def fabric_status(self) -> Dict[str, Any]:
        return {
            "links": {k: {"power_w": v.power_watts, "latency_ns": v.latency_ns, "mode": v.photonic_mode}
                      for k, v in self.links.items()},
            "tools": list(self.tools.keys()),
            "agents": {k: {"role": v.role, "peers": v.peers} for k, v in self.agents.items()},
            "bus_vectors": len(self.bus._vectors),
        }
