"""csoai-sigma-calibration — Uncertainty calibration for the SOVOS substrate.

The sigma-calibration doctrine (from the strategic brief):
    *Sigma calibration → then, and only then, the uncertainty pixel shader.*

Before the substrate may VISUALISE uncertainty (the pixel shader), the
underlying confidence scores MUST be well-calibrated. An uncalibrated
"90% confident" is meaningless noise painted on a screen. This package
is the gate that makes the visualisation honest.

What this package does:
  1. **Expected Calibration Error (ECE)** — the standard deviation of
     observed accuracy vs predicted confidence, bucketed.
  2. **Temperature scaling** — a single scalar `T` that rescales logits
     (T = 1 is no change; T < 1 increases confidence, T > 1 decreases
     it). Optimised by minimising negative log-likelihood.
  3. **Reliability diagram data** — (confidence_bin, observed_accuracy)
     pairs for plotting.
  4. **The CalibrationGate** — refuses to let an artifact be marked
     "shader-ready" unless ECE ≤ threshold (default 0.05, i.e. 5%).

The gate output is verdict + ECE + temperature + a chain_id for the
audit trail. This is the "sigma" the shader will read.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SIGMA_VERSION = "0.1.0"
DEFAULT_ECE_THRESHOLD = 0.05
DEFAULT_N_BINS = 10


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class CalibrationResult:
    """The result of one calibration run (before/after temperature scaling)."""
    ece_before: float
    ece_after: float
    temperature: float
    nll_before: float
    nll_after: float
    n_samples: int
    reliability: List[Dict[str, float]]       # confidence bin → observed accuracy
    passed_ece: bool
    threshold: float
    chain_id: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationGateVerdict:
    """The verdict of the calibration gate (is this shader-ready?)."""
    ready: bool
    ece: float
    temperature: float
    threshold: float
    n_samples: int
    reason: str
    chain_id: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core calibration maths
# ---------------------------------------------------------------------------
def _ece(confidences: np.ndarray, labels: np.ndarray, n_bins: int) -> float:
    """Expected Calibration Error.

    confidences: predicted probabilities in [0, 1]
    labels:      binary ground-truth labels in {0, 1}

    ECE = sum_b (|B_b| / n) * |acc(B_b) - conf(B_b)|
    """
    confidences = np.asarray(confidences, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    n = len(confidences)
    if n == 0:
        return 0.0
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for b in range(n_bins):
        lo, hi = bin_edges[b], bin_edges[b + 1]
        mask = (confidences > lo) & (confidences <= hi)
        # Include bin 0 boundary
        if b == 0:
            mask = (confidences >= lo) & (confidences <= hi)
        if mask.sum() == 0:
            continue
        bin_acc = float(labels[mask].mean())
        bin_conf = float(confidences[mask].mean())
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def _reliability_data(confidences: np.ndarray, labels: np.ndarray,
                      n_bins: int) -> List[Dict[str, float]]:
    """Reliability diagram data: (confidence_bin, observed_accuracy) pairs."""
    confidences = np.asarray(confidences, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    out = []
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    for b in range(n_bins):
        lo, hi = bin_edges[b], bin_edges[b + 1]
        mask = (confidences > lo) & (confidences <= hi)
        if b == 0:
            mask = (confidences >= lo) & (confidences <= hi)
        if mask.sum() == 0:
            out.append({"confidence": (lo + hi) / 2, "accuracy": None,
                        "n": 0})
        else:
            out.append({"confidence": (lo + hi) / 2,
                        "accuracy": float(labels[mask].mean()),
                        "n": int(mask.sum())})
    return out


def _nll(confidences: np.ndarray, labels: np.ndarray) -> float:
    """Negative log-likelihood of the labels under the probabilities."""
    confidences = np.clip(np.asarray(confidences, dtype=np.float64), 1e-12, 1 - 1e-12)
    labels = np.asarray(labels, dtype=np.float64)
    return float(-(labels * np.log(confidences) + (1 - labels) * np.log(1 - confidences)).mean())


def _temperature_scale(logits: np.ndarray, labels: np.ndarray,
                       max_iter: int = 200) -> Tuple[float, float]:
    """Find the optimal temperature T minimising NLL.

    post-T prob = sigmoid(logits / T). We binary-search / grid search
    T in (1e-3, 1e3) to minimise NLL. Returns (T, post_NLL).
    """
    logits = np.asarray(logits, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)

    def nll_at(t: float) -> float:
        # Numerically stable sigmoid via np.exp(-x) clipped
        x = np.clip(logits / t, -700.0, 700.0)
        p = 1.0 / (1.0 + np.exp(-x))
        p = np.clip(p, 1e-12, 1 - 1e-12)
        return float(-(labels * np.log(p) + (1 - labels) * np.log(1 - p)).mean())

    # Grid search log-space
    best_t, best_nll = 1.0, nll_at(1.0)
    ts = np.logspace(-3, 3, 400)
    for t in ts:
        nn = nll_at(float(t))
        if nn < best_nll:
            best_nll, best_t = nn, float(t)
    # Then a finer golden-section refinement around best_t
    lo, hi = best_t * 0.5, best_t * 2.0
    for _ in range(30):
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        if nll_at(float(m1)) < nll_at(float(m2)):
            hi = m2
        else:
            lo = m1
        best_t = (lo + hi) / 2
        best_nll = nll_at(float(best_t))
    return best_t, best_nll


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def calibrate(confidences: np.ndarray, labels: np.ndarray,
              logits: Optional[np.ndarray] = None,
              n_bins: int = DEFAULT_N_BINS,
              ece_threshold: float = DEFAULT_ECE_THRESHOLD) -> CalibrationResult:
    """Calibrate a set of confidence scores + find optimal temperature.

    Args:
        confidences:  predicted probabilities in [0, 1]
        labels:       binary ground-truth in {0, 1}
        logits:       (optional) raw logits — if present, used for
                      temperature scaling; if absent, confidences are
                      treated as if the model is already sigmoid-ed.
        n_bins:       ECE bin count
        ece_threshold: pass/fail threshold for the gate

    Returns:
        CalibrationResult.
    """
    confidences = np.asarray(confidences, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64).astype(int)
    if len(confidences) != len(labels):
        raise ValueError("confidences and labels must be same length")
    if len(confidences) == 0:
        raise ValueError("empty input")

    ece_before = _ece(confidences, labels, n_bins)
    nll_before = _nll(confidences, labels)

    temperature = 1.0
    if logits is not None:
        logits = np.asarray(logits, dtype=np.float64)
        if len(logits) != len(labels):
            raise ValueError("logits and labels must be same length")
        temperature, _ = _temperature_scale(logits, labels)
        # Post-T confidences
        post = 1.0 / (1.0 + np.exp(-logits / temperature))
        reliability = _reliability_data(post, labels, n_bins)
        ece_after = _ece(post, labels, n_bins)
        nll_after = _nll(post, labels)
        passed_ece = ece_after <= ece_threshold
    else:
        # No logits → can't temperature-scale; report before
        post = confidences
        reliability = _reliability_data(post, labels, n_bins)
        ece_after = ece_before
        nll_after = nll_before
        passed_ece = ece_before <= ece_threshold

    chain_body = json.dumps({
        "ece_before": ece_before, "ece_after": ece_after,
        "temperature": temperature, "n": len(labels),
        "passed": passed_ece, "threshold": ece_threshold,
    }, sort_keys=True).encode()
    chain_id = hashlib.sha256(chain_body).hexdigest()[:24]

    return CalibrationResult(
        ece_before=ece_before, ece_after=ece_after,
        temperature=temperature, nll_before=nll_before, nll_after=nll_after,
        n_samples=len(labels), reliability=reliability,
        passed_ece=passed_ece, threshold=ece_threshold, chain_id=chain_id,
    )


def calibration_gate(result: CalibrationResult,
                     ece_threshold: Optional[float] = None) -> CalibrationGateVerdict:
    """The gate: is this artifact's uncertainty shader-ready?

    An artifact may ONLY be marked "shader-ready" (i.e. allowed to be
    rendered by the uncertainty pixel shader) if:
      - ECE ≤ threshold (default 0.05), AND
      - enough samples (≥ 100 recommend)
    """
    threshold = ece_threshold if ece_threshold is not None else result.threshold
    enough_samples = result.n_samples >= 100
    ece_ok = result.ece_after <= threshold
    ready = ece_ok and enough_samples
    reasons = []
    if not ece_ok:
        reasons.append(f"ECE {result.ece_after:.4f} > {threshold}")
    if not enough_samples:
        reasons.append(f"only {result.n_samples} samples (need ≥100)")
    reason = "; ".join(reasons) if reasons else "calibrated + sufficient samples"
    chain_body = json.dumps({
        "ece": result.ece_after, "temperature": result.temperature,
        "n": result.n_samples, "ready": ready, "threshold": threshold,
    }, sort_keys=True).encode()
    chain_id = hashlib.sha256(chain_body).hexdigest()[:24]
    return CalibrationGateVerdict(
        ready=ready, ece=result.ece_after, temperature=result.temperature,
        threshold=threshold, n_samples=result.n_samples,
        reason=reason, chain_id=chain_id,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    """Smoke test: a well-calibrated set passes, a badly-calibrated set fails."""
    rng = np.random.RandomState(42)
    n = 500
    # Well-calibrated: confidence ≈ accuracy
    conf_good = np.clip(rng.uniform(0.5, 0.98, n), 0, 1)
    labels_good = (rng.uniform(0, 1, n) < conf_good).astype(int)
    # Temp-scaling path with logits
    logits = np.log(conf_good / (1 - conf_good)) + rng.randn(n) * 0.05

    res_good = calibrate(conf_good, labels_good, logits=logits)
    gate_good = calibration_gate(res_good)

    # Badly calibrated: 90% confident but only 50% accurate
    conf_bad = np.full(n, 0.9)
    labels_bad = rng.randint(0, 2, n)
    res_bad = calibrate(conf_bad, labels_bad, n_bins=10)
    gate_bad = calibration_gate(res_bad)

    return {
        "good_ece": res_good.ece_after,
        "good_ready": gate_good.ready,
        "good_temp": res_good.temperature,
        "bad_ece": res_bad.ece_after,
        "bad_ready": gate_bad.ready,
        "good_chain_len": len(gate_good.chain_id),
        "reliability_points": len(res_good.reliability),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
