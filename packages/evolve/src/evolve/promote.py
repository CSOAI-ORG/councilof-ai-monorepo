"""The promote-gate: promote a candidate only if it *significantly* beats a
frozen baseline on a held-out set — with the correct sign.

This exists because the estate already shipped a promote-gate that printed
"beats" for a delta of **-9.16**: it only checked that the confidence interval
*excluded zero*, which a solidly-*worse* candidate also satisfies (its CI sits
entirely below zero). The fix is two guards, both required:

1. The effect estimate must have the **correct sign** (candidate genuinely
   better in the intended direction), and
2. The one-sided confidence bound on the effect must **exclude the minimum
   detectable effect** ``min_effect`` (not merely exclude zero).

"Better" is measured as a distribution over a held-out set, never a single
number vs a single number. Two regimes:

- ``candidate_metric`` is a **sequence** (per-item held-out metrics for the
  candidate): a two-sample comparison of mean(candidate) vs mean(baseline).
- ``candidate_metric`` is a **scalar**: a one-sample comparison of the frozen
  candidate constant against the baseline's held-out sampling distribution.

The test is a **bootstrap percentile CI** by default (distribution-free, robust
at small n); a Welch/one-sample **t-test** is available via ``method="ttest"``
with the standard small-``n`` caveat (it assumes approximate normality of the
mean, which is shaky below ~15 samples). The bootstrap is seeded, so a promote
decision is **reproducible**.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

__all__ = ["promote_if_better", "promote_report", "PromoteReport"]


@dataclass(frozen=True)
class PromoteReport:
    """Full verdict of a promote-gate evaluation."""

    promote: bool
    effect: float           # point estimate of (candidate - baseline), oriented
    lower_bound: float      # one-sided confidence bound on the effect
    min_effect: float
    significance: float
    sign_ok: bool
    excludes_min_effect: bool
    method: str
    n_candidate: int
    n_baseline: int
    reason: str


def _percentile_lower_bound(samples: np.ndarray, significance: float) -> float:
    # One-sided lower confidence bound: the ``significance`` quantile.
    return float(np.quantile(samples, significance))


def _bootstrap_effect_dist(
    candidate: np.ndarray | float,
    baseline: np.ndarray,
    *,
    higher_is_better: bool,
    n_boot: int,
    rng: np.random.Generator,
) -> tuple[float, np.ndarray]:
    """Return (point_effect, bootstrap_effect_samples), oriented so >0 = better."""
    orient = 1.0 if higher_is_better else -1.0
    base_boot = rng.choice(baseline, size=(n_boot, baseline.size), replace=True).mean(axis=1)

    if isinstance(candidate, np.ndarray):
        cand_boot = rng.choice(candidate, size=(n_boot, candidate.size), replace=True).mean(axis=1)
        point = orient * (float(candidate.mean()) - float(baseline.mean()))
        effect_boot = orient * (cand_boot - base_boot)
    else:
        # Scalar candidate: only the baseline has sampling variability.
        point = orient * (float(candidate) - float(baseline.mean()))
        effect_boot = orient * (float(candidate) - base_boot)
    return point, effect_boot


def _ttest_lower_bound(
    candidate: np.ndarray | float,
    baseline: np.ndarray,
    *,
    higher_is_better: bool,
    significance: float,
) -> tuple[float, float]:
    """One-sided lower bound via a t-interval (numpy-only, no scipy).

    Uses a normal approximation to the Student-t critical value, which is the
    small-``n`` caveat: below ~15 samples the true t-quantile is fatter-tailed
    and this bound is mildly anti-conservative. Good enough as an alternative to
    the (preferred) bootstrap; flagged in the returned method string.
    """
    orient = 1.0 if higher_is_better else -1.0
    base_mean = float(baseline.mean())
    nb = baseline.size
    # z critical for a one-sided (1 - significance) bound.
    z = _inv_normal_cdf(1.0 - significance)
    if isinstance(candidate, np.ndarray):
        cand_mean = float(candidate.mean())
        nc = candidate.size
        var_c = float(np.var(candidate, ddof=1)) if nc > 1 else 0.0
        var_b = float(np.var(baseline, ddof=1)) if nb > 1 else 0.0
        se = math.sqrt(var_c / max(nc, 1) + var_b / max(nb, 1))
        point = orient * (cand_mean - base_mean)
    else:
        var_b = float(np.var(baseline, ddof=1)) if nb > 1 else 0.0
        se = math.sqrt(var_b / max(nb, 1))
        point = orient * (float(candidate) - base_mean)
    lower = point - z * se
    return point, lower


def _inv_normal_cdf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation)."""
    if not (0.0 < p < 1.0):
        raise ValueError("p must be in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def promote_report(
    candidate_metric,
    baseline_metrics: Sequence[float],
    *,
    min_effect: float,
    significance: float = 0.05,
    higher_is_better: bool = True,
    method: str = "bootstrap",
    n_boot: int = 10_000,
    seed: int = 0,
) -> PromoteReport:
    """Evaluate the promote-gate and return a full :class:`PromoteReport`.

    Promotes iff BOTH:
      * the oriented effect point estimate is positive (correct sign), AND
      * the one-sided ``(1 - significance)`` lower confidence bound on the
        oriented effect strictly exceeds ``min_effect``.

    ``min_effect`` is the minimum *detectable* effect and must be ``>= 0``; the
    gate demands the improvement clear it, not merely clear zero.
    """
    if min_effect < 0:
        raise ValueError("min_effect must be >= 0 (it is a magnitude of improvement)")
    if not (0.0 < significance < 0.5):
        raise ValueError("significance must be in (0, 0.5)")
    if method not in ("bootstrap", "ttest"):
        raise ValueError("method must be 'bootstrap' or 'ttest'")

    baseline = np.asarray(list(baseline_metrics), dtype=float)
    if baseline.size < 2:
        raise ValueError("baseline_metrics must have at least 2 held-out points")

    if isinstance(candidate_metric, (list, tuple, np.ndarray)):
        candidate: np.ndarray | float = np.asarray(list(candidate_metric), dtype=float)
        if candidate.size < 1:
            raise ValueError("candidate_metric sequence must be non-empty")
        n_candidate = int(candidate.size)
    else:
        candidate = float(candidate_metric)
        n_candidate = 1

    if method == "bootstrap":
        rng = np.random.default_rng(seed)
        point, effect_boot = _bootstrap_effect_dist(
            candidate, baseline, higher_is_better=higher_is_better,
            n_boot=n_boot, rng=rng)
        lower = _percentile_lower_bound(effect_boot, significance)
        method_used = "bootstrap"
    else:
        point, lower = _ttest_lower_bound(
            candidate, baseline, higher_is_better=higher_is_better,
            significance=significance)
        method_used = "ttest(normal-approx; small-n caveat)"

    sign_ok = point > 0.0
    excludes_min_effect = lower > min_effect
    promote = bool(sign_ok and excludes_min_effect)

    if promote:
        reason = (f"PROMOTE: effect={point:.4g} > 0 and one-sided lower bound "
                  f"{lower:.4g} > min_effect {min_effect:.4g}")
    elif not sign_ok:
        reason = (f"REJECT: wrong sign — oriented effect {point:.4g} <= 0 "
                  f"(candidate not better in the intended direction)")
    else:
        reason = (f"REJECT: within noise — lower bound {lower:.4g} does not "
                  f"exceed min_effect {min_effect:.4g}")

    return PromoteReport(
        promote=promote, effect=point, lower_bound=lower, min_effect=min_effect,
        significance=significance, sign_ok=sign_ok,
        excludes_min_effect=excludes_min_effect, method=method_used,
        n_candidate=n_candidate, n_baseline=int(baseline.size), reason=reason)


def promote_if_better(
    candidate_metric,
    baseline_metrics: Sequence[float],
    *,
    min_effect: float,
    significance: float = 0.05,
    higher_is_better: bool = True,
    method: str = "bootstrap",
    n_boot: int = 10_000,
    seed: int = 0,
) -> bool:
    """Boolean promote-gate. See :func:`promote_report` for the full verdict.

    Returns ``True`` only when the candidate beats the frozen baseline with
    statistical significance AND the correct sign AND by at least ``min_effect``.
    """
    return promote_report(
        candidate_metric, baseline_metrics, min_effect=min_effect,
        significance=significance, higher_is_better=higher_is_better,
        method=method, n_boot=n_boot, seed=seed).promote
