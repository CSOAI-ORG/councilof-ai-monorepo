"""csoai-city.adoption_space — J-Space 1 (adoption) → Poincaré vector + signed envelope.

The AI Economy Index geometry: three J-Spaces (adoption / policy / behaviour),
one Procrustes alignment, one signed distance, one index number.

This module is J-Space 1 — the DEMAND surface. It turns adoption data
(Anthropic Economic Index-style: who uses AI, at what rate, in which
occupations/sectors) into a Poincaré-embedded vector, then wraps the raw input
in a signed COSE envelope so the adoption flow becomes externally verifiable —
the thing the indices themselves don't do.

J-Space 2 (policy) and J-Space 3 (behaviour/GSPC) already have their inputs;
this completes the third corner. The Procrustes alignment over the three
vectors is provided by sovos-jspace-pipeline (procrustes_alignment /
poincare_distance — tested).

Design:
  * adopt_to_poincare(occupations: {code: rate}) -> normalized vector,
    projected to the Poincaré ball (radius 0.9) via the estate's hyperbolic
    primitives when available, else a deterministic fallback projection.
  * The raw input + the derived vector both go into the COSE envelope: an
    auditor sees exactly what was signed.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

try:
    from hyperbolic import project_to_ball, poincare_distance  # type: ignore
    HAS_HYPERBOLIC = True
except Exception:  # pragma: no cover
    HAS_HYPERBOLIC = False


def _l2(v: List[float]) -> float:
    return sum(x * x for x in v) ** 0.5


def _normalize(v: List[float]) -> List[float]:
    n = _l2(v)
    if n < 1e-9:
        return [0.0] * len(v)
    return [x / n for x in v]


def adopt_to_poincare(occupations: Dict[str, float],
                      sector_weights: Optional[Dict[str, float]] = None,
                      radius: float = 0.9) -> Tuple[List[float], Dict[str, Any]]:
    """Map adoption data -> Poincaré vector.

    occupations: {occupation_code: ai_usage_rate} (e.g. {"11-1011": 0.42})
    sector_weights: optional {sector: weight} appended as extra dims.
    Returns (vector, meta).
    """
    # sort by code for determinism
    codes = sorted(occupations.keys())
    base = [float(occupations[c]) for c in codes]
    if sector_weights:
        base += [float(sector_weights[k]) for k in sorted(sector_weights.keys())]
    if not base:
        base = [0.0]
    norm = _normalize(base)

    if HAS_HYPERBOLIC:
        vec = project_to_ball(norm, radius)
        method = "poincare-project_to_ball"
    else:
        # deterministic fallback: scale into the ball
        mag = _l2(norm)
        scale = min(radius * 0.95, max(0.01, radius * 0.9))
        vec = [x * (scale / mag if mag > 1e-9 else 1.0) for x in norm]
        method = "fallback-ball-scaled"

    meta = {
        "method": method,
        "n_occupations": len(codes),
        "radius": radius,
        "l2_norm": round(_l2(vec), 6),
    }
    return vec, meta


def wrap_adoption(occupations: Dict[str, float],
                  sector_weights: Optional[Dict[str, float]] = None,
                  period: str = "",
                  source: str = "anthropic-economic-index") -> Dict[str, Any]:
    """J-Space-1 producer: derive the vector AND sign the raw input."""
    vec, meta = adopt_to_poincare(occupations, sector_weights)

    payload = {
        "source": source,
        "period": period,
        "occupations": occupations,
        "sector_weights": sector_weights or {},
        "poincare_vector": [round(x, 6) for x in vec],
        "vector_meta": meta,
    }

    from .cose_wrapper import wrap  # noqa: PLC0415
    r = wrap(payload, source=source)
    if r.signed:
        return {
            "envelope": json.loads(r.envelope),
            "poincare_vector": [round(x, 6) for x in vec],
            "vector_meta": meta,
            "content_id": r.content_id,
            "signed": True,
        }
    return {"signed": False, "error": r.error, "poincare_vector": vec, "vector_meta": meta}


def self_test() -> int:
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # 1. deterministic mapping
    v1, m1 = adopt_to_poincare({"11-1011": 0.42, "15-1252": 0.61})
    v2, m2 = adopt_to_poincare({"11-1011": 0.42, "15-1252": 0.61})
    t("deterministic vector", v1 == v2)
    t("vector in ball", _l2(v1) <= 0.95, f"l2={_l2(v1):.3f}")

    # 2. order-independence (dict key order doesn't change the vector)
    v3, _ = adopt_to_poincare({"15-1252": 0.61, "11-1011": 0.42})
    t("key-order independent", v3 == v1)

    # 3. signed envelope produced with real signature
    r = wrap_adoption({"11-1011": 0.42, "15-1252": 0.61}, period="2026-Q2")
    t("adoption envelope signed", r.get("signed") is True, r.get("error", ""))
    if r.get("envelope"):
        from .cose_wrapper import verify
        t("envelope verifies", bool(verify(r["envelope"]).get("valid")))
    t("vector meta present", r.get("vector_meta", {}).get("method") in
      ("poincare-project_to_ball", "fallback-ball-scaled"))

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
