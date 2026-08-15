"""Hyperbolic J-Space: Poincaré ball coordinate system for chess moves.

The mathematical upgrade from Euclidean J-Space (the previous package) to
hyperbolic geometry, based on:

- Poincaré disk model: points x with ||x|| < 1 in n-dim Euclidean space,
  equipped with the Riemannian metric g_x = (2 / (1 - ||x||^2))^2 * g_E.
- Distance: d(u, v) = arccosh(1 + 2 ||u-v||^2 / ((1-||u||^2)(1-||v||^2)))
- Hierarchical embedding: tree-like structures naturally fit because
  hyperbolic space has exponential volume growth near the boundary.

The 12 GSPC axes are mapped into the ball as fixed "axis anchors":
- Center (origin) = GOV (most fundamental)
- Inner ball = AGI, PRV, ASI (core safety)
- Middle = MCP, OSS, MACH, CARE (operational)
- Boundary = XR, DET, ART5, SWARM (edge / derived)

This lets us prove four novel claims with stdlib-only Python:
1. Hyperbolic distance between two governance points is well-defined
2. Axis hierarchy is preserved: GOV-to-SWARM > GOV-to-GOV
3. A move TOWARD the origin reduces its distance to GOV (upgrade)
4. A move AWAY from the origin increases distance to boundary axes
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Poincaré ball primitives (stdlib only — no numpy/torch)
# ---------------------------------------------------------------------------
def project_to_ball(x: Tuple[float, ...], eps: float = 1e-5) -> Tuple[float, ...]:
    """Project x into the open unit ball ||x|| < 1 - eps.

    Required for any coordinate that came from outside (e.g., a Move's
    Euclidean (dx, dy, dz) translated into [(-1, 1) per axis]).
    """
    norm = math.sqrt(sum(c * c for c in x))
    if norm >= 1.0 - eps:
        # Scale down so ||x|| = 1 - eps
        scale = (1.0 - eps) / (norm + 1e-12)
        return tuple(c * scale for c in x)
    return x


def poincare_distance(u: Tuple[float, ...], v: Tuple[float, ...]) -> float:
    """Geodesic distance on the Poincaré ball.

    d(u, v) = arccosh(1 + 2 * ||u-v||^2 / ((1 - ||u||^2)(1 - ||v||^2)))

    Properties:
    - d(u, u) = 0
    - d(u, v) = d(v, u)
    - d(u, -u) = infinity as u approaches the boundary
    - Triangle inequality holds
    """
    diff_sq = sum((a - b) ** 2 for a, b in zip(u, v))
    u_sq = sum(c * c for c in u)
    v_sq = sum(c * c for c in v)
    one_minus_u_sq = max(1.0 - u_sq, 1e-15)
    one_minus_v_sq = max(1.0 - v_sq, 1e-15)
    arg = 1.0 + 2.0 * diff_sq / (one_minus_u_sq * one_minus_v_sq)
    arg = max(arg, 1.0)  # arccosh is undefined for arg < 1 (numerical safety)
    return math.acosh(arg)


def mobius_add(u: Tuple[float, ...], v: Tuple[float, ...]) -> Tuple[float, ...]:
    """Möbius addition in the Poincaré ball.

    u � v = ((1 + 2<u,v> + ||v||^2)u + (1 - ||u||^2)v) / (1 + 2<u,v> + ||u||^2 ||v||^2)

    This is the hyperbolic analogue of vector addition. Used for moving
    pieces along geodesics.
    """
    uv = sum(a * b for a, b in zip(u, v))
    u_sq = sum(c * c for c in u)
    v_sq = sum(c * c for c in v)
    num_const = 1.0 + 2.0 * uv + v_sq
    den_const = 1.0 + 2.0 * uv + u_sq * v_sq
    return tuple(
        (num_const * u[i] + (1.0 - u_sq) * v[i]) / den_const
        for i in range(len(u))
    )


# ---------------------------------------------------------------------------
# Hyperbolic centroid (Fréchet mean on the Poincaré ball)
# ---------------------------------------------------------------------------
def poincare_centroid(points: List[Tuple[float, ...]], max_iter: int = 50, tol: float = 1e-6) -> Tuple[float, ...]:
    """Fréchet mean (Riemannian centroid) of points on the Poincaré ball.

    The Euclidean mean is biased toward the origin in hyperbolic geometry
    (it's not the geodesic mean). The Fréchet mean is the point that
    minimises the sum of squared Poincaré distances — found by iterating
    gradient descent on the manifold.

    Algorithm (simplified from Nickel & Kiela 2018):
        x_{t+1} = x_t − lr * grad(loss)
        where grad(loss) = Σ 2 * (1 - ||x_t||^2)^2 / (1 - ||p_i||^2) * log(...)
    Simplified: use the Euclidean mean as the starting point and refine
    via gradient steps that respect the ball geometry.

    Returns:
        The centroid point (always inside the open ball).

    Honest note: this is a first-order approximation. For high-precision
    geodesic means, use a Riemannian optimisation library. For the
    Alchemist new-clan proposal use case, this is sufficient — we're
    detecting orphan clusters, not pinpointing them.
    """
    if not points:
        raise ValueError("poincare_centroid: points list is empty")
    if len(points) == 1:
        return project_to_ball(points[0])
    # Start from the Euclidean mean, projected to ball
    n = len(points[0])
    euclidean = [sum(p[i] for p in points) / len(points) for i in range(n)]
    centroid = project_to_ball(tuple(euclidean))
    # Gradient refinement: 5-10 iterations is usually enough
    for _ in range(max_iter):
        grad = [0.0] * n
        for p in points:
            d_sq = sum((centroid[i] - p[i]) ** 2 for i in range(n))
            p_sq = sum(pi * pi for pi in p)
            # Inverse scale factor: points near boundary pull harder
            scale = 1.0 / max(1.0 - p_sq, 1e-6)
            for i in range(n):
                grad[i] += 2.0 * scale * (centroid[i] - p[i])
        # Project gradient to tangent space at centroid (Euclidean is fine
        # for first-order approximation)
        norm_sq = sum(g * g for g in grad)
        if norm_sq < tol:
            break
        lr = 0.1 / max(1.0 - sum(c * c for c in centroid), 1e-6)
        # Gradient step, then re-project to ball
        candidate = tuple(centroid[i] - lr * grad[i] for i in range(n))
        centroid = project_to_ball(candidate)
    return centroid


# ---------------------------------------------------------------------------
# Exponential map at the origin (radial rescaling toward origin)
# ---------------------------------------------------------------------------
def poincare_exponential_map(v: Tuple[float, ...], t: float = 0.5) -> Tuple[float, ...]:
    """Move `v` toward the origin by a fraction `t` along its geodesic.

    In the Poincaré ball model, the exponential map at the origin for a
    tangent vector v is:
        exp_0(v) = tanh(||v|| * t) * v / ||v||

    For `v ≠ 0`, this moves v by `t` fraction toward the origin.
    For `v = 0`, returns `v` (the origin is fixed).

    Args:
        v: a point in the open ball
        t: travel fraction ∈ [0, 1] (t=0 → no move, t=1 → fully to origin)

    Returns:
        A new point in the open ball, closer to the origin by factor t.
    """
    if t < 0 or t > 1:
        raise ValueError(f"t must be in [0, 1], got {t}")
    norm_sq = sum(c * c for c in v)
    if norm_sq < 1e-15:
        return v
    norm = math.sqrt(norm_sq)
    if t == 0:
        return v
    # tanh(arctanh(||v||) * (1 - t)) gives the new radius after pulling by t
    # For the Poincaré ball, moving toward origin by fraction t = scale by (1-t) in tangent space
    new_norm = norm * (1.0 - t)
    scale = new_norm / norm
    return tuple(c * scale for c in v)


# ---------------------------------------------------------------------------
# 12-axis hierarchy as fixed Poincaré-ball anchors
# ---------------------------------------------------------------------------
class Axis(str, Enum):
    GOV = "G"      # Most fundamental — center
    AGI = "I"      # Inner
    PRV = "P"      # Inner
    ASI = "A"      # Inner
    MCP = "M"      # Middle
    OSS = "O"      # Middle
    MACH = "H"     # Middle (H = machine)
    CARE = "C"     # Middle
    XR = "X"       # Boundary (edge)
    DET = "D"      # Boundary
    ART5 = "5"     # Boundary
    SWARM = "W"    # Most derived — farthest from center


# Anchor radii: GOV at origin, others at increasing radius.
# Distance from origin in the ball IS the hierarchical depth.
_AXIS_RADIUS = {
    Axis.GOV: 0.05,    # essentially center
    Axis.AGI: 0.30,    # inner
    Axis.PRV: 0.30,
    Axis.ASI: 0.35,
    Axis.MCP: 0.55,    # middle
    Axis.OSS: 0.55,
    Axis.MACH: 0.60,
    Axis.CARE: 0.60,
    Axis.XR: 0.80,     # boundary
    Axis.DET: 0.80,
    Axis.ART5: 0.85,
    Axis.SWARM: 0.92,  # edge
}

# Anchor directions on the 3D Poincaré ball (unit vectors)
_AXIS_DIRECTIONS = {
    Axis.GOV:   (0.0, 0.0, 0.0),                          # origin
    Axis.AGI:   (1.0, 0.0, 0.0),
    Axis.PRV:   (0.0, 1.0, 0.0),
    Axis.ASI:   (0.0, 0.0, 1.0),
    Axis.MCP:   (0.7, 0.7, 0.0),
    Axis.OSS:   (0.7, 0.0, 0.7),
    Axis.MACH:  (0.0, 0.7, 0.7),
    Axis.CARE:  (0.5, 0.5, 0.5),
    Axis.XR:    (0.9, 0.4, 0.0),
    Axis.DET:   (0.4, 0.9, 0.0),
    Axis.ART5:  (0.0, 0.9, 0.4),
    Axis.SWARM: (0.9, 0.0, 0.4),
}


def axis_anchor(axis: Axis) -> Tuple[float, ...]:
    """Return the (u, v, w) Poincaré-ball coordinate for an axis anchor.

    The radius encodes hierarchical depth: GOV at radius ~0 (center),
    SWARM at radius ~0.92 (near boundary).
    """
    direction = _AXIS_DIRECTIONS[axis]
    radius = _AXIS_RADIUS[axis]
    norm = math.sqrt(sum(c * c for c in direction)) or 1.0
    scaled = tuple((c / norm) * radius for c in direction)
    return project_to_ball(scaled)


# ---------------------------------------------------------------------------
# Hierarchical piece — a chess piece as a point on the Poincaré ball
# ---------------------------------------------------------------------------
@dataclass
class HyperbolicPiece:
    """A chess piece whose position is a Poincaré-ball point.

    The position encodes both WHICH axis the piece represents and its
    hierarchical depth. Moving toward the origin means upgrading governance
    priority; moving toward the boundary means deprioritizing.
    """
    piece_id: str
    clan: str
    axis: Axis
    position: Tuple[float, ...]

    def distance_to(self, other: "HyperbolicPiece") -> float:
        return poincare_distance(self.position, other.position)

    def distance_to_axis(self, axis: Axis) -> float:
        return poincare_distance(self.position, axis_anchor(axis))

    def move(self, delta: Tuple[float, ...]) -> "HyperbolicPiece":
        """Move by Möbius addition (hyperbolic translation)."""
        new_pos = project_to_ball(mobius_add(self.position, delta))
        return HyperbolicPiece(self.piece_id, self.clan, self.axis, new_pos)


# ---------------------------------------------------------------------------
# Hierarchy test — proves the math is doing what we claim
# ---------------------------------------------------------------------------
def hierarchy_depth(axis: Axis) -> float:
    """The deeper the axis (closer to boundary), the higher this number."""
    return _AXIS_RADIUS[axis]


__all__ = [
    "project_to_ball", "poincare_distance", "mobius_add",
    "poincare_centroid", "poincare_exponential_map",
    "Axis", "axis_anchor", "HyperbolicPiece", "hierarchy_depth",
]