"""
sovos/data/water.py
Raw ingestion. Water = unstructured, unrefined, abundant.
Everything enters here: APIs, logs, sensors, user input, game telemetry.
"""
from __future__ import annotations
import json
import hashlib
from typing import Any, Dict, List
from datetime import datetime
import numpy as np

from sovos.core.state import StateBus, StateVector


class WaterIngestion:
    """
    Ingests raw data from any source and stores it as water-layer state vectors.
    No processing yet — just capture and normalize.
    """
    def __init__(self, bus: StateBus) -> None:
        self.bus = bus
        self.ingestion_log: List[str] = []

    async def ingest(self, source: str, raw_data: Any, metadata: Dict[str, Any] = None) -> str:
        """Ingest raw data. Returns vector ID."""
        # Serialize raw data to bytes
        if isinstance(raw_data, (dict, list)):
            raw_bytes = json.dumps(raw_data, sort_keys=True).encode()
        elif isinstance(raw_data, str):
            raw_bytes = raw_data.encode()
        elif isinstance(raw_data, np.ndarray):
            raw_bytes = raw_data.tobytes()
        else:
            raw_bytes = str(raw_data).encode()

        # Create a hash-based fingerprint vector
        h = hashlib.sha256(raw_bytes).hexdigest()
        # Convert hash to a high-dimensional but sparse vector
        vec = np.zeros(1024, dtype=np.float32)
        for i, char in enumerate(h[:64]):
            vec[i % 1024] += ord(char)
        vec = vec / (np.linalg.norm(vec) + 1e-9)

        vid = f"water.{source}.{h[:16]}.{datetime.utcnow().timestamp()}"
        vector = StateVector(
            id=vid,
            tensor=vec,
            layer="water",
            metadata={
                "source": source,
                "size_bytes": len(raw_bytes),
                "raw_type": type(raw_data).__name__,
                **(metadata or {}),
            },
        )
        await self.bus.write(vector)
        self.ingestion_log.append(vid)
        return vid

    async def ingest_batch(self, items: List[Dict[str, Any]]) -> List[str]:
        """Ingest multiple water streams."""
        vids = []
        for item in items:
            vid = await self.ingest(
                item.get("source", "unknown"),
                item.get("data"),
                item.get("metadata", {}),
            )
            vids.append(vid)
        return vids
