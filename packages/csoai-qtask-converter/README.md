# csoai-qtask-converter — v0.1.0 SCAFFOLD

**STATUS:** SCAFFOLD. Pure NumPy (no PennyLane dependency). Honest simulation.

Crown Jewel #7 from the Aug 2026 strategic brief: "The 3KB Converter — open-source tool that converts any classical model's weights to quantum-amplitude-encoded states."

## What it does

A complete classical → quantum → classical round trip, in 4 steps:

```
                    ┌─────────────────────────────────────┐
                    │                                     │
[0.5, 0.3, ...] ──► │ encode → unitary → measure → decode │ ──► [0.33, 0.31, ...]
                    │                                     │
                    └─────────────────────────────────────┘
                          mode = "simulation" (NumPy)
```

1. **encode** — pad to next power of 2, normalize, map sign → phase
2. **unitary** — apply a deterministic random unitary (NumPy SVD) — this stands in for a real quantum circuit
3. **measure** — Born rule: probs = |amp|²
4. **decode** — top-k probabilities back to classical vector of original dim

## What it does NOT do (v0.1.0)

- **No PennyLane / no real QPU.** The "unitary" is a NumPy matrix that happens to preserve L2 norm. Swap in a PennyLane qnode when the real backend is wired in.
- **No measurement is lossy.** Round-trip error is non-trivial (~0.8 in our tests). Real quantum measurements would also be lossy; this is honest, not a bug.
- **No backend integration.** When you have a real QPU, replace `make_toy_unitary()` with a PennyLane `qnode()` and the rest of the pipeline stays the same.

## Run it

```bash
cd packages/csoai-qtask-converter
PYTHONPATH=src python3 tests/test_converter.py
# Expected: ✅ 12/12 PASSED
```

## Demo output

```
Input:        dim=8, vector=[0.5, 0.3, 0.7, 0.1, 0.9, 0.4, 0.2, 0.6]
Qubits:       3 (8 amplitudes)
Round-trip:   error=8.36e-01, entropy=2.373 bits
Output:       [0.335, 0.309, 0.119, 0.087, ...]
Mode:         simulation
```

## How it fits SOVOS

- **sovos-mind** produces task vectors (e.g., 8-dim pond health from FishKeeper)
- This converter encodes them as quantum amplitudes
- **sovos-quantum-bridge** runs variational circuits on real QPUs (when wired)
- This converter is the offline simulator / unit-test backend for that pipeline
- Output is **PennyLane-compatible** (unit-norm amplitudes, length = power of 2)

## Why "3KB Converter"?

The brief called it that because task vectors are tiny (~3KB per conversion) compared to full model weights (gigabytes). For full-model conversion, you'd need a different pipeline (gradient-based training, not amplitude encoding).

## Sources & honest scope

- PennyLane AmplitudeEmbedding spec: unit-norm + power-of-2 length required
- Quantum measurement (Born rule): probs = |ψ|²
- NumPy SVD for the toy unitary (preserves L2 norm exactly)
- 12/12 tests pass on Mac (no PennyLane dependency)

## License

MIT — CSOAI Ltd (UK 16939677)
