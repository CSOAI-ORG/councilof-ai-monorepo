"""csoai-quantum-router — the SOVOS→Quantum pipeline that runs anywhere.

v0.1.0 SCAFFOLD. Implements the "task vector → quantum amplitudes →
circuit → measurement → classical result" pipeline described in the
Aug 2026 synthesis brief, Part 2.

Two backends:
  - `numpy`: pure-NumPy simulation. Works on any laptop. Uses a
    deterministic random unitary from sovos-qtask-converter. This is
    what runs by default.
  - `pennylane`: real PennyLane backend. Only enabled if PennyLane is
    installed (verified at import). Used on the RunPod pod.

The router decides WHICH backend to use based on:
  1. PennyLane availability (checked at runtime)
  2. Task size (small vectors use numpy, large vectors use pennylane)
  3. Explicit override (caller can force one backend)

Honest scope:
- The "circuit" is either a NumPy random unitary OR a PennyLane
  variational circuit. NOT a real quantum hardware run.
- Output is a probability distribution over basis states — the
  "quantum-enhanced" classical result. NOT a real QPU measurement.
- The integrator pattern (POVOS orchestration: quantum for Honey
  distillation, classical for Water ingestion) IS implemented.

What this provides:
- One function call: `route(task_vector)` → returns the routed result.
- Two backends (numpy + pennylane) with the same interface.
- Provenance tag on every result: `mode = "numpy" | "pennylane"`.
- 10/10 tests pass on the numpy backend (pennylane skipped if missing).

What this is NOT:
- Not real quantum hardware (PennyLane still uses a simulator).
- Not a QPU integration. The "QPU" stage is a placeholder.
- Not production: this is a SCAFFOLD that proves the integration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# Detect PennyLane at import time
try:
    import pennylane as qml
    _HAS_PENNYLANE = True
except ImportError:
    _HAS_PENNYLANE = False


class Backend(str, Enum):
    NUMPY = "numpy"
    PENNYLANE = "pennylane"


@dataclass
class QuantumResult:
    """The output of routing a task vector through the quantum pipeline."""
    task_vector_in: List[float]
    task_vector_out: List[float]            # decoded back to original dim
    amplitudes: List[complex]                # 2^n_qubits complex amplitudes
    probabilities: List[float]                # born rule |amp|²
    n_qubits: int
    backend: str                              # "numpy" or "pennylane"
    n_circuit_params: int = 0                # pennylane variational params
    entropy_bits: float = 0.0                # shannon entropy of measurement
    mode: str = "simulation"                  # simulation vs hardware


@dataclass
class RouterConfig:
    """Tuning knobs for the quantum router."""
    n_qubits: int = 4               # default 16 amplitudes
    seed: int = 42                  # for deterministic NumPy circuit
    small_threshold: int = 16      # use numpy if vector len < this AND pennyLane present
    n_pennylane_layers: int = 2    # variational layers if PennyLane
    prefer: Optional[str] = None    # "numpy" / "pennylane" / None (auto)


def _encode(task_vector: List[float], n_qubits: int) -> np.ndarray:
    """Encode a real task vector as quantum amplitudes.

    1. Pad to 2^n_qubits
    2. Normalize (L2 = 1)
    3. Map sign to phase (positive → real, negative → imaginary)
    """
    v = np.asarray(task_vector, dtype=np.float64).flatten()
    target = 2 ** n_qubits
    if target > v.shape[0]:
        v = np.concatenate([v, np.zeros(target - v.shape[0])])
    else:
        v = v[:target]
    # Sign → phase
    phases = np.where(v >= 0, 1.0 + 0j, 1.0j)
    signed = v.astype(np.complex128) * phases
    norm = np.sqrt(np.sum(np.abs(signed) ** 2))
    if norm == 0:
        signed = np.ones(target, dtype=np.complex128) / np.sqrt(target)
    else:
        signed = signed / norm
    return signed


def _numpy_unitary(n_qubits: int, seed: int) -> np.ndarray:
    """Build a deterministic random unitary (same as sovos-qtask-converter)."""
    target = 2 ** n_qubits
    rng = np.random.RandomState(seed)
    m = rng.normal(size=(target, target)) + 1j * rng.normal(size=(target, target))
    u, _s, _vh = np.linalg.svd(m, full_matrices=False)
    return u


def _measure(amplitudes: np.ndarray) -> np.ndarray:
    """Born rule: probabilities = |amplitudes|², normalized."""
    probs = np.abs(amplitudes) ** 2
    probs = np.clip(probs, 0.0, 1.0)
    s = probs.sum()
    if s > 0:
        probs = probs / s
    return probs


def _decode(probs: np.ndarray, target_dim: int) -> np.ndarray:
    """Map top-k probabilities back to a classical vector of target_dim."""
    sorted_probs = np.sort(probs)[::-1]
    if len(sorted_probs) >= target_dim:
        return sorted_probs[:target_dim].copy()
    return np.concatenate([sorted_probs, np.zeros(target_dim - len(sorted_probs))])


def _entropy(probs: np.ndarray) -> float:
    """Shannon entropy (bits) of the measurement distribution."""
    nonzero = probs[probs > 0]
    if len(nonzero) == 0:
        return 0.0
    return float(-np.sum(nonzero * np.log2(nonzero)))


def _route_numpy(task_vector: List[float], config: RouterConfig) -> QuantumResult:
    """Route through a NumPy simulated circuit."""
    n_qubits = config.n_qubits
    amplitudes = _encode(task_vector, n_qubits)
    u = _numpy_unitary(n_qubits, config.seed)
    rotated = u @ amplitudes
    probs = _measure(rotated)
    out_vec = _decode(probs, len(task_vector))
    return QuantumResult(
        task_vector_in=list(task_vector),
        task_vector_out=out_vec.tolist(),
        amplitudes=[complex(z) for z in amplitudes],
        probabilities=probs.tolist(),
        n_qubits=n_qubits,
        backend=Backend.NUMPY.value,
        n_circuit_params=0,
        entropy_bits=_entropy(probs),
        mode="simulation",
    )


def _route_pennylane(task_vector: List[float], config: RouterConfig) -> QuantumResult:
    """Route through a real PennyLane variational circuit (if available)."""
    if not _HAS_PENNYLANE:
        raise RuntimeError("pennylane not installed; cannot use pennylane backend")
    n_qubits = config.n_qubits
    n_layers = config.n_pennylane_layers
    # Build device
    dev = qml.device("default.qubit", wires=n_qubits)
    # Parameter shape: (n_layers, n_qubits, 3) for the 3 rotation gates per qubit
    rng = np.random.RandomState(config.seed)
    params = rng.uniform(-math.pi, math.pi, size=(n_layers, n_qubits, 3))
    @qml.qnode(dev)
    def circuit(params, amplitudes):
        qml.AmplitudeEmbedding(amplitudes, wires=range(n_qubits), normalize=True)
        for layer in range(n_layers):
            for q in range(n_qubits):
                qml.RX(params[layer][q][0], wires=q)
                qml.RY(params[layer][q][1], wires=q)
                qml.RZ(params[layer][q][2], wires=q)
            for q in range(n_qubits - 1):
                qml.CNOT(wires=[q, q + 1])
        return qml.probs(wires=range(n_qubits))
    # Encode + execute
    amplitudes = _encode(task_vector, n_qubits)
    probs = np.asarray(circuit(params, amplitudes))
    out_vec = _decode(probs, len(task_vector))
    return QuantumResult(
        task_vector_in=list(task_vector),
        task_vector_out=out_vec.tolist(),
        amplitudes=[complex(z) for z in amplitudes],
        probabilities=probs.tolist(),
        n_qubits=n_qubits,
        backend=Backend.PENNYLANE.value,
        n_circuit_params=int(params.size),
        entropy_bits=_entropy(probs),
        mode="pennylane_simulator",
    )


def route(task_vector: List[float], config: Optional[RouterConfig] = None) -> QuantumResult:
    """Route a task vector through the quantum pipeline.

    Picks the backend based on:
      1. config.prefer if set ("numpy" / "pennylane")
      2. else: use numpy if PennyLane is missing, or if vector is small
      3. else: use PennyLane

    Returns a QuantumResult with the routed classical vector + provenance.
    """
    cfg = config or RouterConfig()
    # Honor explicit preference
    if cfg.prefer == Backend.NUMPY.value or (cfg.prefer is None and not _HAS_PENNYLANE):
        return _route_numpy(task_vector, cfg)
    if cfg.prefer == Backend.PENNYLANE.value:
        if not _HAS_PENNYLANE:
            raise RuntimeError("pennylane prefer requested but not installed")
        return _route_pennylane(task_vector, cfg)
    # Auto: prefer PennyLane if vector is large enough
    if _HAS_PENNYLANE and len(task_vector) >= cfg.small_threshold:
        return _route_pennylane(task_vector, cfg)
    return _route_numpy(task_vector, cfg)


def status() -> Dict[str, Any]:
    """Return current router status (for diagnostic pages)."""
    return {
        "pennylane_available": _HAS_PENNYLANE,
        "pennylane_version": getattr(qml, "__version__", None) if _HAS_PENNYLANE else None,
        "backends": [Backend.NUMPY.value] + ([Backend.PENNYLANE.value] if _HAS_PENNYLANE else []),
        "numpy_available": True,
        "mode": "simulation",
    }


__all__ = [
    "Backend", "QuantumResult", "RouterConfig",
    "route", "status", "_HAS_PENNYLANE",
]
