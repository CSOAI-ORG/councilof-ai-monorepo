"""
sovos/core/state.py
Shared State Bus — The One Mind Memory
All layers read/write to this unified state fabric.
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np


@dataclass
class StateVector:
    """A d-dimensional state vector representing any entity in SAVOS space."""
    id: str
    tensor: np.ndarray
    layer: str  # "water", "milk", "honey", "quantum"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    coherence: float = 1.0  # 1.0 = fully coherent, 0.0 = decohered

    def normalize(self) -> "StateVector":
        norm = np.linalg.norm(self.tensor)
        if norm > 0:
            self.tensor = self.tensor / norm
        return self

    def amplitude_encode(self) -> np.ndarray:
        """Prepare for quantum amplitude encoding."""
        flat = self.tensor.flatten()
        # Pad to power of 2 for qubit allocation
        n = 2 ** int(np.ceil(np.log2(len(flat))))
        padded = np.zeros(n, dtype=np.complex128)
        padded[:len(flat)] = flat.astype(np.complex128)
        padded = padded / np.linalg.norm(padded)
        return padded


class StateBus:
    """
    Unified memory fabric for SOVOS.
    All agents, MCPs, A2A messages, and quantum states flow through here.
    This is the "One Mind" — everything is addressable as a state vector.
    """
    _instance: Optional["StateBus"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "StateBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._vectors: Dict[str, StateVector] = {}
            cls._instance._subscribers: List[Callable[[StateVector], None]] = []
            cls._instance._history: List[str] = []
        return cls._instance

    async def write(self, vector: StateVector) -> None:
        async with self._lock:
            self._vectors[vector.id] = vector
            self._history.append(f"{vector.timestamp.isoformat()} | {vector.layer} | {vector.id}")
            for cb in self._subscribers:
                try:
                    cb(vector)
                except Exception:
                    pass

    async def read(self, vid: str) -> Optional[StateVector]:
        async with self._lock:
            return self._vectors.get(vid)

    async def query_layer(self, layer: str) -> List[StateVector]:
        async with self._lock:
            return [v for v in self._vectors.values() if v.layer == layer]

    def subscribe(self, callback: Callable[[StateVector], None]) -> None:
        self._subscribers.append(callback)

    def get_history(self, n: int = 100) -> List[str]:
        return self._history[-n:]

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Export entire mind state as serializable dict."""
        return {
            vid: {
                "id": v.id,
                "layer": v.layer,
                "shape": v.tensor.shape,
                "coherence": v.coherence,
                "timestamp": v.timestamp.isoformat(),
                "metadata": v.metadata,
            }
            for vid, v in self._vectors.items()
        }


@dataclass
class MindIntent:
    """A distilled intent ready for execution."""
    intent_id: str
    source: str
    action: str
    target: Optional[str] = None
    params: dict = field(default_factory=dict)
    confidence: float = 0.0
    quantum_enhanced: bool = False
