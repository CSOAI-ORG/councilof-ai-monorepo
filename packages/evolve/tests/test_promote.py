"""Tests for the promote-gate, including the -9.16 wrong-sign regression."""

from __future__ import annotations

import numpy as np
import pytest

from evolve import promote_if_better, promote_report


def _samples(mean, sd, n, seed):
    return np.random.default_rng(seed).normal(mean, sd, n).tolist()


# --------------------------------------------------------------------------- #
# PASS on a genuinely-better candidate
# --------------------------------------------------------------------------- #
def test_promotes_genuinely_better_candidate():
    baseline = _samples(70.0, 3.0, 200, seed=1)
    candidate = _samples(75.0, 3.0, 200, seed=2)  # clearly better by ~5
    assert promote_if_better(candidate, baseline, min_effect=1.0, significance=0.05)


def test_report_fields_on_promote():
    baseline = _samples(70.0, 3.0, 200, seed=1)
    candidate = _samples(75.0, 3.0, 200, seed=2)
    rep = promote_report(candidate, baseline, min_effect=1.0)
    assert rep.promote is True
    assert rep.sign_ok and rep.excludes_min_effect
    assert rep.effect > 1.0
    assert rep.lower_bound > 1.0
    assert "PROMOTE" in rep.reason


# --------------------------------------------------------------------------- #
# FAIL on a worse candidate
# --------------------------------------------------------------------------- #
def test_rejects_worse_candidate():
    baseline = _samples(70.0, 3.0, 200, seed=1)
    candidate = _samples(60.0, 3.0, 200, seed=2)  # clearly worse
    assert not promote_if_better(candidate, baseline, min_effect=1.0)


# --------------------------------------------------------------------------- #
# FAIL on wrong SIGN — the -9.16 regression
# --------------------------------------------------------------------------- #
def test_rejects_wrong_sign_delta_minus_9_16():
    """The estate bug: a delta of -9.16 was printed as 'beats' because the gate
    only checked CI-excludes-zero. A worse candidate's CI excludes zero too — on
    the wrong side. Our gate must reject it on the sign guard."""
    rng = np.random.default_rng(42)
    baseline = rng.normal(80.0, 2.0, 300).tolist()
    # candidate mean ~= baseline - 9.16: a large, statistically-clear REGRESSION
    candidate = rng.normal(80.0 - 9.16, 2.0, 300).tolist()

    rep = promote_report(candidate, baseline, min_effect=0.5, significance=0.05)
    assert rep.promote is False
    assert rep.sign_ok is False               # the guard that catches it
    assert rep.effect < 0                     # oriented effect is negative
    assert "wrong sign" in rep.reason.lower()
    # Its CI would indeed exclude zero (entirely negative) — prove the OLD logic
    # would have mis-fired, i.e. the interval does not straddle zero.
    assert rep.lower_bound < 0


def test_higher_is_better_false_flips_orientation():
    # When lower is better (e.g. loss/latency), a smaller candidate should PASS.
    baseline = _samples(50.0, 2.0, 200, seed=5)   # loss ~50
    candidate = _samples(40.0, 2.0, 200, seed=6)  # loss ~40 (better = lower)
    assert promote_if_better(candidate, baseline, min_effect=1.0,
                             higher_is_better=False)
    # And a larger (worse) loss candidate must fail on sign.
    worse = _samples(60.0, 2.0, 200, seed=7)
    rep = promote_report(worse, baseline, min_effect=1.0, higher_is_better=False)
    assert rep.promote is False and rep.sign_ok is False


# --------------------------------------------------------------------------- #
# FAIL when within noise (real but tiny / not clearing min_effect)
# --------------------------------------------------------------------------- #
def test_rejects_within_noise():
    """A candidate better by only ~0.3 with wide spread must not clear a
    min_effect of 2.0 — even though its sign is right."""
    baseline = _samples(70.0, 5.0, 120, seed=8)
    candidate = _samples(70.3, 5.0, 120, seed=9)
    rep = promote_report(candidate, baseline, min_effect=2.0, significance=0.05)
    assert rep.promote is False
    # sign may be positive but it does not clear the minimum detectable effect
    assert rep.excludes_min_effect is False
    assert "within noise" in rep.reason.lower()


def test_barely_positive_does_not_beat_zero_only():
    """Guard: a candidate whose effect is positive and whose CI excludes ZERO but
    NOT min_effect must be rejected (the whole point of min_effect)."""
    baseline = _samples(70.0, 1.0, 400, seed=10)
    candidate = _samples(70.5, 1.0, 400, seed=11)  # ~0.5 better, tight -> excludes 0
    # With min_effect 0 it would pass (excludes zero); with min_effect 2 it fails.
    assert promote_if_better(candidate, baseline, min_effect=0.0)
    assert not promote_if_better(candidate, baseline, min_effect=2.0)


# --------------------------------------------------------------------------- #
# scalar candidate regime + determinism + validation
# --------------------------------------------------------------------------- #
def test_scalar_candidate_regime():
    baseline = _samples(70.0, 3.0, 200, seed=12)
    # A single frozen candidate number well above the baseline distribution.
    assert promote_if_better(78.0, baseline, min_effect=1.0)
    assert not promote_if_better(69.0, baseline, min_effect=1.0)  # below baseline


def test_promote_is_reproducible():
    baseline = _samples(70.0, 3.0, 150, seed=13)
    candidate = _samples(73.0, 3.0, 150, seed=14)
    r1 = promote_report(candidate, baseline, min_effect=0.5, seed=99)
    r2 = promote_report(candidate, baseline, min_effect=0.5, seed=99)
    assert r1.lower_bound == r2.lower_bound and r1.promote == r2.promote


def test_ttest_method_also_works():
    baseline = _samples(70.0, 3.0, 200, seed=1)
    candidate = _samples(75.0, 3.0, 200, seed=2)
    rep = promote_report(candidate, baseline, min_effect=1.0, method="ttest")
    assert rep.promote is True
    assert "ttest" in rep.method
    # wrong-sign still rejected under t-test
    worse = _samples(60.0, 3.0, 200, seed=3)
    assert not promote_if_better(worse, baseline, min_effect=1.0, method="ttest")


def test_validation_errors():
    baseline = _samples(70.0, 3.0, 50, seed=1)
    with pytest.raises(ValueError):
        promote_if_better([71.0] * 10, baseline, min_effect=-1.0)  # negative min_effect
    with pytest.raises(ValueError):
        promote_if_better([71.0] * 10, baseline, min_effect=1.0, significance=0.9)
    with pytest.raises(ValueError):
        promote_if_better([71.0] * 10, [70.0], min_effect=1.0)  # baseline too small
