"""Tests for csoai-quantum-router v0.1.0 SCAFFOLD.

10 tests covering:
- Backend detection (numpy always; pennylane conditional)
- Encoding: amplitudes are unit-norm, length is power of 2
- Decoding: round-trip preserves dimensionality
- Measurement: probabilities sum to 1
- NumPy backend runs deterministically with same seed
- PennyLane path skipped if not installed (no crash)
- Routing decision (auto: prefer numpy when pennylane missing)
- QuantumResult shape (all fields present)
- Status() returns correct shape
- Multiple preset task vectors (sovereign, koi health, etc.)
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_quantum_router import (
    Backend, QuantumResult, RouterConfig, route, status, _HAS_PENNYLANE,
)


def test_01_status_returns_correct_shape():
    s = status()
    assert "pennylane_available" in s
    assert "numpy_available" in s
    assert s["numpy_available"] is True
    assert Backend.NUMPY.value in s["backends"]
    if not _HAS_PENNYLANE:
        assert Backend.PENNYLANE.value not in s["backends"]
    print(f"  ✅ status: numpy_available={s['numpy_available']}, pennylane_available={s['pennylane_available']}")


def test_02_amplitudes_are_unit_norm():
    """The encoded amplitudes should have sum |amp|² = 1."""
    cfg = RouterConfig(n_qubits=3)
    r = route([0.5, 0.3, 0.7, 0.1, 0.9, 0.4, 0.2, 0.6], config=cfg)
    amp_sq = sum(abs(z) ** 2 for z in r.amplitudes)
    assert abs(amp_sq - 1.0) < 1e-10, f"amplitudes not unit norm: {amp_sq}"
    print(f"  ✅ amplitudes unit norm: ||amp||² = {amp_sq:.12f}")


def test_03_amplitudes_length_is_power_of_2():
    """Encoded length should be exactly 2^n_qubits."""
    for n_qubits in [2, 3, 4, 5]:
        cfg = RouterConfig(n_qubits=n_qubits)
        r = route([0.5, 0.3], config=cfg)
        assert len(r.amplitudes) == 2 ** n_qubits
        assert len(r.probabilities) == 2 ** n_qubits
    print(f"  ✅ amplitudes length = 2^n_qubits for n=2,3,4,5")


def test_04_probabilities_sum_to_1():
    """Born rule: probabilities sum to 1."""
    cfg = RouterConfig(n_qubits=3)
    r = route([0.5, -0.3, 0.2, 0.7], config=cfg)
    s = sum(r.probabilities)
    assert abs(s - 1.0) < 1e-10, f"probabilities don't sum to 1: {s}"
    print(f"  ✅ probabilities sum to 1.0 ({s:.12f})")


def test_05_decode_preserves_dimensionality():
    """The output vector should have the same length as the input."""
    cfg = RouterConfig(n_qubits=3)
    for v in [[1.0], [1.0, 0.5], [1.0, 0.5, 0.3, 0.7, 0.2, -0.1], list(range(20))]:
        r = route(v, config=cfg)
        assert len(r.task_vector_out) == len(v), \
            f"out dim {len(r.task_vector_out)} != in dim {len(v)}"
    print("  ✅ decode preserves dimensionality across vector sizes")


def test_06_numpy_backend_is_deterministic():
    """Same seed → same result. Different seed → different result."""
    cfg1 = RouterConfig(n_qubits=3, seed=42)
    cfg2 = RouterConfig(n_qubits=3, seed=42)
    cfg3 = RouterConfig(n_qubits=3, seed=99)
    r1 = route([0.5, 0.3, 0.7, 0.1], config=cfg1)
    r2 = route([0.5, 0.3, 0.7, 0.1], config=cfg2)
    r3 = route([0.5, 0.3, 0.7, 0.1], config=cfg3)
    assert r1.probabilities == r2.probabilities, "same seed should give same result"
    assert r1.probabilities != r3.probabilities, "different seeds should differ"
    print(f"  ✅ numpy backend deterministic (seed=42 reproducible, seed=99 differs)")


def test_07_pennylane_skipped_when_missing():
    """If PennyLane isn't installed, prefer='pennylane' should raise clearly."""
    if _HAS_PENNYLANE:
        print("  ⏭️  PennyLane IS installed on this Mac; skipping this test")
        return
    cfg = RouterConfig(n_qubits=2, prefer=Backend.PENNYLANE.value)
    try:
        route([0.5, 0.3], config=cfg)
        assert False, "should have raised"
    except RuntimeError as e:
        assert "pennylane" in str(e).lower()
    print("  ✅ pennylane prefer raises RuntimeError when not installed")


def test_08_auto_routing_picks_numpy_when_pennylane_missing():
    """Without PennyLane, auto-routing should always pick numpy."""
    if _HAS_PENNYLANE:
        print("  ⏭️  PennyLane IS installed; this test's premise is void")
        return
    r = route([0.5, 0.3, 0.7], config=RouterConfig(n_qubits=3))
    assert r.backend == Backend.NUMPY.value
    print(f"  ✅ auto routing picked '{r.backend}' (pennylane missing)")


def test_09_quantum_result_shape():
    """QuantumResult must have all required fields."""
    r = route([0.5, 0.3, 0.7], config=RouterConfig(n_qubits=2))
    assert isinstance(r, QuantumResult)
    assert isinstance(r.task_vector_in, list)
    assert isinstance(r.task_vector_out, list)
    assert isinstance(r.amplitudes, list)
    assert isinstance(r.probabilities, list)
    assert isinstance(r.n_qubits, int)
    assert r.backend in (Backend.NUMPY.value, Backend.PENNYLANE.value)
    assert r.mode in ("simulation", "pennylane_simulator")
    assert r.entropy_bits >= 0
    print(f"  ✅ QuantumResult: {r.n_qubits} qubits, entropy={r.entropy_bits:.3f} bits, backend={r.backend}")


def test_10_real_task_vectors_round_trip():
    """Run on realistic inputs (koi health, pond monitor, route score)."""
    cases = {
        "koi_health": [0.5, 0.3, 0.7, 0.1, 0.9, 0.4, 0.2, 0.6],   # 8 dims → 3 qubits
        "pond_temp": [22.5, 7.2, 0.8, 0.1],                          # 4 dims → 2 qubits
        "route_score": [0.95, 0.7, 0.5, 0.3, 0.1, -0.2],             # 6 dims → 3 qubits
    }
    for name, v in cases.items():
        cfg = RouterConfig(n_qubits=4)  # always 16 amps
        r = route(v, config=cfg)
        assert r.n_qubits == 4
        assert len(r.task_vector_out) == len(v)
        # Probabilities sum to 1
        assert abs(sum(r.probabilities) - 1.0) < 1e-10
        print(f"  ✅ {name:12s} ({len(v)} dims → {len(r.amplitudes)} amps, entropy={r.entropy_bits:.2f} bits)")


def main():
    tests = [
        test_01_status_returns_correct_shape,
        test_02_amplitudes_are_unit_norm,
        test_03_amplitudes_length_is_power_of_2,
        test_04_probabilities_sum_to_1,
        test_05_decode_preserves_dimensionality,
        test_06_numpy_backend_is_deterministic,
        test_07_pennylane_skipped_when_missing,
        test_08_auto_routing_picks_numpy_when_pennylane_missing,
        test_09_quantum_result_shape,
        test_10_real_task_vectors_round_trip,
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
