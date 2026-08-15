"""FishKeeperAgent — koi farm water-quality monitor.

Skills:
- read_sensors(): returns current pH, ammonia, temperature, dissolved O2
- check_health(): returns green/amber/red status + reason
- dispatch_alert(): hires MuckAway for emergency water change

Triggers (per SOVOS brief):
- pH < 6.0 or > 9.0 → red
- ammonia_ppm > 0.5 → red
- temperature < 5°C or > 30°C → red
- otherwise: green

Real FishKeeper.ai is more complex — this is a minimal honest demo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ..signing import attach_signature


@dataclass
class PondReading:
    """A single water-quality reading from a pond sensor."""
    pond_id: str
    ph: float
    ammonia_ppm: float
    temperature_c: float
    dissolved_oxygen_mg_l: float


@dataclass
class HealthVerdict:
    """The agent's assessment of a pond's current state."""
    pond_id: str
    status: str  # "green" | "amber" | "red"
    reasons: List[str] = field(default_factory=list)
    task_vector: List[float] = field(default_factory=list)


class FishKeeperAgent:
    """The koi farm water-quality monitoring agent."""

    def __init__(self, name: str = "fishkeeper-001") -> None:
        self.name = name
        self.readings: Dict[str, PondReading] = {}
        self.decisions: List[Dict[str, Any]] = []

    def ingest_reading(self, reading: PondReading) -> Dict[str, Any]:
        """A sensor pushes a reading into the agent."""
        self.readings[reading.pond_id] = reading
        result = {
            "agent": self.name,
            "action": "ingest_reading",
            "pond_id": reading.pond_id,
            "ingested_at": len(self.readings),
        }
        return attach_signature(result)

    def check_health(self, pond_id: str) -> Dict[str, Any]:
        """Assess the current state of one pond."""
        if pond_id not in self.readings:
            result = {
                "agent": self.name,
                "action": "check_health",
                "pond_id": pond_id,
                "status": "unknown",
                "reason": f"no reading available for pond {pond_id}",
            }
            return attach_signature(result)
        r = self.readings[pond_id]
        reasons = []
        # pH
        if r.ph < 6.0 or r.ph > 9.0:
            reasons.append(f"pH {r.ph} outside safe range 6.0-9.0")
        # ammonia
        if r.ammonia_ppm > 0.5:
            reasons.append(f"ammonia {r.ammonia_ppm} ppm exceeds 0.5 ppm safe limit")
        elif r.ammonia_ppm > 0.25:
            reasons.append(f"ammonia {r.ammonia_ppm} ppm approaching 0.5 ppm safe limit")
        # temperature
        if r.temperature_c < 5.0 or r.temperature_c > 30.0:
            reasons.append(f"temperature {r.temperature_c}°C outside 5-30°C range")
        # dissolved oxygen
        if r.dissolved_oxygen_mg_l < 5.0:
            reasons.append(f"dissolved O₂ {r.dissolved_oxygen_mg_l} mg/L below 5 mg/L minimum")
        # status
        if any("outside" in x or "exceeds" in x or "below" in x for x in reasons):
            status = "red"
        elif reasons:
            status = "amber"
        else:
            status = "green"
            reasons = ["all parameters within safe ranges"]
        # task vector (8 dims): [ph_norm, ammonia_norm, temp_norm, do_norm, ...]
        task_vector = [
            min(1.0, max(0.0, (r.ph - 5.0) / 5.0)),      # 0 at pH 5, 1 at pH 10
            1.0 - min(1.0, r.ammonia_ppm / 1.0),          # 1 at ammonia 0, 0 at ammonia 1
            min(1.0, max(0.0, (r.temperature_c - 0.0) / 35.0)),
            min(1.0, r.dissolved_oxygen_mg_l / 10.0),
            1.0 if status == "green" else 0.5 if status == "amber" else 0.0,
            1.0 if r.ammonia_ppm > 0.5 else 0.0,
            1.0 if (r.ph < 6.0 or r.ph > 9.0) else 0.0,
            1.0 if (r.temperature_c < 5.0 or r.temperature_c > 30.0) else 0.0,
        ]
        self.decisions.append({
            "action": "check_health",
            "pond_id": pond_id,
            "status": status,
            "reasons": reasons,
        })
        result = {
            "agent": self.name,
            "action": "check_health",
            "pond_id": pond_id,
            "status": status,
            "reasons": reasons,
            "task_vector": task_vector,
        }
        return attach_signature(result)

    def skills(self) -> Dict[str, Any]:
        """Return the public skill manifest."""
        return {
            "agent": self.name,
            "type": "water-quality-monitor",
            "skills": [
                {"name": "ingest_reading", "params": ["pond_id", "ph", "ammonia_ppm", "temperature_c", "dissolved_oxygen_mg_l"]},
                {"name": "check_health", "params": ["pond_id"]},
            ],
            "pricing": {
                "check_health": "£0.05 per call",
                "ingest_reading": "£0.01 per call",
            },
        }


__all__ = ["FishKeeperAgent", "PondReading", "HealthVerdict"]
