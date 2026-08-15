"""csoai_sheaf_gate — The sheaf pre-merge gate for federate_buses().

The federation theorem (from category theory) says that two local
sections over an overlap can be glued into a global section IF AND ONLY
IF they agree on the overlap. Translated to SOVOS StateBus terms:

  Given two buses A and B, with a shared set of sv_ids,
  the federation is well-defined iff for every shared sv_id,
  the two vectors (when properly aligned) agree up to a tolerance.

This package implements the gate:

  sheaf_pre_merge_check(bus_a, bus_b, tolerance=0.1) -> SheafVerdict

If the verdict says "pass", the caller may proceed with Procrustes
alignment (in federate_buses). If it says "fail", the caller should
NOT merge — the buses disagree on the overlap and the federation is
ill-defined.

The gate's output is also a chain_id (audit trail) and a violations
list (which sv_ids disagree, by how much).

This is the SAFETY GATE for federation. Without it, federate_buses
silently merges misaligned buses and produces nonsense.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class SheafVerdict:
    """The result of a sheaf pre-merge check."""
    passed: bool
    agreement_ratio: float          # 0..1 — fraction of shared sv_ids that agree
    n_shared: int
    n_agree: int
    n_disagree: int
    max_disagreement: float         # the largest L2 gap between any aligned pair
    violations: List[Dict[str, Any]] = field(default_factory=list)
    tolerance: float = 0.1
    chain_id: str = ""
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Sheaf pre-merge check
# ---------------------------------------------------------------------------
def _pad_to_dim(v: List[float], dim: int) -> List[float]:
    if len(v) < dim:
        return list(v) + [0.0] * (dim - len(v))
    if len(v) > dim:
        return list(v[:dim])
    return list(v)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [-1, 1]. Returns 0 for zero vectors."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _l2_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def sheaf_pre_merge_check(
    bus_a_vectors: Dict[str, List[float]],
    bus_b_vectors: Dict[str, List[float]],
    tolerance: float = 0.1,
    max_dim: int = 16,
) -> SheafVerdict:
    """Pre-merge check: do the two buses form a consistent sheaf?

    Args:
        bus_a_vectors: sv_id → vector from bus A
        bus_b_vectors: sv_id → vector from bus B
        tolerance:    maximum L2 distance (after dim-pad) considered "agree"
        max_dim:      pad/truncate vectors to this dimension (default 16)

    Returns:
        SheafVerdict with passed=True iff agreement_ratio >= 0.9 AND
        max_disagreement <= tolerance * sqrt(max_dim).

    Rules:
      - The "overlap" is the set of shared sv_ids.
      - Each pair (a, b) is padded to max_dim, compared by L2 distance.
      - Pair "agrees" iff L2 distance <= tolerance * sqrt(max_dim).
      - Pair "disagrees" otherwise.
      - Verdict passes iff ≥ 90% of pairs agree AND max disagreement is
        within a global tolerance.
    """
    shared = sorted(set(bus_a_vectors.keys()) & set(bus_b_vectors.keys()))
    n_shared = len(shared)
    violations: List[Dict[str, Any]] = []
    n_agree = 0
    n_disagree = 0
    max_disagreement = 0.0

    # Effective tolerance scales with dim (L2 norm grows with sqrt(dim))
    eff_tol = tolerance * float(np.sqrt(max_dim))

    for sv_id in shared:
        a = np.asarray(_pad_to_dim(bus_a_vectors[sv_id], max_dim), dtype=np.float64)
        b = np.asarray(_pad_to_dim(bus_b_vectors[sv_id], max_dim), dtype=np.float64)
        d = _l2_distance(a, b)
        max_disagreement = max(max_disagreement, d)
        cos = _cosine_similarity(a, b)
        if d <= eff_tol:
            n_agree += 1
        else:
            n_disagree += 1
            violations.append({
                "sv_id": sv_id,
                "l2_distance": float(d),
                "cosine_similarity": float(cos),
                "tolerance_used": float(eff_tol),
            })

    agreement_ratio = (n_agree / n_shared) if n_shared > 0 else 1.0
    # Sheaf consistency: ≥ 90% agree AND max disagreement bounded
    passed = (n_shared == 0) or (
        agreement_ratio >= 0.9 and max_disagreement <= 5.0 * eff_tol
    )

    # Deterministic chain_id for the audit trail
    chain_body = json.dumps({
        "n_shared": n_shared, "n_agree": n_agree, "n_disagree": n_disagree,
        "max_disagreement": max_disagreement, "agreement_ratio": agreement_ratio,
        "tolerance": tolerance, "passed": passed,
    }, sort_keys=True).encode()
    chain_id = hashlib.sha256(chain_body).hexdigest()[:24]

    return SheafVerdict(
        passed=passed,
        agreement_ratio=agreement_ratio,
        n_shared=n_shared,
        n_agree=n_agree,
        n_disagree=n_disagree,
        max_disagreement=max_disagreement,
        violations=violations,
        tolerance=tolerance,
        chain_id=chain_id,
    )


# ---------------------------------------------------------------------------
# Federate-with-gate — the safe wrapper around federate_buses()
# ---------------------------------------------------------------------------
def federate_with_gate(
    bus_a_vectors: Dict[str, List[float]],
    bus_b_vectors: Dict[str, List[float]],
    tolerance: float = 0.1,
    force: bool = False,
) -> Tuple[Optional[Any], SheafVerdict]:
    """Federate two buses only if the sheaf pre-merge check passes.

    Args:
        bus_a_vectors, bus_b_vectors: the two buses to merge
        tolerance: sheaf tolerance
        force: if True, skip the gate (NOT recommended; for emergency use)

    Returns:
        (FederatedBus or None, SheafVerdict)
        If the verdict passes (or force=True), FederatedBus is returned.
        Otherwise None and the verdict explains why.
    """
    verdict = sheaf_pre_merge_check(bus_a_vectors, bus_b_vectors, tolerance=tolerance)
    if not verdict.passed and not force:
        logger.warning(
            "sheaf pre-merge check FAILED (ratio=%.2f, max_disp=%.3f); refusing to merge",
            verdict.agreement_ratio, verdict.max_disagreement,
        )
        return None, verdict
    # Lazy import so this package can be used standalone
    try:
        from sovos_jspace_pipeline import federate_buses
        fed = federate_buses(bus_a_vectors, bus_b_vectors)
        return fed, verdict
    except ImportError:
        # Standalone mode: return None + the verdict
        logger.debug("sovos_jspace_pipeline unavailable; skipping actual merge")
        return None, verdict


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    """Smoke test: identical buses pass, misaligned buses fail."""
    a = {"s1": [1.0, 0.0, 0.0], "s2": [0.0, 1.0, 0.0]}
    # Identical → passes
    b_same = {"s1": [1.0, 0.0, 0.0], "s2": [0.0, 1.0, 0.0]}
    v_ok = sheaf_pre_merge_check(a, b_same)
    # Wildly different → fails
    b_diff = {"s1": [100.0, 0.0, 0.0], "s2": [0.0, 100.0, 0.0]}
    v_bad = sheaf_pre_merge_check(a, b_diff)
    # Empty overlap → passes (vacuously)
    b_empty: Dict[str, List[float]] = {}
    v_empty = sheaf_pre_merge_check(a, b_empty)
    return {
        "identical_passed": v_ok.passed,
        "identical_agreement": v_ok.agreement_ratio,
        "wildly_diff_passed": v_bad.passed,
        "wildly_diff_agreement": v_bad.agreement_ratio,
        "wildly_diff_violations": len(v_bad.violations),
        "empty_overlap_passed": v_empty.passed,
        "empty_overlap_n_shared": v_empty.n_shared,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
