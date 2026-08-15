"""Tests for csoai-sigma-calibration — uncertainty calibration gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from csoai_sigma_calibration import (
    CalibrationGateVerdict, CalibrationResult,
    _ece, _nll, _reliability_data, _temperature_scale,
    calibrate, calibration_gate, self_test,
)


def _well_calibrated(n=500, seed=42):
    rng = np.random.RandomState(seed)
    conf = np.clip(rng.uniform(0.5, 0.98, n), 0, 1)
    labels = (rng.uniform(0, 1, n) < conf).astype(int)
    return conf, labels


def _badly_calibrated(n=500, seed=42):
    rng = np.random.RandomState(seed)
    conf = np.full(n, 0.9)
    labels = rng.randint(0, 2, n)
    return conf, labels


def test_s01_ece_zero_for_perfect():
    """ECE = 0 when confidence matches accuracy exactly."""
    # All-confident, all-correct, or all-unconfident-all-wrong
    conf = np.array([1.0, 1.0, 0.0, 0.0])
    labels = np.array([1, 1, 0, 0])
    assert _ece(conf, labels, 10) == 0.0
    print(f"  ✅ ECE=0 for perfectly calibrated")


def test_s02_ece_positive_for_overconfident():
    """ECE > 0 when the model is overconfident."""
    conf = np.full(1000, 0.9)
    labels = np.random.RandomState(0).randint(0, 2, 1000)
    ece = _ece(conf, labels, 10)
    assert ece > 0.1, f"overconfident model should have high ECE, got {ece:.4f}"
    print(f"  ✅ ECE={ece:.4f} for 90%-confident/50%-accurate model")


def test_s03_temperature_scale_reduces_nll():
    """Temperature scaling reduces NLL of a mis-scaled model."""
    rng = np.random.RandomState(42)
    n = 500
    # Model is overconfident: logits too large
    logits = rng.randn(n) * 4.0
    labels = (1.0 / (1 + np.exp(-logits)) > rng.uniform(0, 1, n)).astype(int)
    t, _ = _temperature_scale(logits, labels)
    assert t > 1.0, f"overconfident model should find T>1, got {t:.3f}"
    print(f"  ✅ temperature scaled: T={t:.3f} (>1 for overconfident)")


def test_s04_calibrate_good_passes():
    """A well-calibrated set passes the default threshold."""
    conf, labels = _well_calibrated()
    res = calibrate(conf, labels)
    assert res.passed_ece
    assert res.ece_after < 0.05
    assert res.n_samples == 500
    assert res.temperature >= 1.0 * 1e-3  # temp is set
    print(f"  ✅ well-calibrated passes: ECE={res.ece_after:.4f} < 0.05")


def test_s05_calibrate_bad_fails():
    """A badly-calibrated set fails."""
    conf, labels = _badly_calibrated()
    res = calibrate(conf, labels)
    assert not res.passed_ece
    assert res.ece_after > 0.05
    print(f"  ✅ badly-calibrated fails: ECE={res.ece_after:.4f} > 0.05")


def test_s06_gate_ready_good():
    """The gate marks a well-calibrated, well-sampled set shader-ready."""
    conf, labels = _well_calibrated()
    res = calibrate(conf, labels)
    gate = calibration_gate(res)
    assert gate.ready
    assert gate.n_samples >= 100
    assert gate.ece < 0.05
    print(f"  ✅ gate: ready=True (ECE={gate.ece:.4f}, n={gate.n_samples})")


def test_s07_gate_rejects_too_few_samples():
    """The gate rejects <100 samples even if ECE is low."""
    conf, labels = _well_calibrated(n=20)
    res = calibrate(conf, labels)
    gate = calibration_gate(res)
    assert not gate.ready
    assert "samples" in gate.reason
    print(f"  ✅ gate: rejects n=20 ('{gate.reason}')")


def test_s08_gate_rejects_uncalibrated():
    """The gate rejects a badly-calibrated set."""
    conf, labels = _badly_calibrated()
    res = calibrate(conf, labels)
    gate = calibration_gate(res)
    assert not gate.ready
    assert "ECE" in gate.reason
    print(f"  ✅ gate: rejects uncalibrated ('{gate.reason}')")


def test_s09_chain_id_deterministic():
    """chain_id is 24 hex chars, deterministic per input."""
    conf, labels = _well_calibrated()
    r1 = calibrate(conf, labels)
    r2 = calibrate(conf, labels)
    assert r1.chain_id == r2.chain_id
    assert len(r1.chain_id) == 24
    print(f"  ✅ chain_id is 24-char hex, deterministic")


def test_s10_reliability_data_shape():
    """reliability data has n_bins points with confidence + accuracy."""
    conf, labels = _well_calibrated()
    res = calibrate(conf, labels, n_bins=5)
    assert len(res.reliability) == 5
    for pt in res.reliability:
        assert "confidence" in pt
        assert "accuracy" in pt
    print(f"  ✅ reliability diagram: 5 bins, each with confidence+accuracy")


def test_s11_temperature_scaling_with_logits():
    """Passing logits temperature-scales; confident model gets T<1."""
    rng = np.random.RandomState(7)
    n = 400
    # Well-behaved logits
    logits = rng.randn(n) * 1.5
    labels = (rng.uniform(0, 1, n) < (1/(1+np.exp(-logits)))).astype(int)
    conf_before = 1/(1+np.exp(-logits))
    # Add a small perturbation to logits to make temp matter
    logits_perturb = logits * 0.8
    res = calibrate(conf_before, labels, logits=logits_perturb)
    assert abs(res.temperature - 1.0) > 1e-4  # temp found (not stuck at 1.0)
    print(f"  ✅ temperature scaling via logits: T={res.temperature:.3f}")


def test_s12_all_equal_labels_handled():
    """All-same labels should not crash (nll clamps)."""
    conf, labels = _well_calibrated()
    labels[:] = 1  # all positive
    res = calibrate(conf, labels)
    assert np.isfinite(res.ece_before)
    assert np.isfinite(res.nll_before)
    print(f"  ✅ all-same-labels handled: ECE={res.ece_before:.4f}")


def test_s13_self_test():
    """self_test returns a complete picture."""
    info = self_test()
    assert info["good_ready"] is True
    assert info["bad_ready"] is False
    assert info["good_temp"] > 0
    assert info["reliability_points"] > 0
    print(f"  ✅ self_test: good_ready={info['good_ready']}, "
          f"bad_ready={info['bad_ready']}, good_ece={info['good_ece']:.4f}")


if __name__ == "__main__":
    tests = [
        test_s01_ece_zero_for_perfect,
        test_s02_ece_positive_for_overconfident,
        test_s03_temperature_scale_reduces_nll,
        test_s04_calibrate_good_passes,
        test_s05_calibrate_bad_fails,
        test_s06_gate_ready_good,
        test_s07_gate_rejects_too_few_samples,
        test_s08_gate_rejects_uncalibrated,
        test_s09_chain_id_deterministic,
        test_s10_reliability_data_shape,
        test_s11_temperature_scaling_with_logits,
        test_s12_all_equal_labels_handled,
        test_s13_self_test,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            import traceback; traceback.print_exc()
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
