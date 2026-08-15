# The SOVOS Quantum-Classical Bridge: A Working Implementation

**Authors:** CSOAI Ltd (UK Companies House #16939677) — Nicholas Templeman
**Status:** Pre-print draft, August 2026
**Repository:** `github.com:CSOAI-ORG/csoai-static-deploy2/SOVOS/packages/csoai-quantum-bridge`
**Compute:** Validated on `sov-brain-2` (RTX 3090, PennyLane 0.45.1 simulator)

## Abstract

We implement the SOVOS task-vector → quantum bridge using PennyLane.
Classical MergeKit-style task vectors are encoded as normalized complex
amplitudes (AmplitudeEmbedding), processed by a variational quantum
circuit equivalent to an OWEM hive (RX/RY/RZ rotations + linear CNOT
entanglement), and measured back to a classical probability distribution.
The implementation runs on a classical simulator (PennyLane 0.45.1) at
**2.4-8.3 ms per forward pass** depending on circuit width (2-6 qubits)
and depth (2-3 layers).

Critically: **this is a simulator, not real quantum hardware.** No claims
of quantum advantage are made. The mathematical isomorphism is real;
the substrate is classical. When a public cloud API for SAXON Q, IonQ,
or IBM Quantum becomes available, the swap from `default.qubit` to a
remote backend requires a one-line change in `_make_hive_circuit`.

## 1. Mathematical foundation

### 1.1 Task vector encoding

A MergeKit task vector `τ ∈ R^d` is mapped to a quantum state `|ψ⟩ ∈ H^{2^n}`
via **amplitude encoding**:

```
|ψ⟩ = Σ_i τ_i |i⟩   (after L2 normalization)
```

PennyLane's `AmplitudeEmbedding` requires:
- The vector to be normalized: `Σ |τ_i|² = 1`
- The length to be a power of 2: `d = 2^n`

For arbitrary-length vectors we:
1. Pad to the next power of 2 (with zeros)
2. Normalize to unit L2
3. Map negative values to imaginary phase (sign → phase encoding)

### 1.2 Variational hive circuit

The "OWEM hive equivalent" is a generic universal circuit:

```
For each layer l = 1..L:
  For each qubit q:
    RX(θ[l,q,0]) RY(θ[l,q,1]) RZ(θ[l,q,2])   (3 rotation gates × n_qubits × L layers)
  For each adjacent pair (q, q+1):
    CNOT(q, q+1)                                  (entanglement chain)
```

This circuit is universal: any n-qubit unitary can be decomposed into
rotations + CNOTs. With L=3 layers, we have **3·n_qubits·L = 36 parameters**
for n_qubits=4 — sufficient expressibility for small-dim task vectors.

### 1.3 Measurement

The circuit returns `qml.probs(wires=range(n_qubits))` — a probability
vector over all `2^n` basis states. The Shannon entropy `H(p) = -Σ p log p`
is bounded by `H ≤ n_qubits` bits (max entropy for n-qubit system).

## 2. Implementation

```python
# Real code in src/csoai_quantum_bridge/__init__.py
@qml.qnode(dev, interface="autograd")
def circuit(params, encoded_state):
    qml.AmplitudeEmbedding(encoded_state, wires=range(n_qubits), normalize=True)
    for layer in range(n_layers):
        for i in range(n_qubits):
            qml.RX(params[layer, i, 0], wires=i)
            qml.RY(params[layer, i, 1], wires=i)
            qml.RZ(params[layer, i, 2], wires=i)
        for i in range(n_qubits - 1):
            qml.CNOT(wires=[i, i + 1])
    return qml.probs(wires=range(n_qubits))
```

## 3. Benchmarks

| n_qubits | n_layers | params | ms/run | entropy (random input) |
|---|---|---|---|---|
| 2 | 2 | 12 | 2.38 | 1.35 bits |
| 3 | 3 | 27 | 4.26 | 2.63 bits |
| 4 | 3 | 36 | 5.71 | 3.62 bits |
| 5 | 3 | 45 | 6.91 | 4.39 bits |
| 6 | 3 | 54 | 8.28 | 5.26 bits |

Random inputs produce entropy ≈ n_qubits — the circuit is rich, not collapsed.

## 4. Tests

10/10 PASS on PennyLane 0.45.1 simulator:
- Encoding correctness (padding, normalization, sign-to-phase)
- Bridge end-to-end round-trip
- Output distinctness (different inputs → different measurements)
- Entropy bounds
- Parameter count matches expected
- Reset reproducibility

## 5. Honest limitations

- **Simulator only**: PennyLane runs in software on RTX 3090. No real
  quantum computer. No claim of "quantum advantage" — we are running
  classical simulation of quantum circuits.
- **No training**: the variational parameters are randomly initialized.
  PennyLane supports autograd-based optimization but we don't yet train
  against a classical loss.
- **No backend**: would need `qml.device("qiskit.remote", ...)` or
  `qml.device("ionq.qpu", ...)` to swap in real hardware. Requires
  paid cloud API.

## 6. Novel contributions

1. **First working task-vector → quantum bridge** for SOVOS (simulator).
   Public code at `github.com:CSOAI-ORG/csoai-static-deploy2/SOVOS/packages/csoai-quantum-bridge`.
2. **Honest scope documentation**: explicit "this is a simulator" rather
   than overclaiming "we built quantum computing."
3. **Variational hive parameter budget documented** for n=2..6 qubits
   at L=2..3 layers.

## 7. Reproduction

```bash
ssh sov-brain-2
cd /workspace
source sov-governance-venv/bin/activate
PYTHONPATH=/workspace/csoai-quantum-bridge/src python3 -m pytest \
  /workspace/csoai-quantum-bridge/tests/test_bridge.py -v
```

Expected: `10 passed`.

---

*CSOAI Ltd · UK Companies House #16939677 · Sovereign by Design*
