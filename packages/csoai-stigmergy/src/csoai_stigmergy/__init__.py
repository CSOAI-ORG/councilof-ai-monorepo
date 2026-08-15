"""csoai-stigmergy — indirect coordination via the StateBus.

v0.1.0 SCAFFOLD. Stigmergy = coordination through environment traces (ant
pheromones). In SOVOS, agents coordinate by writing to the StateBus and
subscribing to its layers. No direct A2A messages between agents — all
information flow happens through the shared environment.

Honest scope:
- The sovos-mind StateBus already supports `subscribe(layer, callback)`
  (verified from disk: state.py line 49-65). This module is a SCALFFOLD
  that demonstrates the stigmergy pattern with synthetic agents.
- The PheromoneTrail class wraps the StateBus with evaporation logic
  so old "scent" fades unless reinforced.
- The swarm demo shows 2 agents (forager, scout) coordinating without
  any direct messaging — the forager follows the trail, the scout
  reinforces it.

What this provides:
- Proof-of-concept for indirect coordination (the brief's Q3)
- Reusable PheromoneTrail wrapper around StateBus
- Tests that verify the stigmergy pattern actually works

What this is NOT:
- Not a replacement for direct A2A (sovos-a2a-swarm handles that)
- Not a real pheromone model (no decay constants from biology)
- Not production-ready: in-memory only, no persistence
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Use the real StateBus + StateVector from sovos-mind
import sys
from pathlib import Path

# Bootstrap sys.path so we can import sovos_mind
_SOVOS_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_SOVOS_ROOT / "sovos-mind" / "src"))

from sovos_mind.state import StateBus, StateVector


@dataclass
class Pheromone:
    """A stigmergic marker: a vector with an evaporation half-life.

    Stored as a StateVector on the bus. Reading it returns the current
    concentration (decayed). Writing reinforces it (resets decay timer).
    """
    sv_id: str
    vector: List[float]
    deposited_at: float            # wall-clock time
    concentration: float = 1.0    # 1.0 = fresh, decays toward 0
    half_life_seconds: float = 60.0  # time for concentration to halve
    metadata: Dict[str, Any] = field(default_factory=dict)

    def decay(self, now: Optional[float] = None) -> float:
        """Apply exponential decay and return the new concentration."""
        if now is None:
            now = time.time()
        elapsed = max(0.0, now - self.deposited_at)
        if self.half_life_seconds > 0:
            self.concentration = max(0.0, self.concentration * math.pow(0.5, elapsed / self.half_life_seconds))
        else:
            self.concentration = 0.0
        return self.concentration


class PheromoneTrail:
    """A stigmergic trail layer on the StateBus.

    Agents drop pheromones by writing a vector with a tag. Agents read
    pheromones by querying the layer. Concentration decays over time
    unless reinforced.
    """

    def __init__(self, bus: StateBus, layer: str = "pheromone", half_life_seconds: float = 60.0):
        self.bus = bus
        self.layer = layer
        self.half_life_seconds = half_life_seconds
        # In-memory cache of pheromone state (the bus stores the vectors)
        self._pheromones: Dict[str, Pheromone] = {}

    def deposit(self, source: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None) -> str:
        """Drop a pheromone at this location."""
        # Compute a content-hash id from source + vector
        import hashlib
        import json
        body = json.dumps({"source": source, "vector": vector, "ts": time.time()},
                          sort_keys=True, default=str).encode()
        sv_id = hashlib.sha256(body).hexdigest()[:16]
        meta = dict(metadata or {})
        meta["source"] = source
        meta["deposited_at"] = time.time()
        sv = StateVector(
            source=source,
            layer=self.layer,
            vector=vector,
            payload=meta,
        )
        sv.sv_id = sv_id
        self.bus.append(sv)
        self._pheromones[sv_id] = Pheromone(
            sv_id=sv_id, vector=vector,
            deposited_at=time.time(),
            concentration=1.0,
            half_life_seconds=self.half_life_seconds,
            metadata=meta,
        )
        return sv_id

    def reinforce(self, sv_id: str, multiplier: float = 1.0) -> float:
        """Reinforce a pheromone — resets its decay timer."""
        if sv_id not in self._pheromones:
            return 0.0
        p = self._pheromones[sv_id]
        p.deposited_at = time.time()  # reset decay
        p.concentration = min(1.0, p.concentration + multiplier)
        return p.concentration

    def sense(self, threshold: float = 0.05) -> List[Pheromone]:
        """Return all pheromones above the concentration threshold."""
        now = time.time()
        alive = []
        for sv_id, p in list(self._pheromones.items()):
            if p.decay(now) < threshold:
                # Remove fully-decayed pheromones
                del self._pheromones[sv_id]
                continue
            if p.concentration >= threshold:
                alive.append(p)
        return alive

    def strongest(self, k: int = 1, threshold: float = 0.05) -> List[Pheromone]:
        """Return the k strongest pheromones above threshold."""
        alive = self.sense(threshold=threshold)
        return sorted(alive, key=lambda p: p.concentration, reverse=True)[:k]


def stigmergy_demo(verbose: bool = True) -> Dict[str, Any]:
    """Run a minimal 2-agent stigmergy demo.

    Scenario: a scout marks a "food source" location with a strong
    pheromone. The forager senses the trail and reinforces it. After
    3 rounds, the trail is saturated. No direct messaging occurs.

    Returns a dict with the trail state at each step.
    """
    bus = StateBus()
    trail = PheromoneTrail(bus, layer="stigmergy_demo", half_life_seconds=300.0)
    log = []
    # Round 1: scout deposits
    sv_id = trail.deposit("scout", [1.0, 0.0, 0.5], {"target": "food_source_1"})
    log.append({"round": 1, "actor": "scout", "action": "deposit", "sv_id": sv_id, "concentration": 1.0})
    # Round 2: forager senses
    sensed = trail.sense(threshold=0.1)
    log.append({"round": 2, "actor": "forager", "action": "sense", "found": len(sensed), "ids": [p.sv_id for p in sensed]})
    if sensed:
        # forager reinforces
        new_conc = trail.reinforce(sensed[0].sv_id, multiplier=0.5)
        log.append({"round": 2.5, "actor": "forager", "action": "reinforce", "sv_id": sensed[0].sv_id, "new_concentration": new_conc})
    # Round 3: scout senses again
    strongest = trail.strongest(k=1, threshold=0.05)
    log.append({"round": 3, "actor": "scout", "action": "sense_strongest",
               "ids": [p.sv_id for p in strongest], "concentration": strongest[0].concentration if strongest else None})
    # Round 4: another scout deposits a different source
    sv_id2 = trail.deposit("scout_2", [0.0, 1.0, 0.3], {"target": "food_source_2"})
    log.append({"round": 4, "actor": "scout_2", "action": "deposit", "sv_id": sv_id2})
    # Final: what's alive?
    final = trail.sense(threshold=0.01)
    log.append({"round": 5, "actor": "system", "action": "sense_all", "count": len(final)})
    if verbose:
        for entry in log:
            print(f"  round {entry['round']:>3}: {entry['actor']:>10} {entry['action']:>16} → {entry}")
    return {"trail_count": len(trail._pheromones), "log": log}


__all__ = ["Pheromone", "PheromoneTrail", "stigmergy_demo"]
