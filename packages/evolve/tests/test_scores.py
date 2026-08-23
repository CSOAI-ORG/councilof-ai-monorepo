"""Tests for the pluggable nonconformity scores."""

from __future__ import annotations

import numpy as np
import pytest

from evolve import (
    DistanceToCalibration,
    EnsembleDisagreement,
    NonconformityScore,
    OneMinusMaxSoftmax,
    distance_to_calibration,
    ensemble_disagreement,
    one_minus_max_softmax,
)


def test_all_scores_satisfy_protocol():
    assert isinstance(EnsembleDisagreement(), NonconformityScore)
    assert isinstance(OneMinusMaxSoftmax(), NonconformityScore)
    assert isinstance(DistanceToCalibration([[0.0], [1.0]]), NonconformityScore)


# --------------------------------------------------------------------------- #
# (a) ensemble disagreement
# --------------------------------------------------------------------------- #
def test_ensemble_variance_zero_when_members_agree():
    assert ensemble_disagreement([2.0, 2.0, 2.0]) == 0.0


def test_ensemble_variance_rises_with_spread():
    tight = ensemble_disagreement([0.9, 1.0, 1.1])
    wide = ensemble_disagreement([-5.0, 0.0, 5.0])
    assert wide > tight > 0.0


def test_ensemble_entropy_mode_on_prob_vectors():
    # Members all confident & agreeing -> low entropy.
    agree = ensemble_disagreement([[0.98, 0.01, 0.01], [0.97, 0.02, 0.01]])
    # Members disagree across classes -> mean dist near uniform -> high entropy.
    disagree = ensemble_disagreement([[0.98, 0.01, 0.01], [0.01, 0.98, 0.01],
                                      [0.01, 0.01, 0.98]])
    assert disagree > agree
    assert agree >= 0.0


def test_ensemble_determinism():
    x = [[0.5, 0.5], [0.3, 0.7], [0.9, 0.1]]
    assert ensemble_disagreement(x) == ensemble_disagreement(x)


# --------------------------------------------------------------------------- #
# (b) one minus max softmax
# --------------------------------------------------------------------------- #
def test_one_minus_max_softmax_logits():
    # Very peaked logits -> score near 0.
    s = one_minus_max_softmax([10.0, 0.0, 0.0])
    assert 0.0 <= s < 0.001
    # Flat logits over k classes -> score = 1 - 1/k.
    flat = one_minus_max_softmax([0.0, 0.0, 0.0, 0.0])
    assert flat == pytest.approx(0.75, abs=1e-9)


def test_one_minus_max_softmax_accepts_probs():
    s = one_minus_max_softmax([0.7, 0.2, 0.1], already_softmax=True)
    assert s == pytest.approx(0.3, abs=1e-9)


def test_one_minus_max_softmax_empty_raises():
    with pytest.raises(ValueError):
        one_minus_max_softmax([])


# --------------------------------------------------------------------------- #
# (c) distance to calibration (Mahalanobis)
# --------------------------------------------------------------------------- #
def test_distance_grows_with_offset():
    rng = np.random.default_rng(0)
    ref = rng.standard_normal((500, 3))
    scorer = DistanceToCalibration(ref)
    near = scorer.score([0.0, 0.0, 0.0])       # at the mean
    far = scorer.score([6.0, 6.0, 6.0])        # far out
    assert far > near >= 0.0


def test_distance_functional_matches_class():
    ref = [[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0], [0.5, 0.5]]
    a = distance_to_calibration([2.0, 2.0], ref)
    b = DistanceToCalibration(ref).score([2.0, 2.0])
    assert a == b


def test_distance_dim_mismatch_raises():
    scorer = DistanceToCalibration([[0.0, 0.0], [1.0, 1.0]])
    with pytest.raises(ValueError):
        scorer.score([1.0, 2.0, 3.0])


def test_distance_needs_two_rows():
    with pytest.raises(ValueError):
        DistanceToCalibration([[1.0, 2.0]])
