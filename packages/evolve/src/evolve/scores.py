"""Pluggable nonconformity scores.

A *nonconformity score* maps a model output (plus optional side information) to
a scalar where **higher means stranger** — more likely to need escalation. The
split-conformal machinery in :mod:`evolve.conformal` is agnostic to how the
score is produced; it only needs the scores on the calibration set to be
exchangeable with those seen at deployment.

Every score here is a **pure, deterministic function of its inputs** — the same
inputs always yield the same scalar. No randomness, no model call at scoring
time.

Three reference implementations:

- :class:`EnsembleDisagreement` (recommended) — spread across the outputs of a
  *decorrelated* ensemble. High disagreement = the members do not agree = the
  item is on a knife-edge and should escalate. Works on either scalar member
  outputs (uses variance) or member probability vectors (uses mean predictive
  entropy). Ensemble disagreement is the day-one mode-collapse guard: a single
  self-graded model can be confidently wrong, an ensemble that has decorrelated
  cannot hide its disagreement.
- :class:`OneMinusMaxSoftmax` — the classic ``1 - max_k p_k`` uncertainty. Cheap
  and standard; weaker than ensemble disagreement because a single overconfident
  model produces a small score even when wrong.
- :class:`DistanceToCalibration` — Mahalanobis distance of a feature vector to a
  reference (calibration) distribution. Flags *out-of-distribution* inputs the
  in-distribution scores would not catch.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

import numpy as np

__all__ = [
    "NonconformityScore",
    "EnsembleDisagreement",
    "OneMinusMaxSoftmax",
    "DistanceToCalibration",
    "ensemble_disagreement",
    "one_minus_max_softmax",
    "distance_to_calibration",
]


@runtime_checkable
class NonconformityScore(Protocol):
    """Interface for a nonconformity score.

    Implementations must be pure: ``score(x)`` depends only on ``x`` (and any
    parameters frozen at construction), never on hidden state or randomness.
    """

    def score(self, x) -> float:  # pragma: no cover - protocol definition
        ...

    def __call__(self, x) -> float:  # pragma: no cover - protocol definition
        ...


def _entropy(p: np.ndarray) -> np.ndarray:
    """Row-wise Shannon entropy (nats) of a probability matrix, tie-safe."""
    p = np.clip(p, 1e-12, 1.0)
    return -np.sum(p * np.log(p), axis=-1)


# --------------------------------------------------------------------------- #
# (a) Ensemble disagreement  (recommended)
# --------------------------------------------------------------------------- #
class EnsembleDisagreement:
    """Disagreement across decorrelated ensemble member outputs.

    Two input shapes are supported and auto-detected per call:

    - **Scalar members** — ``x`` is a 1-D sequence of ``m`` member outputs
      (e.g. each member's predicted value or logit). Score = population variance
      across members. Zero when all members agree.
    - **Probability-vector members** — ``x`` is an ``(m, k)`` array: ``m``
      members each emitting a ``k``-class probability vector. Score = mean
      predictive entropy across members, i.e. the entropy of the mean
      distribution (a.k.a. the *total* uncertainty), which rises with member
      disagreement. Rows are renormalised defensively.

    Deterministic: pure function of ``x``.
    """

    def __init__(self, *, mode: str = "auto") -> None:
        if mode not in ("auto", "variance", "entropy"):
            raise ValueError("mode must be 'auto', 'variance' or 'entropy'")
        self.mode = mode

    def score(self, x) -> float:
        arr = np.asarray(x, dtype=float)
        mode = self.mode
        if mode == "auto":
            mode = "variance" if arr.ndim == 1 else "entropy"

        if mode == "variance":
            if arr.ndim != 1:
                arr = arr.reshape(-1)
            if arr.size < 2:
                return 0.0
            return float(np.var(arr))  # population variance; 0 iff all equal

        # entropy mode: (m, k) -> entropy of the mean member distribution
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        row_sums = arr.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        probs = arr / row_sums
        mean_dist = probs.mean(axis=0, keepdims=True)  # (1, k)
        return float(_entropy(mean_dist)[0])

    def __call__(self, x) -> float:
        return self.score(x)


# --------------------------------------------------------------------------- #
# (b) One minus max softmax
# --------------------------------------------------------------------------- #
class OneMinusMaxSoftmax:
    """Classic ``1 - max_k softmax(logits)_k`` uncertainty score.

    If ``already_softmax`` is True, ``x`` is treated as a probability vector and
    used directly (renormalised defensively); otherwise ``x`` is treated as
    logits and passed through a numerically stable softmax.
    """

    def __init__(self, *, already_softmax: bool = False) -> None:
        self.already_softmax = already_softmax

    def score(self, x) -> float:
        arr = np.asarray(x, dtype=float).reshape(-1)
        if arr.size == 0:
            raise ValueError("logits/probs must be non-empty")
        if self.already_softmax:
            total = arr.sum()
            probs = arr / (total if total != 0 else 1.0)
        else:
            z = arr - arr.max()  # stability
            e = np.exp(z)
            probs = e / e.sum()
        return float(1.0 - probs.max())

    def __call__(self, x) -> float:
        return self.score(x)


# --------------------------------------------------------------------------- #
# (c) Distance to calibration (Mahalanobis-ish)
# --------------------------------------------------------------------------- #
class DistanceToCalibration:
    """Mahalanobis distance of a feature vector to a reference distribution.

    Fit on a matrix of calibration feature rows; at score time returns the
    Mahalanobis distance of a query vector to that reference mean under the
    (ridge-regularised, pseudo-inverted) reference covariance. Larger = further
    out-of-distribution = stranger.

    Deterministic once fit: the mean and inverse-covariance are frozen at
    construction.
    """

    def __init__(self, reference: Sequence[Sequence[float]], *,
                 ridge: float = 1e-6) -> None:
        ref = np.asarray(reference, dtype=float)
        if ref.ndim == 1:
            ref = ref.reshape(-1, 1)
        if ref.shape[0] < 2:
            raise ValueError("need at least 2 reference rows to estimate covariance")
        self.mean_ = ref.mean(axis=0)
        d = ref.shape[1]
        cov = np.cov(ref, rowvar=False)
        cov = np.atleast_2d(cov)
        cov = cov + ridge * np.eye(d)  # regularise for invertibility
        self.inv_cov_ = np.linalg.pinv(cov)

    def score(self, x) -> float:
        v = np.asarray(x, dtype=float).reshape(-1)
        if v.shape[0] != self.mean_.shape[0]:
            raise ValueError(
                f"query dim {v.shape[0]} != reference dim {self.mean_.shape[0]}")
        delta = v - self.mean_
        d2 = float(delta @ self.inv_cov_ @ delta)
        d2 = max(d2, 0.0)  # guard tiny negatives from numerical error
        return float(np.sqrt(d2))

    def __call__(self, x) -> float:
        return self.score(x)


# --------------------------------------------------------------------------- #
# Functional aliases (pure functions of inputs)
# --------------------------------------------------------------------------- #
def ensemble_disagreement(x, *, mode: str = "auto") -> float:
    """Functional form of :class:`EnsembleDisagreement`."""
    return EnsembleDisagreement(mode=mode).score(x)


def one_minus_max_softmax(x, *, already_softmax: bool = False) -> float:
    """Functional form of :class:`OneMinusMaxSoftmax`."""
    return OneMinusMaxSoftmax(already_softmax=already_softmax).score(x)


def distance_to_calibration(x, reference, *, ridge: float = 1e-6) -> float:
    """Functional form of :class:`DistanceToCalibration`."""
    return DistanceToCalibration(reference, ridge=ridge).score(x)
