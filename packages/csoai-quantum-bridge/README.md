# csoai-quantum-bridge — PennyLane implementation of task-vector → quantum

**The classical-to-quantum bridge for SOVOS. Real math, simulator substrate.**

## What it does

1. **Encode**: takes a classical MergeKit-style task vector `τ = θ_finetuned − θ_base`
   and maps it to normalized complex quantum amplitudes via
   `AmplitudeEmbedding`. Padding to next power of 2; negatives mapped to
   imaginary phase (sign → phase encoding).
2. **Hive**: runs a variational quantum circuit equivalent to an OWEM hive:
   alternating RX/RY/RZ rotations + linear CNOT entanglement. Universal
   gate set (any unitary can be decomposed).
3. **Measure**: extracts `qml.probs(wires=...)` — full probability
   distribution over all 2^n basis states. Maps back to a classical task
   vector of original dimensionality.

## Benchmarks on sov-brain-2 (PennyLane 0.45.1 simulator)

| n_qubits | n_layers | params | ms/run | entropy |
|---|---|---|---|---|
| 2 | 2 | 12 | 2.38 | 1.35 bits |
| 3 | 3 | 27 | 4.26 | 2.63 bits |
| 4 | 3 | 36 | 5.71 | 3.62 bits |
| 5 | 3 | 45 | 6.91 | 4.39 bits |
| 6 | 3 | 54 | 8.28 | 5.26 bits |

(Random inputs → entropy ≈ n_qubits = circuit produces rich distributions.)

## Honest scope

**This is a SIMULATOR.** PennyLane on the GPU pod runs circuits in software.
There is **no real quantum hardware** in the loop. The math is real; the
substrate is classical.

To upgrade to real hardware:
- IBM Quantum: `qml.device("qiskit.remote", wires=N, backend="ibmq_...")`
- IonQ: `qml.device("ionq.qpu", wires=N)`
- SAXON Q: no public API yet (as of 2026-08-10); would require private partnership.

## Run it

On pod (`sov-brain-2`):

```bash
ssh sov-brain-2
cd /workspace
source sov-governance-venv/bin/activate
PYTHONPATH=/workspace/csoai-quantum-bridge/src python3 -m pytest \
  /workspace/csoai-quantum-bridge/tests/test_bridge.py -v
```

Expected: `✅ 10/10 tests PASSED`

## Tests

1. `test_01_padds_to_power_of_2` — 3-dim vector → 4 amps
2. `test_02_normalizes_to_unit_vector` — `||amps||² = 1`
3. `test_03_negative_values_become_complex` — sign → imaginary phase
4. `test_04_zero_vector_safe` — no NaN on all-zero
5. `test_05_bridge_self_test` — PennyLane runs
6. `test_06_amplitude_embedding_round_trip` — input dim preserved
7. `test_07_different_inputs_produce_different_outputs`
8. `test_08_entropy_bounded` — `0 ≤ entropy ≤ n_qubits`
9. `test_09_parameter_count_matches_layers`
10. `test_10_reset_parameters_changes_them`

## License

MIT — CSOAI Ltd (UK 16939677)
