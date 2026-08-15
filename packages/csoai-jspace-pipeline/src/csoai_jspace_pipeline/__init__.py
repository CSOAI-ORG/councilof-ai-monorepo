"""csoai-jspace-pipeline — Poincaré pipeline wrapper for the sovos-mind StateBus.

v0.1.0 SCAFFOLD. This module INTEGRATES the existing J-Space hyperbolic
primitives (`poincare_distance`, `mobius_add`, `project_to_ball`,
`procrustes_alignment`) with the sovos-mind StateBus + Water/Milk/Honey
pipeline.

Honest scope:
- The sovos-mind pipeline (water.py / milk.py / honey.py) is purely
  Euclidean. No Poincaré, no Möbius, no geodesics.
- J-Space primitives EXIST (verified from disk: sovos-jspace-hyperbolic
  exports poincare_distance, mobius_add, project_to_ball, procrustes_alignment).
- This module WRAPS those primitives and applies them to StateVectors
  flowing through the bus. It does NOT replace sovos-mind — it sits
  alongside it as an optional hyperbolic pathway.

Why this matters:
- In Poincaré space, the origin = maximum certainty/consensus.
- Boundary = maximum entropy/possibility.
- Water→Milk→Honey is a journey from the boundary toward the origin.
- Distillation = geodesic convergence along the manifold.

What's in this v0.1.0 SCAFFOLD:
1. `project_water_to_poincare`: take a Euclidean water vector → project
   onto the Poincaré ball (near boundary, |x| ≈ 1).
2. `mobilize_milk`: take a water vector + a centroid (clan target) →
   apply Möbius addition. Result: a milk vector that is "between" water
   and the clan centroid in hyperbolic space.
3. `distill_honey`: take a milk vector → exponential map toward origin.
   The vector moves along the manifold toward maximum certainty.
4. `route_via_procrustes`: align a query vector to known clan centroids
   using Procrustes alignment, then route by closest centroid (Poincaré
   distance, not Euclidean).
5. `federate_buses`: merge two StateBuses with Procrustes-aligned
   consensus (Q3 from the brief, simplified).

Tests: 12 tests, all should pass.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# --- hyperbolic sibling-path hook (durable seam fix, 2026-08-13) ---
# The pipeline's core math lives in the `hyperbolic` package inside
# sovos-jspace-hyperbolic/src. Root pyproject ships it namespaced as
# `sovos_jspace_hyperbolic`, so bare `from hyperbolic import ...`
# only resolves when that source dir is on sys.path. We add it here so
# the pipeline works in every context (monorepo, pod, raw pytest) without
# requiring PYTHONPATH surgery. Honest scope: if the sibling is genuinely
# absent this falls through to the ImportError rather than faking a stub.
import os
import sys
_HYPERBOLIC_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "..", "sovos-jspace-hyperbolic", "src",
)
if os.path.isdir(_HYPERBOLIC_SRC) and _HYPERBOLIC_SRC not in sys.path:
    sys.path.insert(0, _HYPERBOLIC_SRC)
# --- end hook ---

from hyperbolic import poincare_distance, mobius_add, project_to_ball, procrustes_alignment


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BALL_EPS = 1e-5            # safety margin so we never sit on the boundary
DEFAULT_CURVATURE = -1.0   # canonical Poincaré ball curvature


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_tuple(vec: List[float]) -> Tuple[float, ...]:
    return tuple(float(x) for x in vec)


def _l2(vec: List[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def _normalize_safe(vec: List[float], eps: float = 1e-12) -> List[float]:
    n = _l2(vec)
    if n < eps:
        return list(vec)
    return [x / n for x in vec]


def _project_ball_inplace(v: List[float], max_norm: float = 1.0 - BALL_EPS) -> List[float]:
    """Project v onto the open Poincaré ball of radius max_norm."""
    n = _l2(v)
    if n < BALL_EPS:
        # Zero vector — pick a stable small vector along the first axis
        return [BALL_EPS] + [0.0] * (len(v) - 1)
    if n < max_norm:
        return list(v)
    return [x * (max_norm / n) for x in v]


# ---------------------------------------------------------------------------
# Water → Poincaré (boundary placement)
# ---------------------------------------------------------------------------

def project_water_to_poincare(water_vec: List[float], radius: float = 0.9) -> List[float]:
    """Map a Euclidean water vector to a point near the Poincaré boundary.

    The "water" represents raw data — maximum entropy, maximum possibility.
    In Poincaré geometry, this is the boundary. We normalize the input and
    scale it to `radius` (default 0.9, comfortably inside the unit ball).
    """
    normed = _normalize_safe(water_vec)
    # _normalize_safe returns the input unchanged if the vector is zero.
    # In that case, fall back to a stable unit vector along the first axis.
    if _l2(normed) < BALL_EPS:
        # Place a tiny vector on the first axis to keep the direction stable.
        if not normed:
            normed = [1.0] + [0.0] * (len(water_vec) - 1) if len(water_vec) > 1 else [1.0]
        else:
            normed = [BALL_EPS if i == 0 else 0.0 for i in range(len(water_vec))]
    return [x * radius for x in normed]


# ---------------------------------------------------------------------------
# Milk → Möbius transform (mid-space placement, anchored at clan centroid)
# ---------------------------------------------------------------------------

def mobilize_milk(water_vec: List[float], clan_centroid: List[float],
                   curvature: float = DEFAULT_CURVATURE) -> List[float]:
    """Apply Möbius addition to a water vector and a clan centroid.

    Möbius addition (u ⊕ v) is the hyperbolic analogue of vector addition.
    The result lies "between" water and centroid in hyperbolic distance.
    Both inputs must already be inside the Poincaré ball.
    """
    # Project to ball, then Möbius-add.
    u = _project_ball_inplace(water_vec)
    v = _project_ball_inplace(clan_centroid)
    result = mobius_add(_to_tuple(u), _to_tuple(v))
    return list(result)


# ---------------------------------------------------------------------------
# Honey → distillation toward origin (exponential map)
# ---------------------------------------------------------------------------

def distill_honey(milk_vec: List[float], target_radius: float = 0.3) -> List[float]:
    """Move a milk vector toward the origin (distillation = certainty).

    We project the milk onto the Poincaré ball, then rescale its norm
    toward `target_radius` (a fixed fraction of the original). This is the
    exponential map's effect at the origin: "pull the vector inward."

    Honest note: a full exponential map uses a curvature-dependent
    hyperbolic distance metric. We use the simpler Euclidean rescale
    because it is monotonic, deterministic, and preserves direction. The
    true exponential map at the origin is equivalent to a radial
    rescaling in the Poincaré ball model.
    """
    if not milk_vec:
        return [0.0]
    norm = _l2(milk_vec)
    if norm < BALL_EPS:
        return list(milk_vec)
    # Project to safe ball
    safe_max = 1.0 - BALL_EPS
    capped = min(norm, safe_max)
    # Rescale so the new radius = capped * (target_radius / safe_max)
    scale = (capped * target_radius / safe_max) / capped
    return [x * scale for x in milk_vec]


# ---------------------------------------------------------------------------
# Procrustes-aligned routing
# ---------------------------------------------------------------------------

@dataclass
class ClanRoute:
    """The result of routing a query against one or more clans."""
    clan_id: str
    distance: float
    aligned_query: List[List[float]]


def route_via_procrustes(query_vec: List[float], clans: Dict[str, np.ndarray]) -> ClanRoute:
    """Align `query_vec` to each clan's centroid basis and return the closest.

    Args:
        query_vec: a single Euclidean vector (will be wrapped as 1-row matrix)
        clans: mapping of clan_id → centroid matrix (shape: n_clans × dim)

    Returns:
        ClanRoute with the closest clan and the alignment matrix.

    Honest note: if `clans` is empty or all clans have incompatible shapes,
    returns an empty route. The caller should always provide at least one
    clan.
    """
    if not clans:
        return ClanRoute(clan_id="", distance=float("inf"), aligned_query=[])
    q = np.asarray(query_vec, dtype=np.float64).reshape(1, -1)
    best_id, best_d, best_aligned = "", float("inf"), []
    for clan_id, centroid in clans.items():
        if centroid.ndim == 1:
            centroid = centroid.reshape(1, -1)
        if centroid.shape[1] != q.shape[1]:
            # Incompatible dim — skip with a sentinel high distance
            continue
        # Procrustes-align q to centroid's coordinate frame
        try:
            aligned = procrustes_alignment(q.tolist(), centroid.tolist())
        except Exception:
            continue
        # Convert aligned back to flat vector and project to ball
        a = np.asarray(aligned, dtype=np.float64).reshape(-1)
        if a.size == 0:
            continue
        proj = _project_ball_inplace(a.tolist())
        # Distance from the clan centroid in hyperbolic space
        d = poincare_distance(_to_tuple(proj), _to_tuple(_project_ball_inplace(centroid.reshape(-1).tolist())))
        if d < best_d:
            best_d = d
            best_id = clan_id
            best_aligned = aligned
    return ClanRoute(clan_id=best_id, distance=best_d, aligned_query=best_aligned)


# ---------------------------------------------------------------------------
# StateBus federation (Q3 from the brief — simplified)
# ---------------------------------------------------------------------------

@dataclass
class FederatedBus:
    """Two StateBuses merged via Procrustes-aligned consensus.

    Both buses are kept intact (no sovereignty loss). The federated view
    is a read-only projection that consensus-averages shared sources.
    """
    bus_a_vectors: List[List[float]] = field(default_factory=list)
    bus_b_vectors: List[List[float]] = field(default_factory=list)
    shared_sources: List[str] = field(default_factory=list)
    merged_vectors: List[List[float]] = field(default_factory=list)
    n_aligned: int = 0
    n_avg: int = 0


def federate_buses(bus_a_vectors: Dict[str, List[float]],
                    bus_b_vectors: Dict[str, List[float]]) -> FederatedBus:
    """Federate two StateBus vector collections (read-only).

    Args:
        bus_a_vectors: mapping of sv_id → vector from bus A
        bus_b_vectors: mapping of sv_id → vector from bus B

    Returns:
        FederatedBus with merged view. Shared sv_ids are Procrustes-aligned
        then averaged. Buses A and B remain untouched.

    Honest note: we don't enforce dim compatibility — if dims differ, we
    pad the shorter to match. Real federation would require a shared
    dimension via projection (Procrustes) or a known atlas.
    """
    shared = sorted(set(bus_a_vectors.keys()) & set(bus_b_vectors.keys()))
    merged = []
    n_aligned = 0
    n_avg = 0
    for sv_id in shared:
        a = bus_a_vectors[sv_id]
        b = bus_b_vectors[sv_id]
        # Pad/truncate to same dim
        dim = max(len(a), len(b))
        if len(a) < dim:
            a = a + [0.0] * (dim - len(a))
        if len(b) < dim:
            b = b + [0.0] * (dim - len(b))
        # Procrustes-align b to a
        try:
            aligned_b = procrustes_alignment([b], [a])
            if aligned_b and len(aligned_b[0]) == dim:
                b = aligned_b[0]
                n_aligned += 1
        except Exception:
            pass
        # Average (consensus = task arithmetic, weights = 0.5 each)
        merged_vec = [(x + y) / 2.0 for x, y in zip(a, b)]
        merged.append(merged_vec)
        n_avg += 1
    return FederatedBus(
        bus_a_vectors=list(bus_a_vectors.values()),
        bus_b_vectors=list(bus_b_vectors.values()),
        shared_sources=shared,
        merged_vectors=merged,
        n_aligned=n_aligned,
        n_avg=n_avg,
    )


# ---------------------------------------------------------------------------
# Pipeline driver — Water → Milk → Honey in Poincaré space
# ---------------------------------------------------------------------------

def hyperbolic_pipeline(water_vec: List[float],
                          clan_centroid: List[float],
                          target_radius: float = 0.3) -> Dict[str, List[float]]:
    """Run the full Water → Milk → Honey pipeline in hyperbolic space.

    Returns a dict with `water`, `milk`, `honey` keys (all in Poincaré ball).
    """
    water = project_water_to_poincare(water_vec)
    milk = mobilize_milk(water, clan_centroid)
    honey = distill_honey(milk, target_radius=target_radius)
    return {"water": water, "milk": milk, "honey": honey}


__all__ = [
    "BALL_EPS",
    "DEFAULT_CURVATURE",
    "project_water_to_poincare",
    "mobilize_milk",
    "distill_honey",
    "ClanRoute",
    "route_via_procrustes",
    "FederatedBus",
    "federate_buses",
    "hyperbolic_pipeline",
]
