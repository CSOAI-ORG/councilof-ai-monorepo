"""Tests for split-conformal calibration, incl. the empirical coverage guarantee."""

from __future__ import annotations

import math

import numpy as np
import pytest

from evolve import calibrate, coverage_bounds
from evolve.conformal import calibrate_risk


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_threshold_determinism_same_input_same_qhat():
    scores = [0.3, 0.1, 0.9, 0.4, 0.2, 0.7, 0.5, 0.6, 0.8, 0.05]
    a = calibrate(scores, 0.1)
    b = calibrate(list(scores), 0.1)
    # order must not matter (internal sort) and repeated calls are identical
    c = calibrate(list(reversed(scores)), 0.1)
    assert a == b == c


def test_qhat_is_a_calibration_order_statistic():
    # q_hat must be exactly the ceil((n+1)(1-alpha))-th smallest score.
    scores = [float(i) for i in range(1, 11)]  # 1..10, n=10
    alpha = 0.2
    k = math.ceil((10 + 1) * (1 - alpha))  # ceil(11*0.8)=ceil(8.8)=9
    assert calibrate(scores, alpha) == sorted(scores)[k - 1] == 9.0


# --------------------------------------------------------------------------- #
# Edge cases: +inf, tiny n, ties
# --------------------------------------------------------------------------- #
def test_plus_inf_edge_when_index_exceeds_n():
    # n=1, alpha=0.1 -> k = ceil(2*0.9)=ceil(1.8)=2 > n=1 -> +inf
    assert calibrate([0.5], 0.1) == math.inf
    # n=8, alpha=0.05 -> k=ceil(9*0.95)=ceil(8.55)=9 > 8 -> +inf
    assert calibrate(list(range(8)), 0.05) == math.inf


def test_finite_qhat_when_index_within_support():
    # n=19, alpha=0.05 -> k=ceil(20*0.95)=19 <= 19 -> finite (the max)
    scores = list(range(19))
    assert calibrate(scores, 0.05) == 18.0


def test_tie_handling_returns_the_tied_value():
    # Heavy ties must not break the order-statistic pick.
    scores = [1.0] * 5 + [2.0] * 5  # n=10
    alpha = 0.2
    k = math.ceil(11 * 0.8)  # 9 -> 9th smallest = 2.0 (positions 6..10 are 2.0)
    assert calibrate(scores, alpha) == 2.0
    # ties can only raise coverage; lower bound still holds
    lo, _ = coverage_bounds(10, alpha)
    assert lo == pytest.approx(0.8)


def test_alpha_out_of_range_raises():
    with pytest.raises(ValueError):
        calibrate([1, 2, 3], 0.0)
    with pytest.raises(ValueError):
        calibrate([1, 2, 3], 1.0)


def test_empty_calib_raises():
    with pytest.raises(ValueError):
        calibrate([], 0.1)


def test_nan_rejected():
    with pytest.raises(ValueError):
        calibrate([1.0, float("nan"), 2.0], 0.1)


# --------------------------------------------------------------------------- #
# Coverage bounds helper
# --------------------------------------------------------------------------- #
def test_coverage_bounds_sandwich():
    lo, hi = coverage_bounds(99, 0.1)
    assert lo == pytest.approx(0.9)
    assert hi == pytest.approx(0.9 + 1 / 100)
    # upper bound clips at 1.0
    _, hi2 = coverage_bounds(1, 0.1)
    assert hi2 == 1.0


