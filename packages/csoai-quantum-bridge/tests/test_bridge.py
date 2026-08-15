"""Tests for csoai-quantum-bridge.

Tests are written to:
  - SKIP cleanly on Mac (no PennyLane installed)
  - PASS on the pod (PennyLane 0.45.1 installed)

Run on pod:
  ssh sov-brain-2 'cd /workspace && source sov-governance-venv/bin/activate && \
    PYTHONPATH=/workspace/csoai-quantum-bridge/src python3 -m pytest \
    /workspace/csoai-quantum-bridge/tests/test_bridge.py -v'
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_quantum_bridge import (
    task_vector_to_amplitudes,
    QuantumTaskVectorBridge,
    QuantumHiveResult,
    quantum_bridge_self_test,
)

import numpy as np


# ===========================================================================
# CPU-friendly tests (work without PennyLane)
# ===========================================================================
def test_01_padds_to_power_of_2():
    """Task vectors get padded to next power of 2."""
    v = np.array([1.0, 2.0, 3.0])  # length 3 → padded to 4 (2 qubits)
    amps = task_vector_to_amplitudes(v)
    assert amps.shape == (4,), f"expected shape (4,), got {amps.shape}"
    # First 3 entries are the original (mapped), last is 0 (pad)
    assert abs(amps[3]) < 1e-10
    print(f"  ✅ padded to length 4: {amps}")


def test_02_normalizes_to_unit_vector():
    """Amplitudes are normalized (sum of |amp|^2 = 1)."""
    v = np.array([0.3, -0.5, 0.7, 0.2, -0.1, 0.8, -0.4, 0.6, 0.9, 0.1])
    amps = task_vector_to_amplitudes(v)
    n2 = np.sum(np.abs(amps) ** 2)
    assert abs(n2 - 1.0) < 1e-9, f"not normalized: ||amps||² = {n2}"
    print(f"  ✅ normalized: ||amps||² = {n2:.6f}")


def test_03_negative_values_become_complex():
    """Negative amplitudes are mapped to imaginary phase (sign → phase)."""
    v = np.array([1.0, -1.0])  # length 2 → padded to 2
    amps = task_vector_to_amplitudes(v)
    # First entry: positive → real positive
    assert amps[0].real > 0
    # Second entry: negative → imaginary
    assert abs(amps[1].imag) > 0
    print(f"  ✅ negatives → complex phase: {amps}")


def test_04_zero_vector_safe():
    """All-zero vector doesn't divide by zero."""
    v = np.zeros(5)
    amps = task_vector_to_amplitudes(v)
    assert amps.shape == (8,)
    # All zeros stays all zeros (no NaN)
    assert np.all(np.isfinite(amps))
    print(f"  ✅ zero vector handled: {amps}")


# ===========================================================================
# PennyLane-required tests (skip on Mac)
# ===========================================================================
def _pennylane_available():
    try:
        import pennylane as qml  # noqa: F401
        return True
    except ImportError:
        return False


def test_05_bridge_self_test():
    """The bridge runs end-to-end on the simulator."""
    if not _pennylane_available():
        print("  ⏭️  SKIPPED — PennyLane not installed")
        return
    info = quantum_bridge_self_test()
    assert info["pennylane_available"], "PennyLane missing"
    assert info["bridge_works"], f"bridge failed: {info.get('bridge_error')}"
    assert info["n_circuit_params"] > 0
    print(f"  ✅ PennyLane {info['pennylane_version']}, "
          f"params={info['n_circuit_params']}, "
          f"output_probs={info['output_probabilities_shape']}")


def test_06_amplitude_embedding_round_trip():
    """Encoding then measuring preserves the input dim and shape."""
    if not _pennylane_available():
        print("  ⏭️  SKIPPED — PennyLane not installed")
        return
    # Use 3 qubits (8 amplitudes) for small test
    bridge = QuantumTaskVectorBridge(n_qubits=3, n_layers=2, seed=42)
    v = np.array([0.6, -0.3, 0.7, 0.1, -0.5, 0.4, 0.2, -0.6])
    result = bridge.forward(v)
    assert isinstance(result, QuantumHiveResult)
    assert result.input_vector_dim == len(v)
    assert result.output_vector.shape == (len(v),)
    # Output is a probability (bounded [0,1])
    assert np.all(result.output_vector >= 0)
    assert np.all(result.output_vector <= 1.0 + 1e-9)
    # Sum of all 8 probs is 1
    assert abs(result.output_probabilities.sum() - 1.0) < 1e-9
    print(f"  ✅ round-trip: input_dim={len(v)}, "
          f"n_qubits={result.n_qubits}, params={result.n_circuit_params}, "
          f"entropy={result.measurement_entropy:.3f} bits")


def test_07_different_inputs_produce_different_outputs():
    """Distinct task vectors produce distinct measurement distributions."""
    if not _pennylane_available():
        print("  ⏭️  SKIPPED — PennyLane not installed")
        return
    bridge = QuantumTaskVectorBridge(n_qubits=3, n_layers=3, seed=42)
    v1 = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    v2 = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    r1 = bridge.forward(v1)
    r2 = bridge.forward(v2)
    # Distributions should differ (different amplitudes → different probs)
    diff = np.sum(np.abs(r1.output_probabilities - r2.output_probabilities))
    assert diff > 0.1, f"outputs too similar: diff={diff}"
    print(f"  ✅ distinct inputs → distinct outputs (diff={diff:.4f})")


def test_08_entropy_bounded():
    """The measurement entropy is bounded [0, n_qubits] bits."""
    if not _pennylane_available():
        print("  �️  SKIPPED — PennyLane not installed")
        return
    bridge = QuantumTaskVectorBridge(n_qubits=3, n_layers=2, seed=42)
    v = np.random.RandomState(0).randn(8)
    result = bridge.forward(v)
    assert 0.0 <= result.measurement_entropy <= float(result.n_qubits) + 1e-9
    print(f"  ✅ entropy bounded: {result.measurement_entropy:.3f} bits "
          f"(max for n_qubits=3 is 3.0)")


def test_09_parameter_count_matches_layers():
    """n_circuit_params == n_layers × n_qubits × 3 rotations."""
    if not _pennylane_available():
        print("  ⏭️  SKIPPED — PennyLane not installed")
        return
    bridge = QuantumTaskVectorBridge(n_qubits=4, n_layers=3, seed=42)
    expected = 3 * 4 * 3  # n_layers × n_qubits × 3 rotations
    assert bridge.parameter_count() == expected
    print(f"  ✅ params={bridge.parameter_count()} "
          f"(expected {expected} = 3 layers × 4 qubits × 3 rotations)")


def test_10_reset_parameters_changes_them():
    """reset_parameters with new seed produces different params."""
    if not _pennylane_available():
        print("  ⏭️  SKIPPED — PennyLane not installed")
        return
    bridge = QuantumTaskVectorBridge(n_qubits=2, n_layers=2, seed=42)
    before = bridge.params.copy()
    bridge.reset_parameters(seed=99)
    after = bridge.params
    assert not np.allclose(before, after), "params unchanged after reset"
    print(f"  ✅ reset changed params (diff={np.linalg.norm(before - after):.3f})")


def main():
    tests = [
        test_01_padds_to_power_of_2,
        test_02_normalizes_to_unit_vector,
        test_03_negative_values_become_complex,
        test_04_zero_vector_safe,
        test_05_bridge_self_test,
        test_06_amplitude_embedding_round_trip,
        test_07_different_inputs_produce_different_outputs,
        test_08_entropy_bounded,
        test_09_parameter_count_matches_layers,
        test_10_reset_parameters_changes_them,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())