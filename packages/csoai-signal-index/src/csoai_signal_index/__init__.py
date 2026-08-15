"""csoai-signal-index — The SOV SIGNAL index instruments.

This implements the *computable core* of the SOV SIGNAL index, per the
design laws in the market dossier (August 2026):

  Law 1 — Anchored, not reported (SOFR): the index must be computed from
          signed, append-only ChainResults, never vendor self-reporting.
  Law 2 — Distance, not score (Merton): publish the distance-to-permitted-
          manifold; let the market calibrate its own failure frequencies.
  Law 4 — σ-native (Glicko): every constituent carries an uncertainty σ;
          high-σ constituents self-down-weight via precision Π = 1/σ².
  Law 5 — Systemic sub-index (Basel): how much of the economy's AI trust
          sits on one manifold → eigenvalue-concentration of the
          cross-constituent distance covariance (a Vasicek-style
          single-risk-factor measure).

What each function does:
  - trusted_from_chain_result(r): extract the SOFR-anchored inputs
    (distance, permitted_radius, sigma) from a signed ChainResult.
  - constituent_score(...): one constituent's distance-to-default reading.
  - precision_weight(...): Glicko-style 1/σ² down-weighting of high-σ.
  - systemic_correlation_index(distances, sigma): the Basel sub-index —
    a number in [0,1] = how much cross-constituent trust variance is
    explained by the first (dominant) factor. High = monoculture.
  - aggregate_sov_signal(...): precision-weighted geometric composite
    of constituent scores (Fisher-ideal-style composition), the headline
    "trust gauge" number.

Honest scope: this is the NUMERICS of the index — the signed ChainResults
that feed it come from sovos-chain (already shipped). Provenance of each
constituent's σ is the caller's job (σ-calibration package). This package
enforces the mathematics and the SOFR-style anchoring, not the audit
chain itself.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ConstituentScore:
    """One constituent's distance-to-default + precision value."""
    constituent_id: str
    distance: float            # distance to permitted manifold (>=0)
    sigma: float               # uncertainty (>=0; 1/sigma^2 = precision)
    permitted_radius: float    # the allowed radius (threshold)
    precision: float           # 1/sigma^2 (Glicko law)
    is_trusted: bool           # distance <= permitted_radius
    chain_id: str = ""         # anchoring id of the source ChainResult


@dataclass
class SovSignalVerdict:
    """The index output for a portfolio of constituents."""
    n_constituents: int
    mean_distance: float
    aggregate_score: float         # the "trust gauge" (precision-weighted)
    systemic_correlation: float    # Basel sub-index in [0,1]
    multiculture_ccy: bool         # True if NOT dominated by one manifold
    high_sigma_share: float        # fraction of weight on sigma > 1.0
    constituents: List[Dict[str, Any]]
    article_zero: bool
    chain_id: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core instruments
# ---------------------------------------------------------------------------
def trusted_from_chain_result(r: Any) -> ConstituentScore:
    """Extract a constituent score from a signed ChainResult (SOFR anchor).

    Accepts any object with .distance (or .fisher_rao_distance),
    .threshold, and an optional .sigma / .meta['sigma']. Missing sigma
    defaults to 1.0 (unit uncertainty = neutral).
    """
    distance = getattr(r, "distance", None)
    if distance is None:
        distance = getattr(r, "fisher_rao_distance", None)
    if distance is None and isinstance(r, dict):
        distance = r.get("distance") or r.get("fisher_rao_distance")
    if distance is None:
        raise ValueError("ChainResult has no distance field")
    threshold = getattr(r, "threshold", 1.0)
    if isinstance(r, dict):
        threshold = r.get("threshold", threshold)
    sigma = getattr(r, "sigma", None)
    if sigma is None and hasattr(r, "meta"):
        sigma = getattr(r.meta, "get", lambda k, d=None: d)("sigma", None)
    if sigma is None and isinstance(r, dict):
        sigma = (r.get("meta") or {}).get("sigma")
    sigma = float(sigma) if sigma is not None else 1.0
    sigma = max(sigma, 1e-6)
    chain_id = getattr(r, "chain_id", "")
    if isinstance(r, dict):
        chain_id = r.get("chain_id", chain_id)
    cid = getattr(r, "constituent_id", None) or getattr(r, "inputs_sha", str(chain_id))
    return ConstituentScore(
        constituent_id=str(cid),
        distance=float(distance),
        sigma=sigma,
        permitted_radius=float(threshold),
        precision=1.0 / (sigma * sigma),
        is_trusted=float(distance) <= float(threshold),
        chain_id=str(chain_id),
    )


def precision_weight(sigma: float) -> float:
    """Glicko/atlas precision weight: Π = 1/sigma²."""
    s = max(float(sigma), 1e-6)
    return 1.0 / (s * s)


