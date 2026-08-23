"""Tests for the Conformal Risk Control threshold search."""

from __future__ import annotations

import numpy as np

from evolve import select_risk_threshold


def _make_monotone_losses(thresholds, rng, n=400):
    """Per-item loss that is monotone non-decreasing as the threshold loosens.

    Model: item i has a latent difficulty d_i ~ U(0,1). At threshold t it is
    admitted to 'auto' if t >= d_i, and admitting a hard item costs a 0/1 loss
    with prob proportional to d_i. Loss is 0 while not admitted, then can turn
    on once admitted -> monotone non-decreasing in t.
    """
    d = rng.uniform(0, 1, n)
    err = (rng.uniform(0, 1, n) < d).astype(float)  # would-be error if admitted
    L = np.zeros((n, len(thresholds)))
    for j, t in enumerate(thresholds):
        admitted = (t >= d).astype(float)
        L[:, j] = admitted * err
    # enforce exact monotonicity along columns (cumulative max)
    L = np.maximum.accumulate(L, axis=1)
    return L


def test_selects_loosest_feasible_threshold_and_controls_risk():
    rng = np.random.default_rng(0)
    thresholds = list(np.linspace(0.0, 1.0, 21))
    alpha = 0.1

    L = _make_monotone_losses(thresholds, rng)
    res = select_risk_threshold(L.tolist(), thresholds, alpha)
    assert res.feasible is True
    assert res.certified_risk <= alpha + 1e-9

    # Loosening one grid step past the pick must break the guarantee.
    if res.index is not None and res.index + 1 < len(thresholds):
        from evolve.conformal import calibrate_risk
        next_cert = calibrate_risk(L[:, res.index + 1].tolist(), alpha, b=1.0)
        assert next_cert > alpha


def test_infeasible_when_alpha_too_tight():
    rng = np.random.default_rng(1)
    thresholds = list(np.linspace(0.2, 1.0, 10))  # even tightest admits some loss
    L = _make_monotone_losses(thresholds, rng)
    # force loss at the tightest column to be non-trivial
    L[:, 0] = 0.5
    res = select_risk_threshold(L.tolist(), thresholds, alpha=0.001)
    assert res.feasible is False
    assert res.threshold == thresholds[0]  # reports the tightest candidate


def test_out_of_sample_expected_risk_is_controlled():
    """CRC guarantee: E[L(threshold_hat)] <= alpha, marginally over the
    calibration draw that picks the threshold and the fresh test point.

    We estimate that expectation by averaging the fresh-data realised loss (at
    the calibration-chosen threshold) across many independent trials; the MEAN
    must not exceed alpha (within Monte-Carlo error). This is the theorem —
    NOT a per-trial high-probability bound."""
    rng = np.random.default_rng(2)
    thresholds = list(np.linspace(0.0, 1.0, 41))
    alpha = 0.08

    realised = []
    trials = 400
    for _ in range(trials):
        Lc = _make_monotone_losses(thresholds, rng, n=500)
        res = select_risk_threshold(Lc.tolist(), thresholds, alpha)
        if not res.feasible:
            realised.append(0.0)  # nothing admitted -> zero loss
            continue
        # fresh evaluation at the SAME calibration-chosen threshold index
        Lf = _make_monotone_losses(thresholds, rng, n=2000)
        realised.append(float(Lf[:, res.index].mean()))

    mean_realised = float(np.mean(realised))
    se = float(np.std(realised, ddof=1)) / (trials ** 0.5)
    # Expected loss controlled at alpha (allow a few sigma of MC slack).
    assert mean_realised <= alpha + 5 * se, (
        f"E[L]={mean_realised:.4f} exceeds alpha={alpha} (se={se:.4f})")
