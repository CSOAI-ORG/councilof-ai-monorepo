"""
sovos/agents/a2a.py
Agent-to-Agent protocol for SOVOS swarm intelligence.
Agents communicate as state vectors through the photonic fabric.
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from sovos.core.state import StateBus, StateVector


@dataclass
class A2AMessage:
    msg_id: str
    from_agent: str
    to_agent: str
    msg_type: str  # "task", "query", "response", "heartbeat", "entanglement"
    payload: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[np.ndarray] = None  # Optional state vector attachment
    timestamp: datetime = field(default_factory=datetime.utcnow)


class A2ASwarm:
    """
    Agent-to-Agent swarm protocol.
    All agents share the StateBus — they are neurons in one mind.
    """
    def __init__(self, bus: StateBus) -> None:
        self.bus = bus
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.message_log: List[str] = []

    def register_agent(self, agent_id: str, role: str, endpoint: Optional[str] = None) -> None:
        self.agents[agent_id] = {"role": role, "endpoint": endpoint, "peers": []}

    def connect(self, agent_a: str, agent_b: str) -> None:
        """Create bidirectional peer link."""
        if agent_a in self.agents and agent_b in self.agents:
            self.agents[agent_a]["peers"].append(agent_b)
            self.agents[agent_b]["peers"].append(agent_a)

    async def send(self, msg: A2AMessage) -> None:
        """Transmit A2A message through the unified bus."""
        vec = StateVector(
            id=msg.msg_id,
            tensor=msg.vector if msg.vector is not None else np.random.randn(128),
            layer="milk",
            metadata={
                "type": "a2a_message",
                "from": msg.from_agent,
                "to": msg.to_agent,
                "msg_type": msg.msg_type,
                "payload": msg.payload,
                "timestamp": msg.timestamp.isoformat(),
            },
        )
        await self.bus.write(vec)
        self.message_log.append(msg.msg_id)

    async def broadcast(self, from_agent: str, msg_type: str, payload: Dict[str, Any]) -> None:
        """Broadcast to all peers of an agent."""
        agent = self.agents.get(from_agent)
        if not agent:
            return
        for peer_id in agent["peers"]:
            msg = A2AMessage(
                msg_id=f"a2a.{from_agent}.{peer_id}.{datetime.utcnow().timestamp()}",
                from_agent=from_agent,
                to_agent=peer_id,
                msg_type=msg_type,
                payload=payload,
            )
            await self.send(msg)

    async def heartbeat(self) -> None:
        """Periodic coherence pulse across the swarm."""
        for agent_id in self.agents:
            await self.broadcast(agent_id, "heartbeat", {"status": "alive", "coherence": 1.0})