def systemic_correlation_index(scores: List[ConstituentScore],
                               scale: float = 0.5) -> float:
    """Basel-style systemic-correlation sub-index.

    Measures how CONCENTRATED the portfolio's trust levels are — i.e.
    how much of it "sits on one manifold." We build a similarity kernel
    over constituent distances (an RBF adequacy kernel):

        K_ij = exp( -|d_i - d_j| / scale )

    so constituents at the SAME distance co-locate (K=1) and those far
    apart de-correlate (K→0). The systemic score is the normalized size
    of the leading eigenvalue of K (a spectral concentration measure):

        systemic = λ_1 / sum(λ)

    Interpretation (Vasicek single-risk-factor dialect):
      systemic → 1.0 : one factor / one manifold explains (nearly) all
                        cross-constituent similarity = MONOCULTURE
                        = systemic trust risk is HIGH.
      systemic → ~1/n : no dominant factor = MULTICULTURE = safer.

    With < 2 constituents we return 0.0 (no systemic signal).
    """
    n = len(scores)
    if n < 2:
        return 0.0
    ds = np.array([s.distance for s in scores], dtype=np.float64)
    # RBF co-location kernel: same distance → 1, far apart → 0
    ddiff = np.abs(ds[:, None] - ds[None, :])
    K = np.exp(-ddiff / scale)
    try:
        eigvals = np.linalg.eigvalsh(K)
        eigvals = eigvals[eigvals > 1e-9]
        total = float(eigvals.sum())
        if total <= 1e-9:
            return 0.0
        return float(eigvals[-1] / total)  # normalized leading eigenvalue
    except np.linalg.LinAlgError:
        return 0.0


def aggregate_sov_signal(scores: List[ConstituentScore],
                         article_zero: bool = False) -> SovSignalVerdict:
    """Aggregate a portfolio into the SOV SIGNAL index verdict.

    Aggregate score = geometric-mean of inverse-distance, precision-
    weighted (Fisher-ideal-style composition). High = trusted.

    Steps:
      1. Precision ω_i = 1/σ_i²  (Glicko law)
      2. per-i mutual trust t_i = 1 / (1 + d_i)
      3. headline = exp( Σ ω_i · ln(t_i) / Σ ω_i )  (weighted geometric mean)
      4. systemic = systemic_correlation_index(scores)
      5. multiculture_ccy = systemic < 0.5
    """
    if not scores:
        return SovSignalVerdict(
            n_constituents=0, mean_distance=0.0, aggregate_score=0.0,
            systemic_correlation=0.0, multiculture_ccy=False,
            high_sigma_share=0.0, constituents=[], article_zero=article_zero,
            chain_id="",
        )
    omegas = np.array([s.precision for s in scores], dtype=np.float64)
    omegas = np.clip(omegas, 1e-9, None)
    ds = np.array([s.distance for s in scores], dtype=np.float64)
    ts = 1.0 / (1.0 + ds)                      # trust proxy in (0,1]
    ln_t = np.log(ts)
    agg = float(np.exp(np.sum(omegas * ln_t) / np.sum(omegas)))
    mean_d = float(ds.mean())
    sys_corr = systemic_correlation_index(scores)
    # high-sigma share by precision weight (Glicko law)
    gt1 = scores_precision_gt1(scores)
    high_sigma_share = float(np.sum(omegas[gt1]) / np.sum(omegas)) if len(scores) else 0.0

    chain_body = json.dumps({
        "n": len(scores), "agg": agg, "mean_d": mean_d,
        "sys_corr": sys_corr, "article_zero": article_zero,
    }, sort_keys=True).encode()
    chain_id = hashlib.sha256(chain_body).hexdigest()[:24]

    return SovSignalVerdict(
        n_constituents=len(scores),
        mean_distance=mean_d,
        aggregate_score=agg,
        systemic_correlation=sys_corr,
        multiculture_ccy=sys_corr < 0.5,
        high_sigma_share=high_sigma_share,
        constituents=[s.__dict__ for s in scores],
        article_zero=article_zero,
        chain_id=chain_id,
    )


def scores_precision_gt1(scores: List[ConstituentScore]) -> List[bool]:
    """Helper: boolean mask of constituents with sigma > 1 (uncertain)."""
    return [s.sigma > 1.0 for s in scores]


