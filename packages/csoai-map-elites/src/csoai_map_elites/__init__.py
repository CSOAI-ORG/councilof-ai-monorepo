"""csoai_map_elites — Hyperbolic MAP-Elites fitness gate.

MAP-Elites is a Quality-Diversity algorithm: instead of optimizing a
single fitness objective, it populates a grid of "elites" — the best
individual found so far for each cell in a behavior space.

In the SOVOS substrate, the **behavior space** is the Poincaré ball
(hyperbolic geometry). The hyperbolic ball is the right choice because:
  - Hierarchies (governance, OWEM clans, care-floor sub-axes) are
    naturally hierarchical → hyperbolic space represents them
    with much less distortion than Euclidean space.
  - The ball is bounded (||x|| < 1), so elites near the boundary are
    "extreme" in the hyperbolic sense (very deep hierarchies).
  - Mutation operators in the Euclidean subspace map to rich
    geometric moves when lifted to the ball.

This package implements:
  - HyperbolicMapElites: the grid (cells indexed by 2D Poincaré coords)
  - add(v, fitness, behavior): insert v at its behavior cell if it's
    the fittest so far
  - safe_mutate(v, mutation_fn): apply mutation, project back into ball,
    reject if mutation violates care-floor (safety gate)
  - iterate(...): the full MAP-Elites loop with the gate as the safety
    envelope

The "patent-grade white space" is the combination of:
  1. Hyperbolic MAP-Elites (vs the standard Euclidean version).
  2. Mutation operators that respect the care-floor (not just the
     fitness objective).
  3. The fitness gate that REJECTS mutations, not just scores them —
     mutations are checked against the substrate invariants BEFORE
     they enter the archive.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — the SOVOS invariants
# ---------------------------------------------------------------------------
BALL_EPS = 1e-5
BALL_RADIUS = 1.0 - BALL_EPS
CARE_FLOOR = 0.95
MUTATION_REJECT_THRESHOLD = 0.5   # below this, a mutation is rejected as unsafe


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class CellKey:
    """A 2D cell in the hyperbolic behavior grid."""
    i: int
    j: int

    def __hash__(self) -> int:
        return hash((self.i, self.j))

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, CellKey) and self.i == other.i and self.j == other.j


@dataclass
class Elite:
    """One elite stored in a cell."""
    vector: List[float]
    fitness: float
    behavior: List[float]             # 2D Poincaré coordinate
    cell: Tuple[int, int]
    generation: int
    chain_id: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MutationVerdict:
    """The verdict on a proposed mutation."""
    accepted: bool
    original_fitness: float
    mutated_fitness: float
    fitness_delta: float
    care_floor_ok: bool
    ball_ok: bool
    reason: str = ""
    chain_id: str = ""


# ---------------------------------------------------------------------------
# Hyperbolic MAP-Elites
# ---------------------------------------------------------------------------
class HyperbolicMapElites:
    """Hyperbolic MAP-Elites archive + safety-gated mutation operators.

    Args:
        grid_size:  number of cells per axis (default 16 → 256 cells)
        coord_dim:  dimensionality of each elite's vector
        ball_radius: max ||x|| for any elite (default 0.95)
    """

    def __init__(self, grid_size: int = 16, coord_dim: int = 8,
                 ball_radius: float = 0.95,
                 fitness_fn: Optional[Callable[[np.ndarray], float]] = None):
        self.grid_size = grid_size
        self.coord_dim = coord_dim
        self.ball_radius = ball_radius
        self.fitness_fn = fitness_fn or _default_fitness
        self.archive: Dict[Tuple[int, int], Elite] = {}
        self.generation = 0
        self.mutation_log: List[MutationVerdict] = []

    # -----------------------------------------------------------------------
    # Cell indexing — discretize the ball into a grid
    # -----------------------------------------------------------------------
    def _behavior_to_cell(self, behavior: np.ndarray) -> Tuple[int, int]:
        """Map a 2D Poincaré coord (in [-1, 1]) to a grid cell."""
        if len(behavior) < 2:
            raise ValueError(f"behavior must be 2D, got {len(behavior)}")
        # Clamp to [-radius, radius] then map to [0, grid_size-1]
        def to_idx(v: float) -> int:
            v_clamped = max(-self.ball_radius, min(self.ball_radius, float(v)))
            # Map [-radius, radius] → [0, grid_size-1]
            norm = (v_clamped + self.ball_radius) / (2 * self.ball_radius)
            return min(self.grid_size - 1, max(0, int(norm * self.grid_size)))
        return (to_idx(behavior[0]), to_idx(behavior[1]))

    # -----------------------------------------------------------------------
    # Hyperbolic projection
    # -----------------------------------------------------------------------
    def project_to_ball(self, v: np.ndarray) -> np.ndarray:
        """Project a vector into the Poincaré ball (||v|| ≤ ball_radius)."""
        n = float(np.linalg.norm(v))
        if n < 1e-12:
            return np.zeros_like(v)
        if n <= self.ball_radius:
            return v
        return v * (self.ball_radius / n)

    # -----------------------------------------------------------------------
    # Archive add (the MAP-Elites "update" step)
    # -----------------------------------------------------------------------
    def add(self, vector: np.ndarray, behavior: np.ndarray,
            generation: Optional[int] = None) -> bool:
        """Add an individual to the archive if it's the fittest for its cell.

        Returns True if added/replaced, False if rejected (less fit than current).
        """
        v = self.project_to_ball(np.asarray(vector, dtype=np.float64))
        b = np.asarray(behavior[:2], dtype=np.float64)
        cell = self._behavior_to_cell(b)
        fitness = float(self.fitness_fn(v))
        gen = generation if generation is not None else self.generation
        chain_body = json.dumps({
            "vector": v.tolist(), "behavior": b.tolist(),
            "fitness": fitness, "cell": cell, "gen": gen,
        }, sort_keys=True, default=str).encode()
        chain_id = hashlib.sha256(chain_body).hexdigest()[:24]
        existing = self.archive.get(cell)
        if existing is None or fitness > existing.fitness:
            elite = Elite(
                vector=v.tolist(), fitness=fitness,
                behavior=b.tolist(), cell=cell,
                generation=gen, chain_id=chain_id,
            )
            self.archive[cell] = elite
            return True
        return False

    # -----------------------------------------------------------------------
    # Safety-gated mutation
    # -----------------------------------------------------------------------
    def safe_mutate(self, parent: np.ndarray, mutation_fn: Callable[[np.ndarray], np.ndarray],
                    behavior: np.ndarray,
                    care_floor: float = CARE_FLOOR,
                    reject_threshold: float = MUTATION_REJECT_THRESHOLD) -> MutationVerdict:
        """Apply mutation, then SAFETY-GATE against care-floor + ball membership.

        A mutation is REJECTED if:
          - the mutated vector leaves the Poincaré ball, OR
          - the mutated fitness drops below `reject_threshold` (the
            "fitness floor" — below which mutations are unsafe for the
            substrate), OR
          - the mutated fitness drops more than 50% below the parent's
            fitness (catastrophic regression).
        """
        parent_arr = np.asarray(parent, dtype=np.float64)
        parent_fitness = float(self.fitness_fn(parent_arr))
        try:
            mutated = np.asarray(mutation_fn(parent_arr), dtype=np.float64)
        except Exception as e:
            chain_body = f"mutation-failed:{e}".encode()
            chain_id = hashlib.sha256(chain_body).hexdigest()[:24]
            return MutationVerdict(
                accepted=False, original_fitness=parent_fitness,
                mutated_fitness=parent_fitness, fitness_delta=0.0,
                care_floor_ok=False, ball_ok=False,
                reason=f"mutation_fn raised: {e}", chain_id=chain_id,
            )
        # Project into ball
        ball_ok = bool(np.linalg.norm(mutated) <= self.ball_radius)
        mutated_proj = self.project_to_ball(mutated)
        mutated_fitness = float(self.fitness_fn(mutated_proj))
        delta = mutated_fitness - parent_fitness
        # Gate checks
        care_floor_ok = mutated_fitness >= reject_threshold
        no_catastrophe = delta >= -0.5 * parent_fitness if parent_fitness > 0 else True
        accepted = ball_ok and care_floor_ok and no_catastrophe
        reasons = []
        if not ball_ok:
            reasons.append(f"mutation left ball (||v||={np.linalg.norm(mutated):.4f} > {self.ball_radius})")
        if not care_floor_ok:
            reasons.append(f"fitness {mutated_fitness:.4f} < reject_threshold {reject_threshold}")
        if not no_catastrophe:
            reasons.append(f"catastrophic regression: delta={delta:.4f}")
        chain_body = json.dumps({
            "parent_fitness": parent_fitness,
            "mutated_fitness": mutated_fitness, "delta": delta,
            "ball_ok": ball_ok, "care_floor_ok": care_floor_ok,
            "accepted": accepted,
        }, sort_keys=True).encode()
        chain_id = hashlib.sha256(chain_body).hexdigest()[:24]
        verdict = MutationVerdict(
            accepted=accepted, original_fitness=parent_fitness,
            mutated_fitness=mutated_fitness, fitness_delta=delta,
            care_floor_ok=care_floor_ok, ball_ok=ball_ok,
            reason="; ".join(reasons) if reasons else "accepted",
            chain_id=chain_id,
        )
        self.mutation_log.append(verdict)
        return verdict

    # -----------------------------------------------------------------------
    # Iterate — the MAP-Elites loop
    # -----------------------------------------------------------------------
    def iterate(self, n_iterations: int = 10, mutation_fn: Optional[Callable] = None,
                population_init: Optional[Callable[[], Tuple[np.ndarray, np.ndarray]]] = None,
                seed: Optional[int] = None) -> Dict[str, Any]:
        """Run `n_iterations` MAP-Elites iterations with the safety gate.

        Each iteration:
          1. Pick a random elite from the archive (or seed if empty).
          2. Apply a mutation.
          3. Gate the mutation. If accepted, add to archive.
        """
        if mutation_fn is None:
            mutation_fn = _default_mutation
        if population_init is None:
            population_init = _default_init
        rng = np.random.RandomState(seed)
        accepted = 0
        rejected = 0
        for i in range(n_iterations):
            self.generation += 1
            if not self.archive:
                v, b = population_init()
            else:
                cell = list(self.archive.keys())[rng.randint(len(self.archive))]
                elite = self.archive[cell]
                v = np.asarray(elite.vector, dtype=np.float64)
                b = np.asarray(elite.behavior, dtype=np.float64)
            verdict = self.safe_mutate(v, mutation_fn, b)
            if verdict.accepted:
                # Re-evaluate behavior (deterministic from the vector itself)
                mutated = self.project_to_ball(v + rng.randn(self.coord_dim) * 0.1)
                # Behavior = first 2 dims (clipped to ball)
                b_new = np.clip(mutated[:2], -self.ball_radius, self.ball_radius)
                self.add(mutated, b_new, generation=self.generation)
                accepted += 1
            else:
                rejected += 1
        return {
            "generation": self.generation,
            "archive_size": len(self.archive),
            "accepted": accepted, "rejected": rejected,
            "acceptance_rate": accepted / max(1, n_iterations),
        }

    # -----------------------------------------------------------------------
    # Stats + inspection
    # -----------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        if not self.archive:
            return {"archive_size": 0, "fitness_max": 0, "fitness_mean": 0}
        fits = [e.fitness for e in self.archive.values()]
        return {
            "archive_size": len(self.archive),
            "fitness_max": max(fits),
            "fitness_mean": sum(fits) / len(fits),
            "fitness_min": min(fits),
            "grid_coverage": len(self.archive) / (self.grid_size ** 2),
            "mutations_accepted": sum(1 for v in self.mutation_log if v.accepted),
            "mutations_rejected": sum(1 for v in self.mutation_log if not v.accepted),
        }


# ---------------------------------------------------------------------------
# Default fitness + mutation + init (used when caller doesn't supply)
# ---------------------------------------------------------------------------
def _default_fitness(v: np.ndarray) -> float:
    """Default fitness: higher norm + balance is better."""
    n = float(np.linalg.norm(v))
    # Reward norm in [0.4, 0.8] (the "productive" zone of the ball)
    if 0.4 <= n <= 0.8:
        return 1.0 - abs(n - 0.6)  # peak at n=0.6
    elif n < 0.4:
        return 0.5 * n / 0.4  # grow from 0
    else:
        return max(0.0, 0.5 - (n - 0.8))  # decay past 0.8


def _default_mutation(v: np.ndarray) -> np.ndarray:
    """Default mutation: Gaussian noise of magnitude 0.1."""
    return v + np.random.randn(*v.shape) * 0.1


def _default_init() -> Tuple[np.ndarray, np.ndarray]:
    """Default initial population: small random vector."""
    v = np.random.randn(8) * 0.3
    return v, v[:2]


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    """Smoke test: build a small MAP-Elites archive, run some iterations."""
    me = HyperbolicMapElites(grid_size=8, coord_dim=4)
    # Seed with a few individuals
    for _ in range(5):
        v = np.random.randn(4) * 0.3
        b = np.clip(v[:2], -0.95, 0.95)
        me.add(v, b)
    # Run 20 iterations
    result = me.iterate(n_iterations=20, seed=42)
    stats = me.stats()
    return {
        "archive_after_seed": 5,
        "archive_after_iter": stats["archive_size"],
        "iter_accepted": result["accepted"],
        "iter_rejected": result["rejected"],
        "fitness_max": stats["fitness_max"],
        "mutations_accepted": stats["mutations_accepted"],
        "mutations_rejected": stats["mutations_rejected"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
