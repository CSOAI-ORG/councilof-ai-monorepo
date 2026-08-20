"""evolve — the 90/10 router as a frozen split-conformal predicate.

Crown-jewel mechanism of the COAI self-improving (MAPE-K) loop. Deterministic,
distribution-free, NO LLM-as-judge: once a threshold is frozen from a
calibration set, every routing and promotion decision is pure arithmetic and
exactly reproducible.

Public API
----------
Calibration (Analyze stage):
    calibrate(calib_scores, alpha) -> q_hat        # frozen split-conformal threshold
    coverage_bounds(n, alpha) -> (lower, upper)    # finite-sample sandwich
    calibrate_risk(calib_losses, alpha, b=...) -> certified_risk   # Conformal Risk Control
    select_risk_threshold(...) -> RiskThreshold    # CRC threshold search

Routing (Analyze stage):
    route(score, q_hat) -> "auto" | "escalate"
    Router(q_hat, alpha=..., n_calib=...)          # frozen, auditable

Nonconformity scores (pluggable, pure functions):
    EnsembleDisagreement   / ensemble_disagreement       (recommended)
    OneMinusMaxSoftmax     / one_minus_max_softmax
    DistanceToCalibration  / distance_to_calibration
    NonconformityScore     (Protocol)

Promotion (Execute stage):
    promote_if_better(candidate, baseline, min_effect=..., significance=...) -> bool
    promote_report(...) -> PromoteReport           # full verdict incl. sign guard
"""

from __future__ import annotations

from .conformal import calibrate, calibrate_risk, coverage_bounds
from .promote import PromoteReport, promote_if_better, promote_report
from .risk import RiskThreshold, select_risk_threshold
from .router import Decision, Router, route
from .scores import (
    DistanceToCalibration,
    EnsembleDisagreement,
    NonconformityScore,
    OneMinusMaxSoftmax,
    distance_to_calibration,
    ensemble_disagreement,
    one_minus_max_softmax,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # conformal
    "calibrate",
    "coverage_bounds",
    "calibrate_risk",
    "select_risk_threshold",
    "RiskThreshold",
    # router
    "route",
    "Router",
    "Decision",
    # scores
    "NonconformityScore",
    "EnsembleDisagreement",
    "OneMinusMaxSoftmax",
    "DistanceToCalibration",
    "ensemble_disagreement",
    "one_minus_max_softmax",
    "distance_to_calibration",
    # promote
    "promote_if_better",
    "promote_report",
    "PromoteReport",
]
