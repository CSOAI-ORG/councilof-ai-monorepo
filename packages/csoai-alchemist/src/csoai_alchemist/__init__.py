"""csoai-alchemist — proposes new clans via orphan detection in J-Space.

v0.1.0 SCAFFOLD. The Alchemist monitors the StateBus for orphan
StateVectors — vectors that don't fit any existing clan (above a
reconstruction-error threshold) — and proposes a new clan for each
sufficiently-large cluster of orphans.

Architecture (per the Aug 2026 geometry brief, Q1):
1. Each registered clan has a centroid (a Poincaré-ball point).
2. Every StateVector is scored against every clan by reconstruction
   error (Poincaré distance + alignment residual).
3. If a vector's error is above `orphan_threshold` for ALL clans, it
   is an orphan.
4. If the orphan cluster has ≥ `min_clan_size` members, the Alchemist
   computes the orphan centroid via `poincare_centroid` (Fréchet mean)
   and proposes a new ClanPosition.
5. The Alchemist does NOT create clans unilaterally — it proposes them
   to the Council layer (which we don't have yet). For v0.1.0, we
   return the proposal and let the caller decide.

What this provides:
- A real evolutionary loop (not hardcoded, not fixed-ontology)
- A geometric primitive (orphan detection in hyperbolic space)
- A simple threshold-based interface (no LLM, no embeddings, deterministic)

What this does NOT do:
- Real embeddings (we use raw task vectors from the StateBus)
- Real reconstruction (we use Poincaré distance as a proxy)
- Council adjudication (the caller decides whether to accept)
- Persistence (orphan history is in-memory only)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# The two primitives we just added (in v0.2.0)
from hyperbolic import poincare_distance, poincare_centroid, project_to_ball


@dataclass
class ClanPosition:
    """A proposed clan in J-Space.

    Attributes:
        clan_id: name (e.g., "clan_0", "clan_1", "orphan_42")
        centroid: a Poincaré-ball point
        member_ids: list of sv_ids that belong to this clan
        avg_reconstruction_error: mean error across members
        curvature: local curvature estimate (mean ||centroid||)
        proposal_score: how confident the Alchemist is (0..1)
    """
    clan_id: str
    centroid: Tuple[float, ...]
    member_ids: List[str] = field(default_factory=list)
    avg_reconstruction_error: float = 0.0
    curvature: float = 0.0
    proposal_score: float = 0.0


@dataclass
class AlchemistConfig:
    """Tuning knobs for the Alchemist."""
    orphan_threshold: float = 1.5  # minimum reconstruction error to be an orphan
    min_clan_size: int = 3        # minimum orphan cluster size to propose
    max_proposals: int = 10       # cap per scan (don't drown the Council)
    curvature_floor: float = 0.0  # ignore clans closer than this to origin


class Alchemist:
    """Proposes new clans from orphan clusters in the StateBus.

    Usage:
        alchemist = Alchemist()
        alchemist.register_clan(ClanPosition("clan_0", centroid=(0.1, 0.0, 0.0)))
        proposals = alchemist.scan(state_vectors)
        # Caller decides whether to accept proposals
    """

    def __init__(self, config: Optional[AlchemistConfig] = None) -> None:
        self.config = config or AlchemistConfig()
        self.clans: Dict[str, ClanPosition] = {}
        self.proposal_history: List[ClanPosition] = []

    def register_clan(self, clan: ClanPosition) -> None:
        """Register an existing clan (initial state, or after Council approval)."""
        self.clans[clan.clan_id] = clan

    def _reconstruction_error(self, vec: Tuple[float, ...], clan: ClanPosition) -> float:
        """Score a vector against a clan by Poincaré distance.

        In v0.1.0 SCAFFOLD, this is just `poincare_distance`. A real impl
        would use a learned autoencoder and the residual ||x - decoder(x)||
        on the Poincaré ball.
        """
        return poincare_distance(vec, project_to_ball(clan.centroid))

    def _classify_orphan(self, vec: Tuple[float, ...], sv_id: str) -> bool:
        """Return True if `vec` is an orphan (no clan claims it)."""
        if not self.clans:
            return True
        # An orphan if reconstruction error exceeds threshold for ALL clans
        for clan in self.clans.values():
            if self._reconstruction_error(vec, clan) < self.config.orphan_threshold:
                return False
        return True

    def _find_orphan_clusters(
        self, candidates: List[Tuple[str, Tuple[float, ...]]]
    ) -> List[List[Tuple[str, Tuple[float, ...]]]]:
        """Greedy cluster orphans by pairwise Poincaré distance.

        Two orphans are in the same cluster if their distance is < the
        orphan threshold. This is a fast approximation of DBSCAN.
        """
        threshold = self.config.orphan_threshold
        clusters: List[List[Tuple[str, Tuple[float, ...]]]] = []
        used = set()
        for i, (id_i, v_i) in enumerate(candidates):
            if i in used:
                continue
            cluster = [(id_i, v_i)]
            used.add(i)
            for j, (id_j, v_j) in enumerate(candidates):
                if j in used:
                    continue
                # Add to cluster if close to ANY member
                if any(poincare_distance(v_i, v_j) < threshold
                       and poincare_distance(c[1], v_j) < threshold
                       for c in cluster):
                    cluster.append((id_j, v_j))
                    used.add(j)
            clusters.append(cluster)
        return clusters

    def scan(self, state_vectors: List[Tuple[str, Tuple[float, ...]]]) -> List[ClanPosition]:
        """Scan the StateBus for orphan clusters and propose new clans.

        Args:
            state_vectors: list of (sv_id, vector) tuples from the bus.

        Returns:
            List of proposed ClanPositions (caller decides whether to accept).
        """
        # Step 1: filter to orphans
        orphans = [
            (sv_id, v) for sv_id, v in state_vectors
            if self._classify_orphan(v, sv_id)
        ]
        if not orphans:
            return []
        # Step 2: greedy cluster
        clusters = self._find_orphan_clusters(orphans)
        # Step 3: filter by min_clan_size and propose
        proposals = []
        existing_ids = set(self.clans.keys())
        next_id = 0
        while f"orphan_{next_id}" in existing_ids:
            next_id += 1
        for cluster in clusters:
            if len(cluster) < self.config.min_clan_size:
                continue
            member_ids = [sv_id for sv_id, _ in cluster]
            points = [v for _, v in cluster]
            # Compute Fréchet mean
            try:
                centroid = poincare_centroid(points)
            except (ValueError, ZeroDivisionError):
                continue
            # Score proposal: cluster density (1 - mean pairwise distance / threshold)
            pair_distances = []
            for i in range(len(points)):
                for j in range(i + 1, len(points)):
                    pair_distances.append(poincare_distance(points[i], points[j]))
            mean_dist = sum(pair_distances) / len(pair_distances) if pair_distances else 0
            density = max(0.0, 1.0 - mean_dist / self.config.orphan_threshold)
            # Mean reconstruction error (against all existing clans)
            errors = [self._reconstruction_error(v, c) for c in self.clans.values()
                      for v in points]
            avg_err = sum(errors) / len(errors) if errors else self.config.orphan_threshold
            clan = ClanPosition(
                clan_id=f"orphan_{next_id}",
                centroid=centroid,
                member_ids=member_ids,
                avg_reconstruction_error=avg_err,
                curvature=math.sqrt(sum(c * c for c in centroid)),
                proposal_score=density,
            )
            proposals.append(clan)
            self.proposal_history.append(clan)
            next_id += 1
            existing_ids.add(clan.clan_id)
            if len(proposals) >= self.config.max_proposals:
                break
        return proposals

    def accept_proposal(self, clan: ClanPosition) -> None:
        """Council action: accept a proposal, adding the clan to the registry."""
        self.clans[clan.clan_id] = clan

    def reject_proposal(self, clan: ClanPosition) -> None:
        """Council action: reject a proposal, archiving it without adding."""
        # Mark as rejected by moving it out of proposals (caller can keep history)
        pass  # history is preserved via self.proposal_history


__all__ = ["Alchemist", "AlchemistConfig", "ClanPosition"]


# =========================================================================
# v0.2.0 — geometry mutation operators are in mutations.py.
# Re-exported here so callers can `from csoai_alchemist import MutableAlchemist`.
# =========================================================================
from .mutations import (
    MutationOp, MutationRecord, MutationConfig, MutableAlchemist,
)

__all__ = [
    "Alchemist", "AlchemistConfig", "ClanPosition",
    "MutationOp", "MutationRecord", "MutationConfig", "MutableAlchemist",
]
