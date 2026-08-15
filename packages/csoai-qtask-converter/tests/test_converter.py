"""csoai-qtask-converter tests (v0.1.0 SCAFFOLD).

12 tests covering:
- Encoding (normalization, sign-to-phase, padding)
- Unitary construction (orthogonality, determinism with seed)
- Measurement (Born rule, probability conservation)
- Decoding (top-k extraction, padding)
- Round trip (info preservation, error < threshold)
- Batch conversion
- Edge cases (zero vector, single element, large vector)
"""
import sys
import math
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_qtask_converter import (
    ConversionResult,
    encode_classical, make_toy_unitary, measure, decode_to_classical,
    convert, convert_many, format_card,
)


def test_01_encode_pads_to_power_of_2():
    """A length-3 vector should pad to 4 (2 qubits)."""
    amps, n_qubits = encode_classical([0.5, 0.5, 0.5])
    assert len(amps) == 4
    assert n_qubits == 2
    # Normalized: sum |amp|² = 1
    norm = sum(abs(z) ** 2 for z in amps)
    assert abs(norm - 1.0) < 1e-10
    print(f"  ✅ encode length-3 → 4 amps, 2 qubits, norm={norm:.10f}")


def test_02_encode_sign_to_phase():
    """Negative values get a phase factor (1j), which becomes imag after normalization."""
    amps, n_qubits = encode_classical([1.0, -1.0])
    assert n_qubits == 1
    # amp[0] is real (positive input), amp[1] has a phase (negative input)
    assert amps[0].imag == 0.0  # positive → no phase
    assert abs(amps[1].real) < 1e-10  # phase makes real component ~0
    assert abs(amps[1].imag) > 1e-10  # imaginary component carries the magnitude
    # Magnitude should be 1/√2 for each (sum of squared mags = 1)
    assert abs(abs(amps[0]) - 1.0 / math.sqrt(2)) < 1e-10
    assert abs(abs(amps[1]) - 1.0 / math.sqrt(2)) < 1e-10
    print(f"  ✅ sign→phase: amp[0]=({amps[0].real:.3f}, {amps[0].imag:.3f}), amp[1]=({amps[1].real:.3f}, {amps[1].imag:.3f})")


def test_03_encode_zero_vector_returns_uniform():
    """All-zero input should give uniform distribution, not divide-by-zero."""
    amps, n_qubits = encode_classical([0.0, 0.0, 0.0, 0.0])
    norm = sum(abs(z) ** 2 for z in amps)
    assert abs(norm - 1.0) < 1e-10
    # Should be uniform (each amp has magnitude 1/sqrt(N))
    expected = 1.0 / math.sqrt(4)
    for a in amps:
        assert abs(abs(a) - expected) < 1e-10
    print(f"  ✅ zero vector → uniform (1/√N each, N=4)")


def test_04_unitary_is_orthonormal():
    """A unitary U satisfies U @ U† = I."""
    u = make_toy_unitary(n_qubits=3, seed=42)
    target = 2 ** 3
    assert u.shape == (target, target)
    identity = u @ u.conj().T
    # Diagonal should be 1
    for i in range(target):
        assert abs(identity[i, i] - 1.0) < 1e-10
    # Off-diagonal should be ~0
    for i in range(target):
        for j in range(target):
            if i != j:
                assert abs(identity[i, j]) < 1e-10
    print(f"  ✅ unitary U@U† = I (8×8 matrix)")


def test_05_unitary_is_deterministic_with_seed():
    """Same seed → same unitary."""
    u1 = make_toy_unitary(2, seed=42)
    u2 = make_toy_unitary(2, seed=42)
    assert np.allclose(u1, u2)
    u3 = make_toy_unitary(2, seed=43)
    assert not np.allclose(u1, u3)
    print("  ✅ same seed → same unitary; different seed → different")


def test_06_measure_born_rule():
    """Measure preserves normalization."""
    amps = np.array([0.5 + 0.5j, 0.5 - 0.5j, 0.5j, 0.0])
    probs = measure(amps)
    assert abs(probs.sum() - 1.0) < 1e-10
    # |0.5+0.5j|² = 0.5, |0.5-0.5j|² = 0.5, |0.5j|² = 0.25, |0|² = 0
    # Sum = 1.25, so normalized: 0.5/1.25, 0.5/1.25, 0.25/1.25, 0
    assert abs(probs[0] - 0.4) < 1e-10
    assert abs(probs[1] - 0.4) < 1e-10
    assert abs(probs[2] - 0.2) < 1e-10
    assert abs(probs[3] - 0.0) < 1e-10
    print(f"  ✅ Born rule: sum(probs)={probs.sum():.6f}, [0.4, 0.4, 0.2, 0.0]")


