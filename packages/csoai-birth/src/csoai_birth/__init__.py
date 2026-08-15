"""csoai_birth — The Mode 0 birth encoder.

Mode 0 is the *first user experience*: a new user enters the system and
is given a deterministic coordinate in J-space (Poincaré ball). That
coordinate is then anchored to a StateBus "water" event, which downstream
agents subscribe to.

The birth event has these properties:
  - Deterministic: same user_id → same coordinate (sha256-derived).
  - Finite: every user lands at radius ≤ 0.9 inside the ball (so the
    bus has room for moves).
  - Auditable: each birth emits a chain_id (sha256 of the inputs).
  - Replayable: re-running a birth with the same user_id gives the same
    coordinate + chain_id (so we can re-bootstrap from logs).

Public API:
    from csoai_birth import birth, BirthEncoder

    be = BirthEncoder(namespace="iokfarm")
    result = be.encode(user_id="alice@example.com", display_name="Alice")
    print(result.coordinate)   # [0.21, -0.45, 0.83, ...]
    print(result.chain_id)     # "7a4e2b..."

The result is also a StateBus append payload (a "water" event). When
fed to a RedisBus or in-process StateBus, downstream OWEM subscribers
will see the birth as a new user joining their domain.

This is the prerequisite for Modes 1 and 2 (chat and tool call),
because every user message is anchored to their birth coordinate.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BALL_EPS = 1e-5
DEFAULT_RADIUS = 0.85          # birth coordinate lands inside this radius
COORDINATE_DIM = 8             # J-space coordinate dimension (matches StateVector convention)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class BirthResult:
    """The output of one birth event."""
    user_id: str
    display_name: str
    namespace: str
    coordinate: List[float]             # the Poincaré-ball coordinate
    coordinate_norm: float              # ||coordinate||
    radius: float                       # the allowed radius (≤ 0.9)
    chain_id: str                       # sha256 of the birth inputs
    sv_layer: str = "water"             # Bus layer this lands in
    sv_payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_bus_vector(self) -> Dict[str, Any]:
        """Render as a StateBus append payload (compatible with StateVector)."""
        return {
            "source": f"birth:{self.namespace}",
            "layer": self.sv_layer,
            "vector": self.coordinate,
            "payload": {
                "user_id": self.user_id,
                "display_name": self.display_name,
                "chain_id": self.chain_id,
                "coordinate_norm": self.coordinate_norm,
                "radius": self.radius,
                **self.sv_payload,
            },
            "ts": self.ts,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# BirthEncoder
# ---------------------------------------------------------------------------
class BirthEncoder:
    """Encodes users as Poincaré-ball coordinates + audit-able chain_ids.

    Args:
        namespace: domain prefix (e.g. "iokfarm", "meok", "csoai") — keeps
                   birth coordinates separated per product
        radius:    maximum coordinate norm (default 0.85; the ball's
                   boundary is at 1.0, so 0.85 leaves room for moves)
        dim:       coordinate dimension (default 8)
    """

    def __init__(self, namespace: str = "sovos",
                 radius: float = DEFAULT_RADIUS,
                 dim: int = COORDINATE_DIM):
        if radius >= 1.0:
            raise ValueError(f"radius must be < 1.0 (Poincaré ball boundary), got {radius}")
        if radius <= 0:
            raise ValueError(f"radius must be > 0, got {radius}")
        if dim < 2:
            raise ValueError(f"dim must be >= 2, got {dim}")
        self.namespace = namespace
        self.radius = radius
        self.dim = dim

    def encode(self, user_id: str, display_name: str = "",
               extra: Optional[Dict[str, Any]] = None) -> BirthResult:
        """Encode a user as a Poincaré-ball coordinate.

        Steps:
          1. Hash user_id + namespace with sha256 → 32 bytes
          2. Expand to dim floats (Box-Muller for normal distribution)
          3. Normalize to length 1, scale to radius
          4. chain_id = sha256 of (user_id, display_name, namespace, coordinate)
          5. Return BirthResult with bus-vector payload
        """
        # 1. Hash → 32 bytes
        body = f"{self.namespace}::{user_id}".encode()
        digest = hashlib.sha256(body).digest()  # 32 bytes
        # 2. Expand to dim floats via Box-Muller
        coord = self._bytes_to_normalized(digest)
        # 3. Normalize to length 1, scale to radius
        coord = self._project_to_ball(coord, self.radius)
        # 4. chain_id from the canonical birth string
        chain_body = json.dumps({
            "namespace": self.namespace, "user_id": user_id,
            "display_name": display_name, "coordinate": coord.tolist(),
        }, sort_keys=True).encode()
        chain_id = hashlib.sha256(chain_body).hexdigest()[:24]
        # 5. Build result
        return BirthResult(
            user_id=user_id, display_name=display_name,
            namespace=self.namespace, coordinate=coord.tolist(),
            coordinate_norm=float(np.linalg.norm(coord)),
            radius=self.radius, chain_id=chain_id,
            sv_payload={"extra": extra or {}},
        )

    def _bytes_to_normalized(self, digest: bytes) -> np.ndarray:
        """Expand 32 bytes into a dim-length vector via Box-Muller.

        Box-Muller turns 2 uniform [0,1) values into 2 standard-normal
        values. We pair up bytes as (u1, u2) until we have enough normal
        samples, then truncate to `dim`.
        """
        # 1. Convert bytes to floats in [0, 1)
        n_pairs = (self.dim + 1) // 2  # ceil(dim/2)
        u1 = np.zeros(n_pairs)
        u2 = np.zeros(n_pairs)
        for i in range(n_pairs):
            b1 = digest[(2 * i) % 32]
            b2 = digest[(2 * i + 1) % 32]
            u1[i] = max(b1 / 255.0, 1e-9)  # avoid log(0)
            u2[i] = b2 / 255.0
        # 2. Box-Muller transform
        normals = np.zeros(2 * n_pairs)
        normals[0::2] = np.sqrt(-2 * np.log(u1)) * np.cos(2 * np.pi * u2)
        normals[1::2] = np.sqrt(-2 * np.log(u1)) * np.sin(2 * np.pi * u2)
        return normals[:self.dim]

    def _project_to_ball(self, v: np.ndarray, radius: float) -> np.ndarray:
        """Normalize to length 1, then scale to radius.

        If v is zero (vanishingly unlikely with normal-distributed input),
        fall back to a canonical "origin" coordinate.
        """
        n = float(np.linalg.norm(v))
        if n < 1e-12:
            # Deterministic fallback: all zeros → origin
            return np.zeros(self.dim)
        # Normalize to unit length, then scale
        v_unit = v / n
        return v_unit * radius


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------
_default_encoder: Optional[BirthEncoder] = None


def encoder(namespace: str = "sovos") -> BirthEncoder:
    """Return the default BirthEncoder (singleton per namespace)."""
    global _default_encoder
    if _default_encoder is None or _default_encoder.namespace != namespace:
        _default_encoder = BirthEncoder(namespace=namespace)
    return _default_encoder


def birth(user_id: str, display_name: str = "",
          namespace: str = "sovos",
          extra: Optional[Dict[str, Any]] = None) -> BirthResult:
    """One-liner birth: encode a user as a Poincaré-ball coordinate."""
    return encoder(namespace).encode(user_id, display_name=display_name, extra=extra)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    """Smoke test: deterministic, in-ball, distinct users land apart."""
    be = BirthEncoder(namespace="self-test")
    a = be.encode("alice@example.com", "Alice")
    b = be.encode("bob@example.com", "Bob")
    same = be.encode("alice@example.com", "Alice")
    # Same user → same coord (determinism)
    deterministic = a.coordinate == same.coordinate
    # Different users → different coords
    different = a.coordinate != b.coordinate
    # Inside the ball
    in_ball = all(c < 1.0 for c in a.coordinate) and a.coordinate_norm < 1.0
    return {
        "deterministic": deterministic,
        "different_users_distinct": different,
        "coordinate_inside_ball": in_ball,
        "chain_id_len": len(a.chain_id),
        "coordinate_dim": len(a.coordinate),
        "sample_coordinate": a.coordinate[:3],
        "sample_norm": a.coordinate_norm,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