# --------------------------------------------------------------------------- #
# THE POINT: empirical coverage guarantee holds, distribution-free
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("alpha", [0.05, 0.1, 0.2])
@pytest.mark.parametrize("n", [50, 200, 500])
@pytest.mark.parametrize("dist", ["normal", "exponential", "uniform"])
def test_empirical_coverage_holds(alpha, n, dist):
    """Split calib/test many times; mean test coverage must sit inside the
    finite-sample sandwich [1-alpha, 1-alpha+1/(n+1)] within sampling error.

    This is the distribution-free guarantee actually holding — across three
    unrelated continuous distributions, several alpha, several n.
    """
    rng = np.random.default_rng(20260820 + n + int(alpha * 1000) + hash(dist) % 1000)
    trials = 3000
    m_test = 40

    def draw(size):
        if dist == "normal":
            return rng.standard_normal(size)
        if dist == "exponential":
            return rng.exponential(1.0, size)
        return rng.uniform(-3, 3, size)

    covered_fractions = np.empty(trials)
    for t in range(trials):
        calib = draw(n)
        q_hat = calibrate(calib.tolist(), alpha)
        test = draw(m_test)
        covered_fractions[t] = np.mean(test <= q_hat)

    mean_cov = float(covered_fractions.mean())
    lo, hi = coverage_bounds(n, alpha)

    # Monte-Carlo standard error of the mean coverage across trials.
    se = covered_fractions.std(ddof=1) / math.sqrt(trials)
    tol = 5 * se + 0.005  # generous: 5 sigma + small slack

    # Lower guarantee: coverage must not fall below 1 - alpha (within MC error).
    assert mean_cov >= lo - tol, (
        f"under-coverage: mean={mean_cov:.4f} < {lo:.4f} (dist={dist}, n={n}, a={alpha})")
    # Upper guarantee (continuous, no ties): not much more conservative.
    assert mean_cov <= hi + tol, (
        f"over-coverage beyond sandwich: mean={mean_cov:.4f} > {hi:.4f} "
        f"(dist={dist}, n={n}, a={alpha})")


def test_coverage_is_distribution_free_reports_numbers(capsys):
    """Emit a compact coverage table so the guarantee is visible in test output."""
    rng = np.random.default_rng(7)
    trials = 4000
    m_test = 50
    print("\n--- empirical coverage (exponential scores) ---")
    for alpha in (0.05, 0.1, 0.2):
        for n in (100, 400):
            cov = np.empty(trials)
            for t in range(trials):
                calib = rng.exponential(1.0, n)
                q = calibrate(calib.tolist(), alpha)
                cov[t] = np.mean(rng.exponential(1.0, m_test) <= q)
            lo, hi = coverage_bounds(n, alpha)
            print(f"alpha={alpha:.2f} n={n:4d}  target>={lo:.3f}  "
                  f"empirical={cov.mean():.3f}  sandwich_hi={hi:.3f}")
            assert cov.mean() >= lo - 0.01
    # Force capture to show in -s runs; always passes.
    assert True


# --------------------------------------------------------------------------- #
# Conformal Risk Control: E[L] <= alpha
# --------------------------------------------------------------------------- #
def test_calibrate_risk_certifies_and_bounds_in_expectation():
    """The CRC-certified quantity ``(n/(n+1))*mean + b/(n+1)`` must (a) never fall
    below the empirical mean it bounds, and (b) upper-bound the TRUE mean *in
    expectation* over calibration draws.

    CRC controls the marginal expected loss, not a per-draw high-probability
    bound, so the correct check is on the average certified value across many
    independent calibration sets — that average must sit at or above the true
    mean (the bound is valid) and, for large n, close to it (it is tight)."""
    rng = np.random.default_rng(11)
    n = 400
    b = 1.0
    true_mean = 0.08

    certified_vals = []
    for _ in range(2000):
        calib = rng.binomial(1, true_mean, n).astype(float)  # losses in {0,1}
        certified = calibrate_risk(calib.tolist(), 0.1, b=b)
        # per-draw: certified must never be below the empirical mean it bounds
        assert certified >= calib.mean() - 1e-9
        certified_vals.append(certified)

    mean_certified = float(np.mean(certified_vals))
    # (b) valid in expectation: average certified bound >= true mean
    assert mean_certified >= true_mean - 1e-3
    # tight: within the analytic slack b/(n+1) of the true mean
    assert mean_certified <= true_mean + b / (n + 1) + 1e-3


def test_calibrate_risk_rejects_bad_bounds_and_ranges():
    with pytest.raises(ValueError):
        calibrate_risk([0.1, 0.2, 1.5], 0.1, b=1.0)  # loss > b
    with pytest.raises(ValueError):
        calibrate_risk([0.1, 0.2], 2.0, b=1.0)  # alpha > b
    with pytest.raises(ValueError):
        calibrate_risk([], 0.1, b=1.0)  # empty


def test_calibrate_risk_slack_shrinks_with_n():
    # The b/(n+1) slack term must shrink as n grows for the same mean loss.
    small = calibrate_risk([0.1] * 10, 0.5, b=1.0)
    large = calibrate_risk([0.1] * 1000, 0.5, b=1.0)
    assert large < small
    assert large == pytest.approx(0.1, abs=0.01)
