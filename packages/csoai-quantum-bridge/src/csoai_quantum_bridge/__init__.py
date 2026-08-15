"""csoai-quantum-bridge — PennyLane implementation of the task-vector bridge.

What this does (real, not vapor):
  1. Takes a classical task vector (MergeKit-style: τ = θ_finetuned − θ_base).
  2. Encodes it as a quantum state via AmplitudeEmbedding (normalized
     classical vector → complex amplitudes of an n-qubit state).
  3. Runs a variational quantum circuit (the OWEM hive equivalent).
  4. Measures the result back to classical probabilities.
  5. Returns the "quantum-modified" task vector.

Honest scope: This is a SIMULATOR. We are running PennyLane on a CPU/GPU
emulator. There is no real quantum hardware in the loop. The math is
real; the substrate is simulated.

Why this matters architecturally: PennyLane is auto-differentiable. The
variational circuit can be gradient-trained against a classical loss.
This is the EXACT mechanism by which a future real quantum backend
(SAXON Q cloud API, IBM Quantum) would slot in — PennyLane supports
multiple backends with the same interface.

Requires: pennylane (installed on pod), numpy, scipy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import pennylane as qml
    _HAS_PENNYLANE = True
except ImportError:
    _HAS_PENNYLANE = False


# ---------------------------------------------------------------------------
# Encoding: classical task vector → quantum amplitudes
# ---------------------------------------------------------------------------
def task_vector_to_amplitudes(task_vector: np.ndarray,
                              target_n_qubits: Optional[int] = None) -> np.ndarray:
    """Map a classical real-valued task vector to normalized quantum amplitudes.

    PennyLane's AmplitudeEmbedding requires the input to be normalized
    (sum of squared amplitudes = 1) and to have a length that's a power of 2
    (because n qubits = 2^n amplitudes).

    For an arbitrary-length vector we:
    1. Pad to the next power of 2 (or to 2^target_n_qubits if given).
    2. Normalize so the squared L2 norm = 1.
    3. Map sign to phase: positive amplitudes stay real, negative get a phase.
    """
    v = np.asarray(task_vector, dtype=np.float64).flatten()
    n = v.shape[0]
    # If target_n_qubits given, use exactly 2^target_n_qubits. Else next pow2 ≥ n.
    if target_n_qubits is not None:
        target_len = 2 ** target_n_qubits
    else:
        target_len = max(2, 1 << (max(n, 1) - 1).bit_length())  # next pow2 ≥ max(n,1)
    if n > target_len:
        # Caller gave a vector larger than the chosen capacity — truncate.
        v = v[:target_len]
        n = target_len
    padded = np.zeros(target_len, dtype=np.float64)
    padded[:n] = v
    # Map negative values to phase (sign → imaginary axis)
    amplitudes = np.where(padded >= 0, padded, padded + 1j * np.abs(padded))
    # Normalize
    norm = np.linalg.norm(amplitudes)
    if norm < 1e-12:
        return amplitudes
    return amplitudes / norm


# ---------------------------------------------------------------------------
# Variational circuit: the "OWEM hive" in quantum form
# ---------------------------------------------------------------------------
def _make_hive_circuit(n_qubits: int, n_layers: int = 3):
    """Build a variational circuit equivalent to an OWEM hive.

    Structure: alternating rotation + entanglement layers.
    - Rotation: RX/RY/RZ per qubit with trainable parameters
    - Entanglement: CNOT chain (linear) connecting all qubits

    This is the simplest universal circuit: any unitary can be decomposed
    into rotations + CNOTs. n_layers=3 gives enough expressibility for
    small-dim task vectors without exploding the parameter count.
    """
    dev = qml.device("default.qubit", wires=n_qubits)

    @qml.qnode(dev, interface="autograd")
    def circuit(params, encoded_state):
        # 1. AmplitudeEmbedding: load the task vector as the initial state
        qml.AmplitudeEmbedding(encoded_state, wires=range(n_qubits),
                                normalize=True, pad_with=0.0)
        # 2. Variational layers
        for layer in range(n_layers):
            # Single-qubit rotations (trainable)
            for i in range(n_qubits):
                qml.RX(params[layer, i, 0], wires=i)
                qml.RY(params[layer, i, 1], wires=i)
                qml.RZ(params[layer, i, 2], wires=i)
            # Entanglement: linear CNOT chain
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
        # 3. Measurement: full probability vector over 2^n basis states
        return qml.probs(wires=range(n_qubits))

    return circuit


@dataclass
class QuantumHiveResult:
    input_vector_dim: int
    n_qubits: int
    n_layers: int
    n_circuit_params: int
    output_probabilities: np.ndarray   # shape (2**n_qubits,)
    measurement_entropy: float         # Shannon entropy of output probs
    output_vector: np.ndarray          # classical task vector back from measurement


# ---------------------------------------------------------------------------
# The bridge: vector in → vector out
# ---------------------------------------------------------------------------
class QuantumTaskVectorBridge:
    """Encode a classical MergeKit-style task vector, run a variational
    hive, measure back to classical. The "two become one."

    Lifecycle:
        1. Initialize with n_qubits and n_layers.
        2. For each task vector: encode → hive → measure.
        3. Optionally train the hive parameters by gradient descent
           against a classical loss (e.g. "preserve cosine similarity
           with a target vector").
    """

    def __init__(self, n_qubits: int = 4, n_layers: int = 3, seed: int = 42):
        if not _HAS_PENNYLANE:
            raise ImportError("pennylane is required: pip install pennylane")
        self.n_qubits = n_qubits
        self.n_layers = n_layers
        # Trainable circuit parameters: shape (n_layers, n_qubits, 3 rotations)
        rng = np.random.RandomState(seed)
        self.params = rng.uniform(-math.pi, math.pi,
                                   size=(n_layers, n_qubits, 3))
        self.circuit = _make_hive_circuit(n_qubits, n_layers)

    def forward(self, task_vector: np.ndarray) -> QuantumHiveResult:
        """Encode task_vector, run the hive, return measurement."""
        # Encode to exactly 2**self.n_qubits amplitudes
        amplitudes = task_vector_to_amplitudes(task_vector,
                                               target_n_qubits=self.n_qubits)
        probs = self.circuit(self.params, amplitudes)
        # Compute Shannon entropy (bits) of the output distribution
        # Zero-prob entries contribute 0
        p = np.asarray(probs, dtype=np.float64)
        # Numerical safety: ensure probs sum to 1 and clip
        p = np.clip(p, 0.0, 1.0)
        s = p.sum()
        if s > 0:
            p = p / s
        nonzero = p[p > 0]
        entropy = float(-np.sum(nonzero * np.log2(nonzero))) if len(nonzero) > 0 else 0.0
        # Map probabilities back to a classical "task vector" of original dim
        n_in = len(task_vector)
        # Take the top-n_in probabilities as the output signature
        # (preserves dimensionality of the input)
        sorted_probs = np.sort(p)[::-1]  # descending
        out_vec = sorted_probs[:n_in].copy()
        # Pad with zeros if probs shorter than input
        if len(out_vec) < n_in:
            out_vec = np.concatenate([out_vec, np.zeros(n_in - len(out_vec))])
        return QuantumHiveResult(
            input_vector_dim=n_in,
            n_qubits=self.n_qubits,
            n_layers=self.n_layers,
            n_circuit_params=self.params.size,
            output_probabilities=p,
            measurement_entropy=entropy,
            output_vector=out_vec,
        )

    def parameter_count(self) -> int:
        return int(self.params.size)

    def reset_parameters(self, seed: int = 42):
        rng = np.random.RandomState(seed)
        self.params = rng.uniform(-math.pi, math.pi,
                                   size=(self.n_layers, self.n_qubits, 3))


# ---------------------------------------------------------------------------
# Honest self-test: does it actually run?
# ---------------------------------------------------------------------------
def quantum_bridge_self_test() -> Dict[str, Any]:
    """Verify PennyLane is available + the bridge runs end-to-end."""
    info: Dict[str, Any] = {
        "pennylane_available": _HAS_PENNYLANE,
        "pennylane_version": qml.__version__ if _HAS_PENNYLANE else None,
        "bridge_works": False,
        "n_circuit_params": 0,
    }
    if not _HAS_PENNYLANE:
        return info
    try:
        # Use 3 qubits = 8-dim amplitudes. Sufficient for a small task vector.
        bridge = QuantumTaskVectorBridge(n_qubits=3, n_layers=2)
        v = np.array([0.5, -0.3, 0.2, 0.7, -0.1, 0.4, 0.6, -0.5])[:8]
        result = bridge.forward(v)
        info["bridge_works"] = True
        info["n_circuit_params"] = bridge.parameter_count()
        info["output_probabilities_shape"] = list(result.output_probabilities.shape)
        info["measurement_entropy"] = result.measurement_entropy
        info["output_vector_dim"] = len(result.output_vector)
        info["input_vector_dim"] = result.input_vector_dim
        info["n_qubits"] = result.n_qubits
    except Exception as e:
        info["bridge_error"] = str(e)
    return info


__all__ = [
    "task_vector_to_amplitudes",
    "_make_hive_circuit", "QuantumHiveResult",
    "QuantumTaskVectorBridge",
    "quantum_bridge_self_test",
]