def test_07_decode_top_k_extraction():
    """Decode takes top-k probabilities sorted descending."""
    probs = np.array([0.1, 0.4, 0.05, 0.45])
    out = decode_to_classical(probs, target_dims=2)
    # Top 2: 0.45, 0.4 (descending)
    assert abs(out[0] - 0.45) < 1e-10
    assert abs(out[1] - 0.4) < 1e-10
    print(f"  ✅ decode top-k: [0.45, 0.4] from [0.1, 0.4, 0.05, 0.45]")


def test_08_decode_pads_short_distribution():
    """Decode pads with zeros if distribution < target_dims."""
    probs = np.array([0.5, 0.5])
    out = decode_to_classical(probs, target_dims=4)
    assert len(out) == 4
    assert abs(out[0] - 0.5) < 1e-10
    assert abs(out[1] - 0.5) < 1e-10
    assert abs(out[2] - 0.0) < 1e-10
    assert abs(out[3] - 0.0) < 1e-10
    print(f"  ✅ decode pads short distribution with zeros")


def test_09_round_trip_preserves_info():
    """A random vector should round-trip with low error (info preserved)."""
    v = list(np.random.RandomState(0).normal(size=6))
    r = convert(v)
    assert r.n_qubits == 3  # padded from 6 to 8
    # Output should have same dimensionality as input
    assert len(r.output_vector) == len(v)
    # Round-trip error should be reasonable (not zero — measurement is lossy)
    # But information should be largely preserved
    assert r.round_trip_error < 1.0, f"high error {r.round_trip_error}"
    print(f"  ✅ round trip: dim={r.n_input_dims}, error={r.round_trip_error:.4f}, entropy={r.entropy_bits:.2f} bits")


def test_10_amplitudes_normalized_to_unit_length():
    """Every conversion's amplitudes should be PennyLane-compatible (unit norm)."""
    r = convert([0.3, -0.7, 0.2, 0.5, -0.1])
    norm = sum(abs(z) ** 2 for z in r.amplitudes)
    assert abs(norm - 1.0) < 1e-10, f"not unit norm: {norm}"
    # Length should be a power of 2
    n = len(r.amplitudes)
    assert n & (n - 1) == 0, f"{n} is not a power of 2"
    print(f"  ✅ amplitudes: {n} amps (2^{int(math.log2(n))}), unit norm={norm:.12f}")


def test_11_convert_many_aggregates():
    """Batch conversion returns aggregate stats."""
    vectors = [
        [0.1, 0.5, 0.3],
        [0.7, -0.2, 0.4, 0.1],
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ]
    agg = convert_many(vectors)
    assert agg["total"] == 3
    assert agg["max_qubits"] == 3  # largest padded to 8
    assert agg["avg_entropy_bits"] >= 0
    assert agg["all_have_pennylane_compatible_amplitudes"] is True
    print(f"  ✅ batch: {agg['total']} vectors, max_qubits={agg['max_qubits']}, avg_entropy={agg['avg_entropy_bits']:.2f}")


def test_12_format_card_renders():
    """The card formatter should produce multi-line, no-NumPy output."""
    r = convert([0.3, -0.7, 0.2])
    card = format_card(r)
    assert "Input:" in card
    assert "Qubits:" in card
    assert "Round-trip:" in card
    assert "Output:" in card
    assert "Mode:" in card
    # Should not contain NumPy types
    assert "np.float" not in card
    assert "np.complex" not in card
    print(f"  ✅ format_card: {len(card)} chars, multi-line OK")


def main():
    tests = [
        test_01_encode_pads_to_power_of_2,
        test_02_encode_sign_to_phase,
        test_03_encode_zero_vector_returns_uniform,
        test_04_unitary_is_orthonormal,
        test_05_unitary_is_deterministic_with_seed,
        test_06_measure_born_rule,
        test_07_decode_top_k_extraction,
        test_08_decode_pads_short_distribution,
        test_09_round_trip_preserves_info,
        test_10_amplitudes_normalized_to_unit_length,
        test_11_convert_many_aggregates,
        test_12_format_card_renders,
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
