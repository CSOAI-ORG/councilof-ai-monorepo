"""sovos-core/data/water.py — Raw data ingestion.

WaterIngestion accepts any source (sensors, APIs, user input, farm logs)
and produces a StateVector on the "water" layer of the StateBus.

Honest: this is a normaliser + vectoriser. It does NOT do ML — it just
turns heterogeneous input into a consistent (vector, payload) tuple.
The "OWEM hive" transforms water into milk in milk.py.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .state import StateBus, StateVector


@dataclass
class IngestionSource:
    """A registered ingestion source."""
    source_id: str               # "iokfarm.sensors"
    description: str
    schema_hint: Optional[str]   # what kind of data this carries


class WaterIngestion:
    """Turns raw inputs into StateVector (water layer) entries on the bus."""
    def __init__(self, bus: StateBus, vector_dim: int = 8):
        self.bus = bus
        self.vector_dim = vector_dim
        self.sources: Dict[str, IngestionSource] = {}

    def register_source(self, source: IngestionSource) -> str:
        self.sources[source.source_id] = source
        return source.source_id

    def ingest(self, source_id: str, raw_payload: Dict[str, Any]) -> str:
        """Ingest a raw payload from `source_id`. Returns sv_id."""
        if source_id not in self.sources:
            raise ValueError(f"unknown source: {source_id}")
        vec = self._payload_to_vector(raw_payload)
        sv = StateVector(
            source=source_id,
            layer="water",
            vector=vec,
            payload=raw_payload,
        )
        return self.bus.append(sv)

    def _payload_to_vector(self, payload: Dict[str, Any]) -> List[float]:
        """Deterministic hash-based vectoriser. Real impl: learned embedding.

        We hash (key, value) pairs into fixed-dim buckets. Two payloads
        with the same keys + values produce the same vector.
        """
        h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).digest()
        # Repeat hash to fill vector_dim bytes
        out = []
        i = 0
        while len(out) < self.vector_dim:
            out.append((h[i % len(h)] - 128) / 128.0)  # normalise to [-1, 1]
            i += 1
        return out


__all__ = ["IngestionSource", "WaterIngestion"]