"""sovos-core/state.py — the StateBus (One Mind Memory).

Every agent, tool, quantum state, MCP message, A2A swarm packet, and
ingested data point in SOVOS exists as a StateVector in a single
StateBus. This is the "one memory fabric, one mind" primitive.

Design choices:
- In-process dict-backed bus (no DB, no Redis) — the persistence layer
  (gap #2 from the brief) is owner-gated.
- Every StateVector has a layer ∈ {"water", "milk", "honey", "action",
  "control"} so the pipeline is explicit.
- Every StateVector carries a vector field (task vector / capability
  vector / measurement vector) for semantic routing.
- Bus supports append + read-by-layer + subscribe (for the OWEM hive
  to consume new water without polling).
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class StateVector:
    """One unit of state in the SOVOS One Mind.

    Attributes:
        sv_id: unique content-hash id
        layer: which stage of the pipeline this lives in
        source: where it came from ("farm.sensors", "mcp:fishkeeper",
               "a2a:gpu-cluster", "quantum:circuit-7")
        vector: numerical representation (task vector, capability
                vector, or measurement probabilities)
        payload: structured data accompanying the vector (JSON-serialisable)
        ts: timestamp of creation
    """
    source: str
    layer: str             # "water" | "milk" | "honey" | "action" | "control"
    vector: List[float]     # the numerical state
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sv_id: str = ""

    def __post_init__(self):
        if not self.sv_id:
            body = json.dumps({
                "source": self.source, "layer": self.layer,
                "vector": self.vector, "payload": self.payload,
                "ts": self.ts,
            }, sort_keys=True, default=str).encode()
            self.sv_id = hashlib.sha256(body).hexdigest()[:16]


class StateBus:
    """Append-only log of StateVectors, indexed by layer and source.

    Subscribers receive callbacks whenever a new vector lands in a layer
    they care about — the OWEM hive's natural consumer interface.
    """
    def __init__(self):
        self._all: List[StateVector] = []
        self._by_layer: Dict[str, List[StateVector]] = defaultdict(list)
        self._by_source: Dict[str, List[StateVector]] = defaultdict(list)
        self._subscribers: Dict[str, List[Callable[[StateVector], None]]] = defaultdict(list)

    def append(self, sv: StateVector) -> str:
        """Append a StateVector to the bus. Returns its sv_id."""
        self._all.append(sv)
        self._by_layer[sv.layer].append(sv)
        self._by_source[sv.source].append(sv)
        for cb in self._subscribers.get(sv.layer, []):
            try:
                cb(sv)
            except Exception as e:
                # Subscribers must not break the bus.
                # Log silently (real impl would use a logger).
                pass
        return sv.sv_id

    def read_by_layer(self, layer: str) -> List[StateVector]:
        return list(self._by_layer.get(layer, []))

    def read_by_source(self, source: str) -> List[StateVector]:
        return list(self._by_source.get(source, []))

    def read_all(self) -> List[StateVector]:
        return list(self._all)

    def subscribe(self, layer: str, callback: Callable[[StateVector], None]) -> None:
        """Register a callback for new StateVectors in `layer`."""
        self._subscribers[layer].append(callback)

    def stats(self) -> Dict[str, int]:
        return {
            "total": len(self._all),
            "by_layer": {l: len(vs) for l, vs in self._by_layer.items()},
            "by_source_count": len(self._by_source),
            "subscribers": sum(len(cbs) for cbs in self._subscribers.values()),
        }


__all__ = ["StateVector", "StateBus"]