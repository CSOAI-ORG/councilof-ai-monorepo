"""
sovos/data/honey.py
Distilled insight. Honey = concentrated, valuable, actionable.
The final distillation layer before execution.
"""
from __future__ import annotations
from typing import Any, Dict
from datetime import datetime
import numpy as np

from sovos.core.state import StateBus, StateVector
from sovos.core.state import MindIntent


class HoneyDistiller:
    """
    Distills milk vectors into executable intents.
    This is where decisions are made. Quantum enhancement optional.
    """
    def __init__(self, bus: StateBus) -> None:
        self.bus = bus
        self.distillation_log: List[str] = []
        # Action prototypes as vectors
        self.action_prototypes = {
            "mcp.invoke": np.random.randn(512).astype(np.float32),
            "a2a.broadcast": np.random.randn(512).astype(np.float32),
            "quantum.submit": np.random.randn(512).astype(np.float32),
            "noop": np.random.randn(512).astype(np.float32),
        }
        for k in self.action_prototypes:
            self.action_prototypes[k] = self.action_prototypes[k] / np.linalg.norm(self.action_prototypes[k])

    async def distill(self, milk_vec: StateVector) -> MindIntent:
        """Find closest action prototype and build intent."""
        similarities = {}
        for action, proto in self.action_prototypes.items():
            sim = np.dot(milk_vec.tensor, proto)
            similarities[action] = sim

        best_action = max(similarities, key=similarities.get)
        confidence = float(similarities[best_action])

        intent = MindIntent(
            intent_id=f"honey.{milk_vec.id}.{datetime.utcnow().timestamp()}",
            source=milk_vec.metadata.get("parent_water", "unknown"),
            action=best_action,
            params={
                "milk_vector_id": milk_vec.id,
                "similarities": {k: float(v) for k, v in similarities.items()},
            },
            confidence=confidence,
            quantum_enhanced=milk_vec.metadata.get("quantum_enhanced", False),
        )

        # Write honey vector
        honey_vec = StateVector(
            id=intent.intent_id,
            tensor=np.array([confidence]),
            layer="honey",
            metadata={
                "action": best_action,
                "confidence": confidence,
                "parent_milk": milk_vec.id,
                "quantum_enhanced": intent.quantum_enhanced,
            },
        )
        await self.bus.write(honey_vec)
        self.distillation_log.append(intent.intent_id)
        return intent
