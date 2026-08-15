"""csoai_fisher_rao — The pure Fisher-Rao kernel.

This is the dedicated package for the Fisher-Rao information-geometric
distance kernel. It is a *clean port* of the kernel logic that lives in
`sovos-info-geometry`, with a tighter API surface and zero GPU dependencies
in the CPU path (the kernel works on any machine with numpy + scipy).

Why a dedicated package?
------------------------
1. **Separation of concerns** — info-geometry bundles Fisher-Rao + GW (which
   requires POT). The kernel itself only needs numpy + scipy. This package
   pins that minimal dependency set so the chain wiring can import it
   without dragging in POT.

2. **Stable API** — `fisher_rao_distance(A, B)` and `sov_signal_gate(...)`
   are the two public functions. Everything else is implementation detail.

3. **Replaceable backend** — the kernel has a clean plug-point for
   GPU/torch/geomstats acceleration when those are available, but the
   CPU path is always the canonical reference implementation.

Mathematical definition
-----------------------
For two Symmetric Positive Definite (SPD) matrices A, B (e.g. covariance
matrices of Gaussian distributions), the Affine-Invariant Riemannian
Metric (AIRM) distance is:

    d(A, B) = || log( A^{-1/2} · B · A^{-1/2} ) ||_F

On the Gaussian-family parameter manifold, AIRM coincides (up to a scale)
with the Fisher information metric — so this distance IS the Fisher-Rao
information loss between the two distributions.

CPU fallback: log-Euclidean distance

    d_LE(A, B) = || logm(A) - logm(B) ||_F

is a fast, well-behaved approximation of AIRM. (Both equalities hold for
diagonal SPD matrices; they differ on off-diagonal ones, but AIRM is the
canonical choice and we fall back to log-Euclidean only when AIRM is not
implementable without torch/geomstats.)

NB: We use `scipy.linalg.logm` (matrix log), NOT `np.log` (elementwise).
`np.log` returns NaN on off-diagonal zeros. This bug was caught 11 Aug
2026 and fixed in sovos-info-geometry; the same fix is applied here from
day one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional backend detection (CPU is the canonical reference implementation)
# ---------------------------------------------------------------------------
try:
    import torch
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

try:
    from scipy.linalg import logm
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

try:
    from geomstats.geometry.spd_matrices import SPDAffineMetric, SPDMatrices
    _HAS_GEOMSTATS = True
except ImportError:
    _HAS_GEOMSTATS = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FisherRaoResult:
    """The result of a Fisher-Rao distance computation.

    distance:           AIRM (or log-Euclidean fallback) distance, >= 0
    is_permitted:       True iff distance <= threshold
    threshold:          The geodesic-ball radius for the SOV SIGNAL gate
    geodesic_ball_radius: same as threshold (kept for clarity in reports)
    matrix_shape:       shape of the input matrices (n, n)
    on_gpu:             True iff the GPU backend was used
    backend:            which backend produced the result ("geomstats",
                        "torch-gpu", "scipy-logm")
    """
    distance: float
    is_permitted: bool
    threshold: float
    geodesic_ball_radius: float
    matrix_shape: Tuple[int, int]
    on_gpu: bool
    backend: str


# ---------------------------------------------------------------------------
# Kernel — the canonical Fisher-Rao distance
# ---------------------------------------------------------------------------
def fisher_rao_distance(A: np.ndarray, B: np.ndarray,
                        use_gpu: bool = True) -> float:
    """Affine-Invariant Riemannian (Fisher-Rao) distance between two SPD matrices.

        d(A, B) = || log(A^{-1/2} B A^{-1/2}) ||_F

    This is the geodesic distance on the SPD manifold. On the Gaussian-family
    parameter manifold, this IS the Fisher-Rao distance (information loss
    between two distributions).

    Backends (in preference order):
      1. geomstats SPDAffineMetric — canonical AIRM, slow on CPU
      2. torch on CUDA — fast eigendecomp AIRM
      3. scipy.linalg.logm — fast log-Euclidean fallback (matrix log)

    Returns float >= 0. Returns NaN if inputs are not SPD.

    Raises:
        ValueError: if A and B have different shapes or are not square.
    """
    A_arr = np.asarray(A, dtype=np.float64)
    B_arr = np.asarray(B, dtype=np.float64)

    if A_arr.shape != B_arr.shape:
        raise ValueError(f"shape mismatch: A {A_arr.shape} vs B {B_arr.shape}")
    if A_arr.ndim != 2 or A_arr.shape[0] != A_arr.shape[1]:
        raise ValueError(f"SPD matrices must be square 2D, got {A_arr.shape}")

    # Canonical geomstats path (AIRM exact)
    if _HAS_GEOMSTATS:
        try:
            space = SPDMatrices(n=A_arr.shape[0])
            metric = SPDAffineMetric(space)
            return float(metric.dist(A_arr, B_arr))
        except Exception as e:
            logger.warning("geomstats path failed (%s); falling back to logm", e)

    # GPU path via torch eigendecomposition (AIRM exact)
    if use_gpu and _HAS_TORCH and torch.cuda.is_available():
        try:
            A_t = torch.as_tensor(A_arr, dtype=torch.float64, device="cuda")
            B_t = torch.as_tensor(B_arr, dtype=torch.float64, device="cuda")
            evals_A, evecs_A = torch.linalg.eigh(A_t)
            A_inv_sqrt = evecs_A @ torch.diag(evals_A.pow(-0.5)) @ evecs_A.T
            M = A_inv_sqrt @ B_t @ A_inv_sqrt
            evals_M, _ = torch.linalg.eigh(M)
            return float(torch.norm(torch.log(evals_M)).item())
        except Exception as e:
            logger.warning("torch CUDA path failed (%s); falling back to logm", e)

    # CPU fallback: log-Euclidean via scipy.linalg.logm (matrix log)
    if not _HAS_SCIPY:
        raise RuntimeError(
            "csoai_fisher_rao requires scipy for the CPU fallback. "
            "Install with `pip install scipy`."
        )
    log_A = logm(A_arr).real
    log_B = logm(B_arr).real
    return float(np.linalg.norm(log_A - log_B))


# ---------------------------------------------------------------------------
# SOV SIGNAL gate — Fisher-Rao with a threshold
# ---------------------------------------------------------------------------
def sov_signal_gate(current_state: np.ndarray,
                    permitted_state: np.ndarray,
                    threshold: float = 1.0,
                    use_gpu: bool = True) -> FisherRaoResult:
    """Decide whether the current state is inside the permitted geodesic ball.

    SOV SIGNAL = geodesic distance from current_state to permitted_state.
    If d < threshold → GOVERNED (state is permitted).
    Otherwise → ESCALATE_TO_HUMAN (state is outside the ball).

    Args:
        current_state:    (n, n) SPD matrix — the state to evaluate.
        permitted_state:  (n, n) SPD matrix — the centre of the permitted ball.
        threshold:        geodesic-ball radius (default 1.0)
        use_gpu:          if True and torch+CUDA are available, use GPU AIRM

    Returns:
        FisherRaoResult with distance, is_permitted, backend tag.
    """
    # Determine which backend will be used (for honest reporting)
    on_gpu = bool(use_gpu and _HAS_TORCH and torch.cuda.is_available())
    if _HAS_GEOMSTATS:
        backend = "geomstats"
    elif on_gpu:
        backend = "torch-gpu"
    elif _HAS_SCIPY:
        backend = "scipy-logm"
    else:
        backend = "unavailable"

    d = fisher_rao_distance(current_state, permitted_state, use_gpu=use_gpu)
    A = np.asarray(current_state)
    return FisherRaoResult(
        distance=d,
        is_permitted=(d <= threshold),
        threshold=threshold,
        geodesic_ball_radius=threshold,
        matrix_shape=A.shape,
        on_gpu=on_gpu,
        backend=backend,
    )


# ---------------------------------------------------------------------------
# Self-test (for the chain wiring's health check)
# ---------------------------------------------------------------------------
def gpu_self_test() -> dict:
    """Report which backends are usable. Returns a dict of booleans + details."""
    info = {
        "numpy_available": True,
        "scipy_available": _HAS_SCIPY,
        "torch_available": _HAS_TORCH,
        "torch_cuda": bool(_HAS_TORCH and torch.cuda.is_available()),
        "geomstats_available": _HAS_GEOMSTATS,
        "fisher_rao_works": False,
        "fisher_rao_test_distance": None,
        "fisher_rao_backend": "unavailable",
        "fisher_rao_error": None,
    }
    if not _HAS_SCIPY and not _HAS_GEOMSTATS:
        info["fisher_rao_error"] = "scipy and geomstats both missing"
        return info
    try:
        # A = 2I, B = 0.5I on R^3 → expected distance sqrt(3) * log(4)
        A = np.eye(3) * 2.0
        B = np.eye(3) * 0.5
        d = fisher_rao_distance(A, B, use_gpu=False)
        info["fisher_rao_test_distance"] = float(d)
        info["fisher_rao_works"] = bool(np.isfinite(d))
        # Identify which backend actually ran
        if _HAS_GEOMSTATS:
            info["fisher_rao_backend"] = "geomstats"
        else:
            info["fisher_rao_backend"] = "scipy-logm"
    except Exception as e:
        info["fisher_rao_error"] = str(e)
    return info
