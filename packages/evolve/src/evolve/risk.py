"""Conformal Risk Control threshold search.

The vehicle for calibrating an *escalation/abstention* threshold to a target
error rate rather than to a coverage level. Given, for each calibration item, a
loss evaluated across a grid of candidate thresholds -- where the per-item loss
is **monotone non-decreasing** as the threshold loosens (admits more items to
``auto``) -- pick the loosest threshold whose CRC-certified risk stays ``<=
alpha``.

This is the ``lambda``-search of Conformal Risk Control (Angelopoulos, Bates,
Fisch, Lei, Schuster, arXiv:2208.02814): the certified bound at each candidate
is ``(n/(n+1)) * mean_loss + b/(n+1)`` (:func:`evolve.conformal.calibrate_risk`),
and monotonicity means the certified risk is itself monotone along the grid, so
the admissible region is a prefix and we return its boundary.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from .conformal import calibrate_risk

__all__ = ["select_risk_threshold", "RiskThreshold"]


class RiskThreshold:
    """Result of :func:`select_risk_threshold`."""

    __slots__ = ("threshold", "certified_risk", "alpha", "index", "feasible")

    def __init__(self, threshold, certified_risk, alpha, index, feasible):
        self.threshold = threshold
        self.certified_risk = certified_risk
        self.alpha = alpha
        self.index = index
        self.feasible = feasible

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (f"RiskThreshold(threshold={self.threshold!r}, "
                f"certified_risk={self.certified_risk!r}, feasible={self.feasible})")


def select_risk_threshold(
    losses_at_thresholds: Sequence[Sequence[float]],
    thresholds: Sequence[float],
    alpha: float,
    *,
    b: float | None = None,
    loosening: str = "increasing",
) -> RiskThreshold:
    """Pick the loosest threshold whose CRC-certified risk ``<= alpha``.

    Parameters
    ----------
    losses_at_thresholds:
        ``(n_calib, n_thresholds)`` matrix. Entry ``[i, j]`` is item ``i``'s loss
        when the threshold is ``thresholds[j]``. Along ``j`` (in the direction the
        threshold *loosens*) each row must be monotone non-decreasing.
    thresholds:
        The candidate threshold grid, ordered so that ``loosening`` describes how
        loosening moves along it. ``"increasing"`` (default): larger threshold =
        looser (admits more to ``auto``), so risk rises with index and we return
        the largest feasible threshold. ``"decreasing"``: reverse.
    alpha:
        Target risk. The certified bound must not exceed it.
    b:
        Loss upper bound; forwarded to :func:`calibrate_risk`.

    Returns
    -------
    RiskThreshold
        ``feasible=False`` when even the tightest threshold cannot certify
        ``alpha`` (then ``threshold`` is that tightest candidate).
    """
    L = np.asarray([list(r) for r in losses_at_thresholds], dtype=float)
    thr = list(thresholds)
    if L.ndim != 2:
        raise ValueError("losses_at_thresholds must be 2-D (n_calib, n_thresholds)")
    if L.shape[1] != len(thr):
        raise ValueError("thresholds length must match number of loss columns")
    if loosening not in ("increasing", "decreasing"):
        raise ValueError("loosening must be 'increasing' or 'decreasing'")

    # Evaluate the tightest-first order.
    order = range(len(thr)) if loosening == "increasing" else range(len(thr) - 1, -1, -1)

    best = None
    tightest_certified = None
    tightest_threshold = None
    for j in order:
        certified = calibrate_risk(L[:, j].tolist(), alpha, b=b)
        if tightest_certified is None:
            tightest_certified = certified
            tightest_threshold = thr[j]
        if certified <= alpha:
            best = (thr[j], certified, j)  # keep the loosest feasible one
        else:
            # Monotone risk: once it exceeds alpha it never comes back.
            break

    if best is None:
        return RiskThreshold(tightest_threshold, tightest_certified, alpha,
                             index=None, feasible=False)
    thr_val, cert, idx = best
    return RiskThreshold(thr_val, cert, alpha, index=idx, feasible=True)
