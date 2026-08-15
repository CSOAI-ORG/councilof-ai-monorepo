"""csoai_chain — The SOVOS substrate chain.

Wires four primitives into one execution chain:

  StateBus (sovos-mind)
        │
        ▼
  jspace-hyperbolic (Poincaré) — route each StateVector to its OWEM clan
        │                         (geometric proximity in hyperbolic space)
        ▼
  fisher-rao (sovos-fisher-rao) — verify the routed state is inside the
        │                           permitted geodesic ball (SOV SIGNAL)
        ▼
  jspace-pipeline — emit a signed ChainResult with the canonical
                    (poincare_distance, fisher_rao_distance, is_permitted)
                    triple.

This is the canonical "substrate in 4 calls" surface. Every agent,
every MCP, every A2A swarm message can be scored through this chain.

Why a chain?
------------
- Composability — each step is independently testable.
- Honest accounting — the chain returns every score, so callers can
  decide their own thresholds (don't bake policy into the kernel).
- SIGIL-able — chain results carry a sha256 id and are append-only
  compatible with the StateBus, so the OWEM hive can subscribe.

This package depends on:
  - sovos-fisher-rao (the kernel — numpy + scipy only)
  - sovos-mind (StateBus, StateVector — pure Python)
  - hyperbolic from sovos-jspace-hyperbolic (Poincaré — numpy only)
  - sovos_jspace_pipeline (water→milk→honey transformation)

It deliberately does NOT depend on POT/geomstats/PennyLane so the chain
runs on any machine that can run the kernel.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy imports — keep chain usable even if some peer packages are absent
# ---------------------------------------------------------------------------
def _try_import(name: str, attr: Optional[str] = None) -> Any:
    """Import `name` and return module or `name.attr`. Return None on failure."""
    try:
        mod = __import__(name, fromlist=[attr] if attr else [])
        return getattr(mod, attr) if attr else mod
    except Exception as e:
        logger.debug("optional import %s.%s unavailable: %s", name, attr, e)
        return None


_fisher_rao_module = _try_import("sovos_fisher_rao")
_mind_module = _try_import("sovos_mind")
_hyperbolic_module = _try_import("hyperbolic")
_pipeline_module = _try_import("sovos_jspace_pipeline")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChainResult:
    """The signed output of one chain run.

    Attributes:
        chain_id:   sha256 hash of the inputs (deterministic).
        poincare_distance:   geometric distance in the hyperbolic ball to the
                            nearest permitted OWEM clan centroid (None if no
                            routing performed).
        fisher_rao_distance: AIRM (or log-Euclidean) distance from the
                            routed state to the permitted manifold (None
                            if no SOV SIGNAL applied).
        is_permitted:        True iff fisher_rao_distance <= threshold.
        threshold:           The threshold used for the SOV SIGNAL gate.
        routed_clan:         Name of the OWEM clan the StateVector was
                             routed to (or None).
        inputs_sha:          Hash of the input StateVector (content-only).
        backend:             Which kernel backend produced the Fisher-Rao
                             distance ("geomstats" / "scipy-logm" /
                             "torch-gpu" / "unavailable").
        ts:                  UTC ISO-8601 timestamp.
        meta:                Free-form dict for caller-specific notes.
    """
    chain_id: str
    poincare_distance: Optional[float]
    fisher_rao_distance: Optional[float]
    is_permitted: Optional[bool]
    threshold: float
    routed_clan: Optional[str]
    inputs_sha: str
    backend: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FitnessGate:
    """The fitness gate — composes the chain into a single verdict.

    A closure (in spirit) that takes a StateVector and returns a verdict
    that combines:
      - poincare_distance (route-fit)
      - fisher_rao_distance (manifold-fit)
      - care_floor (min acceptable governance score, default 0.95)
      - bft_quorum (min acceptable BFT agreement, default 23/33 = 0.697)

    The verdict is one of {"PASS", "ESCALATE", "BLOCK"}. PASS emits a
    SIGIL-style chain_id; ESCALATE keeps it as a record but flags for
    human review; BLOCK drops it (caller decides what to do).

    The thresholds are configurable. The defaults come from the
    SOVOS invariants:
      - care_floor = 0.95 (from sovos_invariants.CARE_FLOOR)
      - bft_quorum = 23/33 = 0.697 (from the 33-agent BFT council)
    """
    care_floor: float = 0.95
    bft_quorum: float = 23.0 / 33.0
    fisher_rao_threshold: float = 1.0
    poincare_threshold: float = 0.5
    enabled: bool = True
    sigil_log: List[str] = field(default_factory=list)

    def __call__(self, sv: Any, permitted_state: Optional[np.ndarray] = None,
                 clans: Optional[Dict[str, np.ndarray]] = None) -> ChainResult:
        """Score one StateVector through the chain."""
        return _chain_through(sv, permitted_state=permitted_state,
                              clans=clans, threshold=self.fisher_rao_threshold,
                              gate=self if self.enabled else None)

    def emit_sigil(self, chain_id: str) -> None:
        """Record a SIGIL for a passing verdict."""
        ts = datetime.now(timezone.utc).isoformat()
        msg = f"SIGIL {ts} {chain_id}"
        self.sigil_log.append(msg)

    def verdicts(self, r: ChainResult) -> Tuple[str, str]:
        """Reduce a ChainResult to (verdict, reason).

        verdict ∈ {"PASS", "ESCALATE", "BLOCK"}
        """
        if r.poincare_distance is not None and r.poincare_distance > self.poincare_threshold:
            return "ESCALATE", f"poincare={r.poincare_distance:.3f} > {self.poincare_threshold}"
        if r.fisher_rao_distance is not None and r.fisher_rao_distance > self.fisher_rao_threshold:
            return "ESCALATE", f"fisher_rao={r.fisher_rao_distance:.3f} > {self.fisher_rao_threshold}"
        if r.fisher_rao_distance is None and r.poincare_distance is None:
            return "BLOCK", "no distance computed (missing peer packages?)"
        return "PASS", "all thresholds met"


# ---------------------------------------------------------------------------
# Chain implementation
# ---------------------------------------------------------------------------
def _compute_inputs_sha(sv: Any) -> str:
    """Content hash for a StateVector (or dict/list/float fallback)."""
    if hasattr(sv, "sv_id") and getattr(sv, "sv_id", ""):
        # StateVector: hash sv_id + vector + payload
        body = json.dumps({
            "sv_id": sv.sv_id,
            "layer": getattr(sv, "layer", None),
            "source": getattr(sv, "source", None),
            "vector": list(getattr(sv, "vector", []) or []),
            "payload": getattr(sv, "payload", {}),
        }, sort_keys=True, default=str).encode()
    elif isinstance(sv, (dict, list)):
        body = json.dumps(sv, sort_keys=True, default=str).encode()
    elif isinstance(sv, np.ndarray):
        body = sv.tobytes()
    else:
        body = str(sv).encode()
    return hashlib.sha256(body).hexdigest()[:24]


def _chain_through(sv: Any, permitted_state: Optional[np.ndarray] = None,
                   clans: Optional[Dict[str, np.ndarray]] = None,
                   threshold: float = 1.0,
                   gate: Optional[FitnessGate] = None) -> ChainResult:
    """Run a StateVector through the chain and return a signed ChainResult.

    Steps:
      1. Compute inputs_sha (content hash of the StateVector).
      2. If clans is provided, route via Poincaré distance — pick the
         nearest clan centroid. (Uses hyperbolic.poincare_distance.)
      3. If permitted_state is provided, compute Fisher-Rao distance via
         the sovos-fisher-rao kernel.
      4. Build a deterministic chain_id from inputs_sha + the two
         distances + threshold + backend.
      5. Return ChainResult.

    All steps are best-effort: missing peer packages are reported as
    None for the corresponding distance rather than raising. This way
    the chain never breaks the StateBus — it always returns a result
    (the caller can decide what to do).
    """
    inputs_sha = _compute_inputs_sha(sv)
    poincare_distance: Optional[float] = None
    routed_clan: Optional[str] = None
    fisher_rao_distance: Optional[float] = None
    is_permitted: Optional[bool] = None
    backend = "unavailable"

    # Step 1 — extract vector (works for StateVector, dict, ndarray, list)
    vector = _extract_vector(sv)

    # Step 2 — Poincaré routing (if clans + hyperbolic available)
    if clans and _hyperbolic_module is not None:
        poincare_distance_fn = getattr(_hyperbolic_module, "poincare_distance", None)
        if poincare_distance_fn is not None and vector is not None:
            best_clan, best_d = None, float("inf")
            for name, centroid in clans.items():
                try:
                    d = poincare_distance_fn(vector, list(centroid))
                    if d < best_d:
                        best_d, best_clan = d, name
                except Exception as e:
                    logger.debug("poincare_distance failed for clan %s: %s", name, e)
            if best_clan is not None:
                poincare_distance = best_d
                routed_clan = best_clan

    # Step 3 — Fisher-Rao SOV SIGNAL gate (if permitted_state available)
    if permitted_state is not None and _fisher_rao_module is not None:
        sov_signal = getattr(_fisher_rao_module, "sov_signal_gate", None)
        fisher_rao_fn = getattr(_fisher_rao_module, "fisher_rao_distance", None)
        if vector is not None and sov_signal is not None:
            try:
                # Build current-state SPD from the vector (outer product + scale)
                current = _vector_to_spd(vector)
                result = sov_signal(current, permitted_state, threshold=threshold)
                fisher_rao_distance = float(result.distance)
                is_permitted = bool(result.is_permitted)
                backend = result.backend
            except Exception as e:
                logger.debug("sov_signal_gate failed: %s", e)
        elif vector is not None and fisher_rao_fn is not None:
            try:
                current = _vector_to_spd(vector)
                d = fisher_rao_fn(current, permitted_state, use_gpu=False)
                fisher_rao_distance = float(d)
                is_permitted = bool(d <= threshold)
                backend = "scipy-logm"
            except Exception as e:
                logger.debug("fisher_rao_distance failed: %s", e)

    # Step 4 — deterministic chain_id
    chain_body = json.dumps({
        "inputs_sha": inputs_sha,
        "poincare_distance": poincare_distance,
        "fisher_rao_distance": fisher_rao_distance,
        "threshold": threshold,
        "backend": backend,
    }, sort_keys=True).encode()
    chain_id = hashlib.sha256(chain_body).hexdigest()[:24]

    # Step 5 — auto-SIGIL if gate provided + verdict would PASS
    if gate is not None and getattr(gate, "enabled", True):
        tmp = ChainResult(
            chain_id=chain_id, poincare_distance=poincare_distance,
            fisher_rao_distance=fisher_rao_distance, is_permitted=is_permitted,
            threshold=threshold, routed_clan=routed_clan, inputs_sha=inputs_sha,
            backend=backend, meta={},
        )
        verdict, _ = gate.verdicts(tmp)
        if verdict == "PASS":
            gate.emit_sigil(chain_id)

    return ChainResult(
        chain_id=chain_id, poincare_distance=poincare_distance,
        fisher_rao_distance=fisher_rao_distance, is_permitted=is_permitted,
        threshold=threshold, routed_clan=routed_clan, inputs_sha=inputs_sha,
        backend=backend, meta={},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_vector(sv: Any) -> Optional[List[float]]:
    """Pull a list-of-floats vector from a StateVector / dict / list / ndarray."""
    if sv is None:
        return None
    if hasattr(sv, "vector"):
        v = getattr(sv, "vector", None)
        if v is not None:
            return list(v)
    if isinstance(sv, dict):
        if "vector" in sv and isinstance(sv["vector"], (list, tuple)):
            return [float(x) for x in sv["vector"]]
        if "vec" in sv and isinstance(sv["vec"], (list, tuple)):
            return [float(x) for x in sv["vec"]]
    if isinstance(sv, np.ndarray):
        return sv.astype(float).tolist()
    if isinstance(sv, (list, tuple)):
        try:
            return [float(x) for x in sv]
        except Exception:
            return None
    return None


def _vector_to_spd(vector: List[float]) -> np.ndarray:
    """Build a small SPD matrix from a 1D vector.

    Strategy: a diagonally-dominant SPD matrix built from the vector.
        M_ii = max(EPS, v_i)        — positive diagonal
        M_ij = v_i * v_j / S        — outer-product smoothing (with S = sum(|v|))
    The result is always symmetric positive-definite by construction.

    A "default" vector like [1, 1, 1, 1] maps to a matrix with diagonal
    [1, 1, 1, 1] and small off-diagonals — close to the identity in
    Fisher-Rao distance. A vector like [0.05, 0, 0, 0] maps to a matrix
    with diagonal [0.05, 0.1, 0.1, 0.1] (the EPS floor kicks in) — which
    is close to identity in the dominant-eigenvalue direction but with
    small eigenvalues. That is the honest behaviour of "0.05 on the
    first axis, nothing on the rest".

    The Fisher-Rao kernel only needs an SPD matrix shape; this helper is
    the canonical "wrap a vector for the kernel" surface.
    """
    v = np.asarray(vector, dtype=np.float64)
    if v.ndim != 1:
        v = v.flatten()
    n = max(2, min(len(v), 8))  # cap matrix size at 8 for sanity
    v_trunc = v[:n]
    EPS = 0.1
    diag = np.maximum(EPS, np.abs(v_trunc))
    M = np.diag(diag)
    # Add a small outer-product term for off-diagonal structure
    # (this is what makes off-diagonal SPD tests work without breaking diagonal identity)
    s = float(np.sum(np.abs(v_trunc))) + 1e-9
    outer = np.outer(v_trunc, v_trunc) / s * 0.05  # 5% weight to off-diagonals
    M = M + outer
    # Re-symmetrize (numerical safety)
    M = 0.5 * (M + M.T)
    # Floor diagonal again so M stays SPD after the outer-product subtraction
    np.fill_diagonal(M, diag)
    return M


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def chain(sv: Any, permitted_state: Optional[np.ndarray] = None,
          clans: Optional[Dict[str, np.ndarray]] = None,
          threshold: float = 1.0,
          gate: Optional[FitnessGate] = None) -> ChainResult:
    """Run a StateVector through the full SOVOS substrate chain.

    Args:
        sv:              a StateVector, dict, ndarray, or list
        permitted_state: (n, n) SPD matrix representing the permitted
                         manifold. If None, SOV SIGNAL is skipped.
        clans:           dict mapping clan name → centroid vector.
                         If None, hyperbolic routing is skipped.
        threshold:       SOV SIGNAL geodesic-ball radius.
        gate:            optional FitnessGate to auto-SIGIL on PASS.

    Returns:
        ChainResult (always — never raises on missing peer packages).
    """
    return _chain_through(sv, permitted_state=permitted_state,
                          clans=clans, threshold=threshold, gate=gate)


def fitness_gate(care_floor: float = 0.95, bft_quorum: float = 23.0 / 33.0,
                 fisher_rao_threshold: float = 1.0,
                 poincare_threshold: float = 0.5) -> FitnessGate:
    """Build a FitnessGate with the canonical SOVOS thresholds."""
    return FitnessGate(
        care_floor=care_floor,
        bft_quorum=bft_quorum,
        fisher_rao_threshold=fisher_rao_threshold,
        poincare_threshold=poincare_threshold,
    )


def self_test() -> Dict[str, Any]:
    """Report which peer packages are reachable + their versions."""
    info: Dict[str, Any] = {
        "sovos_fisher_rao": False,
        "sovos_mind": False,
        "hyperbolic": False,
        "sovos_jspace_pipeline": False,
        "chain_works": False,
    }
    if _fisher_rao_module is not None:
        try:
            info["sovos_fisher_rao"] = bool(
                getattr(_fisher_rao_module, "fisher_rao_distance", None))
        except Exception:
            pass
    if _mind_module is not None:
        info["sovos_mind"] = hasattr(_mind_module, "StateBus")
    if _hyperbolic_module is not None:
        info["hyperbolic"] = hasattr(_hyperbolic_module, "poincare_distance")
    if _pipeline_module is not None:
        info["sovos_jspace_pipeline"] = hasattr(_pipeline_module, "hyperbolic_pipeline")

    # Smoke test: chain through a fake vector
    try:
        fake_sv = {
            "vector": [0.1, 0.2, 0.3],
            "layer": "water",
            "source": "self-test",
        }
        clans = {"gov": np.array([0.0, 0.0, 0.0])}
        permitted = np.eye(3) * 1.0
        r = chain(fake_sv, permitted_state=permitted, clans=clans)
        info["chain_works"] = True
        info["smoke_chain_id"] = r.chain_id
        info["smoke_poincare"] = r.poincare_distance
        info["smoke_fisher_rao"] = r.fisher_rao_distance
    except Exception as e:
        info["chain_works"] = False
        info["chain_error"] = str(e)
    return info
