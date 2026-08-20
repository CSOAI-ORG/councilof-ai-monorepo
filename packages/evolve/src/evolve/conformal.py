"""Split (inductive) conformal prediction and conformal risk control.

Distribution-free, finite-sample calibration primitives. NO model judges a
model here: once a threshold is frozen from a calibration set, every decision
is a pure deterministic comparison and is exactly reproducible.

References
----------
- Vovk, Gammerman, Shafer (2005), *Algorithmic Learning in a Random World* —
  the split/inductive conformal construction and its exact finite-sample
  coverage.
- Angelopoulos & Bates (2021), *A Gentle Introduction to Conformal Prediction
  and Distribution-Free Uncertainty Quantification*, arXiv:2107.07511 — the
  ``ceil((n+1)(1-alpha))/n`` quantile recipe and the coverage sandwich.
- Angelopoulos, Bates, Fisch, Lei, Schuster (2022), *Conformal Risk Control*,
  arXiv:2208.02814 — bounding ``E[L] <= alpha`` for any monotone loss.

The finite-sample coverage sandwich
-----------------------------------
For calibration scores that are exchangeable with the test point and have no
ties (continuous distribution), the split-conformal threshold ``q_hat``
returned by :func:`calibrate` guarantees::

    1 - alpha  <=  P(score_test <= q_hat)  <=  1 - alpha + 1/(n + 1)

where ``n`` is the number of calibration scores. The lower bound is the
marginal validity guarantee; the upper bound shows the coverage is not much
more conservative than requested. Ties can only *increase* coverage, so the
lower bound still holds; the upper bound is the no-tie (continuous) case.
"""

from __future__ import annotations

import math
from typing import Sequence

__all__ = [
    "calibrate",
    "coverage_bounds",
    "calibrate_risk",
]


def _as_sorted_floats(scores: Sequence[float], *, name: str) -> list[float]:
    if scores is None:
        raise ValueError(f"{name} must not be None")
    vals = [float(s) for s in scores]
    if len(vals) == 0:
        raise ValueError(f"{name} must be non-empty")
    for v in vals:
        if math.isnan(v):
            raise ValueError(f"{name} contains NaN")
    vals.sort()
    return vals


def calibrate(calib_scores: Sequence[float], alpha: float) -> float:
    """Freeze the split-conformal threshold ``q_hat`` from calibration scores.

    Returns the ``k``-th smallest calibration nonconformity score, where::

        k = ceil((n + 1) * (1 - alpha))

    (1-indexed). This is the standard inductive-conformal quantile. When
    ``k > n`` the required quantile lies beyond the empirical support and the
    only distribution-free valid threshold is ``+inf`` (accept everything —
    the guarantee then holds trivially because coverage is 1). When ``k <= 0``
    (only possible at ``alpha >= 1``) the threshold is ``-inf``.

    Parameters
    ----------
    calib_scores:
        Nonconformity scores on a held-out calibration set. Higher = stranger.
        Must be exchangeable with the scores seen at deployment.
    alpha:
        Target miscoverage in ``(0, 1)``. Coverage target is ``1 - alpha``.

    Returns
    -------
    float
        The frozen threshold ``q_hat``. Deterministic in ``(calib_scores,
        alpha)``: the same multiset and alpha always yield the same value.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in the open interval (0, 1), got {alpha}")
    vals = _as_sorted_floats(calib_scores, name="calib_scores")
    n = len(vals)

    k = math.ceil((n + 1) * (1.0 - alpha))
    # Clip / handle the two out-of-support edges explicitly.
    if k > n:
        # Quantile beyond the empirical support: no finite score is provably
        # valid, so accept everything. Coverage == 1 >= 1 - alpha, trivially.
        return math.inf
    if k <= 0:
        return -math.inf
    # k is 1-indexed into the ascending sorted scores.
    return vals[k - 1]


def coverage_bounds(n: int, alpha: float) -> tuple[float, float]:
    """Return the ``(lower, upper)`` finite-sample coverage sandwich.

    ``lower = 1 - alpha`` and ``upper = min(1, 1 - alpha + 1/(n+1))``. The
    upper bound is the continuous (no-tie) guarantee. Useful for tests and for
    documenting the guarantee an operator is actually buying at a given ``n``.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1)")
    lower = 1.0 - alpha
    upper = min(1.0, 1.0 - alpha + 1.0 / (n + 1))
    return lower, upper


def calibrate_risk(
    calib_losses: Sequence[float],
    alpha: float,
    *,
    b: float | None = None,
) -> float:
    """Conformal Risk Control: bound the expected monotone loss ``E[L] <= alpha``.

    This is the Conformal Risk Control (CRC) generalisation of split conformal
    (Angelopoulos, Bates, Fisch, Lei, Schuster, arXiv:2208.02814). Where
    :func:`calibrate` controls *coverage* (a 0/1 miscoverage loss), CRC controls
    the *expectation* of any loss that is monotone non-increasing in a threshold
    parameter and bounded above by ``b``.

    Here we expose the workhorse special case used by the router: the losses in
    ``calib_losses`` are the realised loss values on the calibration set (each in
    ``[0, b]``), and we return the largest empirical-mean loss level that the CRC
    finite-sample bound certifies to be ``<= alpha`` in expectation on a fresh
    point. Concretely CRC guarantees, for ``n`` calibration points each bounded
    by ``b``::

        E[L_test]  <=  (n / (n + 1)) * mean(calib_losses)  +  b / (n + 1)

    We return that right-hand side as the *certified risk level*. The caller
    picks the operating threshold so that this certified level does not exceed
    the target ``alpha``; see :func:`select_risk_threshold` in ``risk.py`` for
    the threshold-search form.

    Parameters
    ----------
    calib_losses:
        Realised loss values on the calibration set, each in ``[0, b]``.
    alpha:
        Target risk level. Must be in ``(0, b]``. Returned value is compared
        against this by the caller; passing it lets us validate the bound is
        even attainable (``alpha >= b/(n+1)`` is required for any non-trivial
        control).
    b:
        Upper bound on the loss. Defaults to ``max(calib_losses)`` clipped to at
        least 1.0 when not supplied, but supplying the true bound is strongly
        preferred — the ``b/(n+1)`` slack term depends on it.

    Returns
    -------
    float
        The CRC-certified upper bound on ``E[L_test]``. If this is ``<= alpha``
        the calibration set certifies the target risk; otherwise it does not and
        the caller must tighten the operating point or gather more data.
    """
    vals = _as_sorted_floats(calib_losses, name="calib_losses")
    n = len(vals)
    if b is None:
        b = max(max(vals), 1.0)
    if b <= 0:
        raise ValueError("b (loss upper bound) must be positive")
    for v in vals:
        if v < 0 or v > b + 1e-12:
            raise ValueError(f"each loss must be in [0, b]={b}; got {v}")
    if not (0.0 < alpha <= b):
        raise ValueError(f"alpha must be in (0, b]=(0, {b}], got {alpha}")

    mean_loss = sum(vals) / n
    certified = (n / (n + 1)) * mean_loss + b / (n + 1)
    return certified