# ---------------------------------------------------------------------------
# Empirical permitted-manifold calibrator (RAS spec §2)
#
# The permitted manifold is NOT np.eye(4) — it is calibrated from a
# reference set of known-good behaviour profiles (≥30 profiles). The
# manifold = a regularized covariance (SPD) of those profiles, which
# matches the Fisher-Rao math in sovos-fisher-rao. SOV SIGNAL distance =
# how far a target sits from this empirical permitted region — the
# Merton/KMV "distance-to-default" isomorphism, done for real.
# ---------------------------------------------------------------------------
def calibrate_permitted_manifold(profiles: List[List[float]],
                                 shrink: float = 0.1,
                                 floor: float = 1e-6) -> Dict[str, Any]:
    """Build a permitted manifold from a reference set of profiles.

    Returns a dict with the reference MEAN and SPD COVARIANCE:
        {"mean": [...], "cov": [[...]], "n": N, "dims": d}
    This is the empirical permitted region. The mean is the centroid of
    known-good behaviour; the covariance is the SPD shape of the cluster.
    distance_to_permitted_manifold() then measures how far a target sits
    (Mahalanobis) from this region — the Merton/KMV distance-to-default.

    Args:
        profiles: list of known-good behaviour profile vectors.
        shrink: Ledoit-Wolf-style shrinkage toward identity.
        floor: positive floor on the covariance diagonal (guarantees SPD).

    Raises:
        ValueError if fewer than 2 profiles or mismatched dims.
    """
    import numpy as np
    if len(profiles) < 2:
        raise ValueError("calibrate_permitted_manifold needs >= 2 reference profiles")
    dims = {len(p) for p in profiles}
    if len(dims) != 1:
        raise ValueError(f"mismatched profile dims: {dims}")
    d = dims.pop()
    X = np.asarray(profiles, dtype=float)          # (N, d)
    mean = X.mean(axis=0)
    centered = X - mean
    cov = centered.T @ centered / max(1, len(profiles) - 1)
    ident = np.eye(d)
    M = (1 - shrink) * cov + shrink * ident
    M = 0.5 * (M + M.T)
    M = M + floor * ident
    evals = np.linalg.eigvalsh(M)
    if evals.min() <= 0:
        M = M + (abs(evals.min()) + floor) * ident
    return {"mean": mean.tolist(), "cov": M.tolist(),
            "n": len(profiles), "dims": d}


def distance_to_permitted_manifold(candidate: List[float],
                                   manifold: Dict[str, Any]) -> float:
    """Mahalanobis distance-to-center of a candidate from the permitted manifold.

    This is the Merton/KMV "distance-to-default" isomorphism made real:
    how many standard deviations the candidate's measured behaviour profile
    sits from the CENTER of the permitted (known-good) region.

        d = sqrt((c - μ)^T Σ⁻¹ (c - μ))

    A candidate inside the reference cluster → small d; a far candidate
    → large d. This is the honest statistical analogue of "distance to a
    permitted region" for a single measured point vs a reference
    distribution — the textbook default-distance measure.

    Args:
        candidate: the measured behaviour profile vector.
        manifold: the dict from calibrate_permitted_manifold (mean + cov).

    Returns:
        d >= 0. d==0 means the candidate is exactly at the reference mean.
    """
    import numpy as np
    v = np.asarray(candidate, dtype=float)
    mu = np.asarray(manifold["mean"], dtype=float)
    cov = np.asarray(manifold["cov"], dtype=float)
    if v.shape != mu.shape:
        raise ValueError(f"candidate dim {len(v)} != manifold mean dim {len(mu)}")
    delta = v - mu
    try:
        sol = np.linalg.solve(cov, delta)
        d2 = float(delta @ sol)
    except np.linalg.LinAlgError:
        evals, evecs = np.linalg.eigh(cov)
        evals = np.clip(evals, 1e-12, None)
        whitened = (evecs.T @ delta) / np.sqrt(evals)
        d2 = float(whitened @ whitened)
    return math.sqrt(max(0.0, d2))


def self_test() -> Dict[str, Any]:
    """Smoke test: a 'safe' portfolio vs a 'monoculture high-σ' portfolio."""
    # Safe/spread portfolio: varied distances, low sigma → multiculture
    safe = [
        ConstituentScore("a", 0.05, 0.4, 0.5, 6.25, True),
        ConstituentScore("b", 0.30, 0.5, 0.5, 4.0, True),
        ConstituentScore("c", 0.90, 0.6, 0.5, 2.78, True),
        ConstituentScore("d", 2.50, 0.55, 0.5, 3.31, False),
    ]
    verdict_safe = aggregate_sov_signal(safe)
    # Monoculture: all distances identical (maximally correlated) + high σ
    mono = [
        ConstituentScore("m1", 0.3, 2.0, 0.5, 0.25, True) for _ in range(4)
    ]
    verdict_mono = aggregate_sov_signal(mono)
    return {
        "safe_agg": round(verdict_safe.aggregate_score, 3),
        "safe_syscorr": round(verdict_safe.systemic_correlation, 3),
        "safe_multiculture": verdict_safe.multiculture_ccy,
        "mono_agg": round(verdict_mono.aggregate_score, 3),
        "mono_syscorr": round(verdict_mono.systemic_correlation, 3),
        "mono_multiculture": verdict_mono.multiculture_ccy,
        "chain_id_len": len(verdict_safe.chain_id),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
