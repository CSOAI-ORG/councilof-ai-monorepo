"""
sovos/agents/mcp.py
MCP (Model Context Protocol) integration for SOVOS.
Every tool is a photonic endpoint. Every call is a state vector transmission.
"""
from __future__ import annotations
from typing import Any, Dict, List
from dataclasses import dataclass
import numpy as np

from sovos.core.state import StateBus, StateVector


@dataclass
class MCPServerConfig:
    name: str
    endpoint: str
    tools: List[str] = None
    capability_embedding: np.ndarray = None


class MCPRegistry:
    """
    Registry of all MCP servers in the SOVOS ecosystem.
    Each server is mapped to a capability vector for semantic routing.
    """
    def __init__(self, bus: StateBus) -> None:
        self.bus = bus
        self.servers: Dict[str, MCPServerConfig] = {}

    def register(self, config: MCPServerConfig) -> None:
        self.servers[config.name] = config
        # Write capability vector to bus
        if config.capability_embedding is not None:
            vec = StateVector(
                id=f"mcp.server.{config.name}",
                tensor=config.capability_embedding,
                layer="milk",
                metadata={"type": "mcp_server", "endpoint": config.endpoint, "tools": config.tools},
            )
            import asyncio
            asyncio.create_task(self.bus.write(vec))

    def find_server(self, intent_vector: np.ndarray, top_k: int = 3) -> List[str]:
        """Semantic routing: find best MCP server for a given intent vector."""
        scores = []
        for name, config in self.servers.items():
            if config.capability_embedding is not None:
                sim = np.dot(intent_vector, config.capability_embedding)
                scores.append((name, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in scores[:top_k]]

    def list_tools(self) -> Dict[str, List[str]]:
        return {name: config.tools or [] for name, config in self.servers.items()}
