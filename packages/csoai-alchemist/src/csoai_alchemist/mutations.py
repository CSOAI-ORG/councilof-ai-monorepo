"""csoai-alchemist v0.2.0 — geometry mutation operators.

This module adds the 6 fitness-gated mutation operators from the Aug 2026
frontier research brief to the Alchemist:

  1. MOVE      — perturb a clan's J-Space position (analog: fine-tuning)
  2. SPAWN     — new clan at a vacant region (analog: expert cloning)
  3. MERGE     — fuse two overlapping clans (analog: HC-SMoE merging)
  4. SPLIT     — one clan → two specialisations (analog: expert splitting)
  5. REWIRE    — change routing edges (analog: GPTSwarm edge optimisation)
  6. CURVATURE — bend the space itself (analog: learnable-curvature)
                  HUMAN-SIGN ONLY — never auto-applied

Gating is CVT-MAP-Elites-style: every mutation is proposed, scored against
a surrogate predictor, and committed only if it improves on held-out
tasks. v0.2.0 implements the operators and the apply/commit logic. Real
fitness gating requires GovBench integration (not in scope here).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from hyperbolic import (
    poincare_distance, poincare_centroid, project_to_ball,
)
from . import Alchemist, AlchemistConfig, ClanPosition


class MutationOp(str, Enum):
    """Six geometry-mutation operators per the frontier brief."""
    MOVE = "MOVE"
    SPAWN = "SPAWN"
    MERGE = "MERGE"
    SPLIT = "SPLIT"
    REWIRE = "REWIRE"
    CURVATURE = "CURVATURE"


@dataclass
class MutationRecord:
    """The result of one mutation."""
    op: MutationOp
    parent_ids: List[str]
    new_centroid: Tuple[float, ...]
    fitness_delta: float = 0.0
    accepted: bool = False
    rationale: str = ""


@dataclass
class MutationConfig:
    move_step: float = 0.05
    spawn_radius: float = 0.7
    merge_overlap_threshold: float = 0.3
    split_min_members: int = 5
    curvature_step: float = 0.1
    seed: int = 42


class MutableAlchemist(Alchemist):
    """Alchemist + 6 geometry mutation operators."""

    def __init__(self, config: Optional[AlchemistConfig] = None,
                 mutation_config: Optional[MutationConfig] = None) -> None:
        super().__init__(config=config)
        self.mut_config = mutation_config or MutationConfig()
        self.mutation_history: List[MutationRecord] = []
        self.edges: Dict[str, Dict[str, float]] = {}

    def add_edge(self, parent_id: str, child_id: str, weight: float = 1.0) -> None:
        self.edges.setdefault(parent_id, {})[child_id] = weight

    def edges_of(self, clan_id: str) -> Dict[str, float]:
        return self.edges.get(clan_id, {})

    def _record(self, record: MutationRecord) -> MutationRecord:
        """Append to history. Every mutation (success or failure) is logged."""
        self.mutation_history.append(record)
        return record

    # ----- 1. MOVE -----
    def op_move(self, target_id: str, step: Optional[float] = None) -> MutationRecord:
        if target_id not in self.clans:
            return self._record(MutationRecord(MutationOp.MOVE, [target_id], (),
                                                 0.0, False, "unknown clan"))
        target = self.clans[target_id]
        c = list(target.centroid)
        s = step if step is not None else self.mut_config.move_step
        random.seed(self.mut_config.seed + hash(target_id) % 10000)
        new_c = [x + random.gauss(0, s) for x in c]
        projected = project_to_ball(tuple(new_c))
        delta = math.sqrt(sum((a - b) ** 2 for a, b in zip(c, projected)))
        return self._record(MutationRecord(
            op=MutationOp.MOVE,
            parent_ids=[target_id],
            new_centroid=projected,
            fitness_delta=0.0,
            accepted=False,
            rationale=f"MOVE({target_id}): step={s}, ||Δ||={delta:.4f}",
        ))

    # ----- 2. SPAWN -----
    def op_spawn(self, parent_id: str, radius: Optional[float] = None) -> MutationRecord:
        if parent_id not in self.clans:
            return self._record(MutationRecord(MutationOp.SPAWN, [parent_id], (),
                                                 0.0, False, "unknown clan"))
        r = radius if radius is not None else self.mut_config.spawn_radius
        random.seed(self.mut_config.seed + hash(parent_id + "spawn") % 10000)
        dim = len(self.clans[parent_id].centroid)
        direction = [random.gauss(0, 1) for _ in range(dim)]
        norm = math.sqrt(sum(x * x for x in direction))
        if norm < 1e-9:
            direction = [1.0] + [0.0] * (dim - 1)
            norm = 1.0
        new_c = tuple(x * (r / norm) for x in direction)
        projected = project_to_ball(new_c)
        return self._record(MutationRecord(
            op=MutationOp.SPAWN,
            parent_ids=[parent_id],
            new_centroid=projected,
            fitness_delta=0.0,
            accepted=False,
            rationale=f"SPAWN({parent_id}): new clan at radius={r}",
        ))

    # ----- 3. MERGE -----
    def op_merge(self, clan_a_id: str, clan_b_id: str) -> MutationRecord:
        if clan_a_id not in self.clans or clan_b_id not in self.clans:
            return self._record(MutationRecord(MutationOp.MERGE, [clan_a_id, clan_b_id], (),
                                                 0.0, False, "unknown clan(s)"))
        a = self.clans[clan_a_id].centroid
        b = self.clans[clan_b_id].centroid
        d = poincare_distance(_to_tuple(a), _to_tuple(b))
        if d > self.mut_config.merge_overlap_threshold:
            return self._record(MutationRecord(
                op=MutationOp.MERGE, parent_ids=[clan_a_id, clan_b_id], new_centroid=(),
                fitness_delta=0.0, accepted=False,
                rationale=f"clans too far apart (d={d:.4f} > threshold {self.mut_config.merge_overlap_threshold})",
            ))
        merged = poincare_centroid([_to_tuple(a), _to_tuple(b)])
        return self._record(MutationRecord(
            op=MutationOp.MERGE,
            parent_ids=[clan_a_id, clan_b_id],
            new_centroid=merged,
            fitness_delta=0.0,
            accepted=False,
            rationale=f"MERGE({clan_a_id},{clan_b_id}): d={d:.4f}, ||merged||={math.sqrt(sum(c*c for c in merged)):.4f}",
        ))

    # ----- 4. SPLIT -----
    def op_split(self, clan_id: str) -> MutationRecord:
        if clan_id not in self.clans:
            return self._record(MutationRecord(MutationOp.SPLIT, [clan_id], (),
                                                 0.0, False, "unknown clan"))
        if len(self.clans[clan_id].member_ids) < self.mut_config.split_min_members:
            return self._record(MutationRecord(
                op=MutationOp.SPLIT, parent_ids=[clan_id], new_centroid=(),
                fitness_delta=0.0, accepted=False,
                rationale=f"clan too small ({len(self.clans[clan_id].member_ids)} members < {self.mut_config.split_min_members})",
            ))
        c = list(self.clans[clan_id].centroid)
        random.seed(self.mut_config.seed + hash(clan_id + "split") % 10000)
        dim = len(c)
        offset = [random.gauss(0, 0.1) for _ in range(dim)]
        c1 = project_to_ball(tuple(x + y for x, y in zip(c, offset)))
        c2 = project_to_ball(tuple(x - y for x, y in zip(c, offset)))
        return self._record(MutationRecord(
            op=MutationOp.SPLIT,
            parent_ids=[clan_id],
            new_centroid=c1,
            fitness_delta=0.0,
            accepted=False,
            rationale=f"SPLIT({clan_id}): c1=({c1[0]:.3f},...) c2=({c2[0]:.3f},...)",
        ))

    # ----- 5. REWIRE -----
    def op_rewire(self, clan_id: str, target_weight: Optional[float] = None) -> MutationRecord:
        if clan_id not in self.clans:
            return self._record(MutationRecord(MutationOp.REWIRE, [clan_id], (),
                                                 0.0, False, "unknown clan"))
        edges = self.edges.get(clan_id, {})
        if not edges:
            return self._record(MutationRecord(MutationOp.REWIRE, [clan_id], (),
                                                 0.0, False, "no edges to rewire"))
        target_child = next(iter(edges.keys()))
        old_w = edges[target_child]
        new_w = target_weight if target_weight is not None else max(0.0, min(1.0, old_w + old_w * 0.2))
        return self._record(MutationRecord(
            op=MutationOp.REWIRE,
            parent_ids=[clan_id],
            new_centroid=(new_w,),
            fitness_delta=0.0,
            accepted=False,
            rationale=f"REWIRE({clan_id}->{target_child}): {old_w:.3f} → {new_w:.3f}",
        ))

    # ----- 6. CURVATURE (HUMAN-SIGN ONLY) -----
    def op_curvature(self, target_id: str, step: Optional[float] = None) -> MutationRecord:
        if target_id not in self.clans:
            return self._record(MutationRecord(MutationOp.CURVATURE, [target_id], (),
                                                 0.0, False, "unknown clan"))
        s = step if step is not None else self.mut_config.curvature_step
        c = list(self.clans[target_id].centroid)
        norm = math.sqrt(sum(x * x for x in c))
        if norm < 1e-9:
            return self._record(MutationRecord(MutationOp.CURVATURE, [target_id], (),
                                                 0.0, False, "zero-radius clan"))
        new_norm = max(0.0, min(1.0 - 1e-5, norm + s * norm))
        scale = new_norm / norm
        new_c = tuple(x * scale for x in c)
        return self._record(MutationRecord(
            op=MutationOp.CURVATURE,
            parent_ids=[target_id],
            new_centroid=new_c,
            fitness_delta=0.0,
            accepted=False,
            rationale=f"CURVATURE({target_id}): ||c||={norm:.4f} → {new_norm:.4f} (HUMAN-SIGN ONLY)",
        ))

    # ----- Universal dispatcher -----
    def mutate(self, op: MutationOp, **kwargs) -> MutationRecord:
        if op == MutationOp.MOVE:
            return self.op_move(kwargs["target_id"])
        if op == MutationOp.SPAWN:
            return self.op_spawn(kwargs["parent_id"])
        if op == MutationOp.MERGE:
            return self.op_merge(kwargs["clan_a_id"], kwargs["clan_b_id"])
        if op == MutationOp.SPLIT:
            return self.op_split(kwargs["clan_id"])
        if op == MutationOp.REWIRE:
            return self.op_rewire(kwargs["clan_id"], kwargs.get("target_weight"))
        if op == MutationOp.CURVATURE:
            return self.op_curvature(kwargs["target_id"], kwargs.get("step"))
        raise ValueError(f"unknown mutation op: {op}")

    # ----- Apply a mutation to the registry -----
    def apply_mutation(self, record: MutationRecord) -> bool:
        if record.op == MutationOp.CURVATURE:
            return False  # HUMAN-SIGN ONLY
        if record.op == MutationOp.SPAWN:
            new_id = f"spawned_{len(self.clans)}"
            self.clans[new_id] = ClanPosition(
                clan_id=new_id,
                centroid=record.new_centroid,
                member_ids=[],
                avg_reconstruction_error=0.0,
                curvature=math.sqrt(sum(c * c for c in record.new_centroid)),
                proposal_score=0.0,
            )
            record.accepted = True
            return True
        if record.op == MutationOp.REWIRE:
            parent = record.parent_ids[0]
            if parent in self.edges and self.edges[parent]:
                target_child = next(iter(self.edges[parent].keys()))
                self.edges[parent][target_child] = record.new_centroid[0]
                record.accepted = True
                return True
            return False
        if record.op == MutationOp.MERGE and len(record.parent_ids) >= 2:
            self.clans[record.parent_ids[0]].centroid = record.new_centroid
            if record.parent_ids[1] in self.clans:
                del self.clans[record.parent_ids[1]]
            record.accepted = True
            return True
        # MOVE / SPLIT / CURVATURE: update centroid of parent
        if record.parent_ids and record.parent_ids[0] in self.clans:
            self.clans[record.parent_ids[0]].centroid = record.new_centroid
            record.accepted = True
            return True
        return False

    def apply_mutation_curvature_human_signed(self, record: MutationRecord) -> bool:
        """CURVATURE: explicit human sign-off."""
        if record.op != MutationOp.CURVATURE:
            return False
        if record.parent_ids and record.parent_ids[0] in self.clans:
            self.clans[record.parent_ids[0]].centroid = record.new_centroid
            record.accepted = True
            return True
        return False


def _to_tuple(p) -> Tuple[float, ...]:
    return tuple(p) if isinstance(p, (tuple, list)) else tuple(p.centroid)


__all__ = [
    "MutationOp", "MutationRecord", "MutationConfig", "MutableAlchemist",
]
