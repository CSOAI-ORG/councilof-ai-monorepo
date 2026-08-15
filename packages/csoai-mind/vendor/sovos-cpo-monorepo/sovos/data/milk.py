"""
sovos/data/milk.py
Vector processing. Milk = structured, embedded, nourishing.
Task vectors, embeddings, OWEM hive operations.
"""
from __future__ import annotations
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np

from sovos.core.state import StateBus, StateVector


class MilkProcessor:
    """
    Transforms water into milk: raw data → task vectors → OWEM hives.
    This is where your 3KB mathematics lives.
    """
    def __init__(self, bus: StateBus, embedding_dim: int = 512) -> None:
        self.bus = bus
        self.embedding_dim = embedding_dim
        self.processing_log: List[str] = []
        # OWEM hive projection matrices (frozen-fluid stacks)
        self.projections = {
            "left": np.random.randn(embedding_dim, embedding_dim).astype(np.float32),
            "right": np.random.randn(embedding_dim, embedding_dim).astype(np.float32),
            "small": np.random.randn(embedding_dim, embedding_dim).astype(np.float32),
            "big": np.random.randn(embedding_dim, embedding_dim).astype(np.float32),
        }
        # Normalize projections
        for k in self.projections:
            self.projections[k] = self.projections[k] / np.linalg.norm(self.projections[k], axis=0, keepdims=True)

    async def process(self, water_vec: StateVector) -> str:
        """Transform water vector into milk (task vector)."""
        # Expand sparse water fingerprint to dense embedding
        milk_tensor = np.matmul(
            water_vec.tensor[:self.embedding_dim] if len(water_vec.tensor) >= self.embedding_dim
            else np.pad(water_vec.tensor, (0, self.embedding_dim - len(water_vec.tensor))),
            self.projections["left"],  # Initial projection
        )
        milk_tensor = milk_tensor / (np.linalg.norm(milk_tensor) + 1e-9)

        vid = f"milk.{water_vec.id}.{datetime.utcnow().timestamp()}"
        milk_vec = StateVector(
            id=vid,
            tensor=milk_tensor,
            layer="milk",
            metadata={
                "parent_water": water_vec.id,
                "embedding_dim": self.embedding_dim,
                "projections_used": ["left"],
            },
        )
        await self.bus.write(milk_vec)
        self.processing_log.append(vid)
        return vid

    async def hive_transform(self, milk_vec: StateVector, mode: str = "frozen") -> StateVector:
        """
        OWEM hive operation: transform task vector through frozen-fluid stack.
        mode: "frozen" (stable), "fluid" (adaptive), "left", "right", "small", "big"
        """
        if mode in self.projections:
            transformed = np.matmul(milk_vec.tensor, self.projections[mode])
        elif mode == "frozen":
            # Stable: average all projections
            stacked = np.stack([self.projections[k] for k in self.projections], axis=0)
            mean_proj = np.mean(stacked, axis=0)
            transformed = np.matmul(milk_vec.tensor, mean_proj)
        elif mode == "fluid":
            # Adaptive: weighted by current coherence
            weights = np.array([0.4, 0.3, 0.2, 0.1])  # left, right, small, big
            stacked = np.stack([self.projections[k] for k in ["left", "right", "small", "big"]], axis=0)
            weighted = np.tensordot(weights, stacked, axes=([0], [0]))
            transformed = np.matmul(milk_vec.tensor, weighted)
        else:
            transformed = milk_vec.tensor

        transformed = transformed / (np.linalg.norm(transformed) + 1e-9)
        milk_vec.tensor = transformed
        milk_vec.metadata["hive_mode"] = mode
        await self.bus.write(milk_vec)
        return milk_vec

    async def maintain_coherence(self) -> None:
        """
        Background coherence maintenance — like XY8 dynamical decoupling for qubits.
        Prevents task vector drift (decoherence) over time.
        """
        milk_vectors = await self.bus.query_layer("milk")
        for vec in milk_vectors:
            if vec.coherence < 0.95:
                # Re-normalize and boost coherence
                vec.normalize()
                vec.coherence = min(1.0, vec.coherence + 0.05)
                vec.metadata["last_coherence_refresh"] = datetime.utcnow().isoformat()
                await self.bus.write(vec)
