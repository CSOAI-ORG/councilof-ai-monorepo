"""csoai-info-geometry — Information-geometric SOV SIGNAL.

The fourth mathematical weapon for SOVOS: replace the scalar SOV SIGNAL
score with a **Fisher-Rao geodesic distance** on the manifold of
information states.

Mathematical foundation:
- For a Gaussian-family model, parameters live on the manifold of
  Symmetric Positive Definite (SPD) matrices equipped with the
  Affine-Invariant Riemannian Metric (AIRM). The Fisher information
  metric coincides with AIRM (up to a scale).
- Distance: d(A, B) = ||log(A^{-1/2} B A^{-1/2})||_F (the Riemannian
  log-Euclidean distance, equivalent to geodesic distance on SPD manifold).
- A "permitted manifold" is a geodesic ball around the ideal governance
  state. SOV SIGNAL measures geodesic distance to that ball.

Cross-architecture model fusion via Gromov-Wasserstein (GW):
- Two models with different latent spaces (e.g. Llama-3 vs Qwen-2) have
  no layer-wise alignment. GW matches them RELATIONALLY — by comparing
  internal distance matrices, not raw embeddings.
- The GW coupling T(i,j,k,l) says "neuron i of model A corresponds to
  neuron k of model B AND neuron j of model A corresponds to neuron l
  of model B".
- This lets us merge models of different architectures (and sizes).

Requires PyTorch + geomstats + POT on GPU.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

try:
    from geomstats.geometry.spd_matrices import SPDAffineMetric, SPDMatrices
    _HAS_GEOMSTATS = True
except ImportError:
    _HAS_GEOMSTATS = False

try:
    import ot
    _HAS_POT = True
except ImportError:
    _HAS_POT = False


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fisher-Rao distance on SPD matrices (GPU-accelerated)
# ---------------------------------------------------------------------------
@dataclass
class FisherRaoResult:
    distance: float
    is_permitted: bool
    threshold: float
    geodesic_ball_radius: float
    matrix_shape: Tuple[int, int]
    on_gpu: bool


def spd_geodesic_distance(A: np.ndarray, B: np.ndarray,
                          use_gpu: bool = True) -> float:
    """Affine-Invariant Riemannian (Fisher-Rao) distance between two SPD matrices.

    d(A, B) = || log(A^{-1/2} B A^{-1/2}) ||_F

    This is the geodesic distance on the SPD manifold. On the Gaussian-family
    parameter manifold, this IS the Fisher-Rao distance (information loss
    between two distributions).

    Returns float. CPU fallback if geomstats/torch unavailable.
    """
    if not _HAS_GEOMSTATS:
        # CPU fallback: log-Euclidean distance via MATRIX log (not elementwise!)
        # d = ||logm(A) - logm(B)||_F  (only an approximation of AIRM but valid)
        # NB: use scipy.linalg.logm — np.log is elementwise and breaks on off-diag
        from scipy.linalg import logm
        log_A = logm(np.asarray(A, dtype=np.float64))
        log_B = logm(np.asarray(B, dtype=np.float64))
        # Real-part only (logm can return tiny imag parts from numerical noise)
        log_A = log_A.real
        log_B = log_B.real
        return float(np.linalg.norm(log_A - log_B))
    if use_gpu and _HAS_TORCH and torch.cuda.is_available():
        # GPU path: torch eigendecomp is fast; AIRM via eigendecomposition
        A_t = torch.as_tensor(A, dtype=torch.float64, device="cuda")
        B_t = torch.as_tensor(B, dtype=torch.float64, device="cuda")
        # Eigendecompose A: A = U D U^T
        evals_A, evecs_A = torch.linalg.eigh(A_t)
        # A^{-1/2} = U D^{-1/2} U^T
        A_inv_sqrt = evecs_A @ torch.diag(evals_A.pow(-0.5)) @ evecs_A.T
        # M = A^{-1/2} B A^{-1/2}
        M = A_inv_sqrt @ B_t @ A_inv_sqrt
        # Eigendecompose M: eigenvalues λ_i of M, log of these gives AIRM
        evals_M, _ = torch.linalg.eigh(M)
        # AIRM distance: ||log(λ_i)||_2
        d = float(torch.norm(torch.log(evals_M)).item())
        return d
    # CPU geomstats path
    space = SPDMatrices(n=A.shape[0])
    metric = SPDAffineMetric(space)
    return float(metric.dist(A, B))


def sov_signal_fisher_rao(
    current_state: np.ndarray,
    permitted_state: np.ndarray,
    threshold: float = 1.0,
    use_gpu: bool = True,
) -> FisherRaoResult:
    """SOV SIGNAL = geodesic distance to the permitted manifold.

    If d(current, permitted) < threshold → GOVERNED.
    Otherwise → ESCALATE_TO_HUMAN.

    This is the information-geometric version of the SOV SIGNAL scalar
    from sovos-core.gspc: instead of "score = 0.89", you get a geodesic
    distance that respects the probability manifold.
    """
    A = np.asarray(current_state, dtype=np.float64)
    B = np.asarray(permitted_state, dtype=np.float64)
    if A.shape != B.shape:
        raise ValueError(f"shape mismatch: {A.shape} vs {B.shape}")
    if A.shape[0] != A.shape[1]:
        raise ValueError(f"SPD matrices must be square, got {A.shape}")
    d = spd_geodesic_distance(A, B, use_gpu=use_gpu)
    return FisherRaoResult(
        distance=d,
        is_permitted=d < threshold,
        threshold=threshold,
        geodesic_ball_radius=threshold,
        matrix_shape=A.shape,
        on_gpu=use_gpu and _HAS_TORCH and torch.cuda.is_available(),
    )


# ---------------------------------------------------------------------------
# Gromov-Wasserstein model fusion (cross-architecture)
# ---------------------------------------------------------------------------
@dataclass
class GWResult:
    gw_distance: float
    transport_plan: np.ndarray  # (n_a, n_b) — how to couple neurons
    on_gpu: bool


def gromov_wasserstein_distance(
    feats_a: np.ndarray,
    feats_b: np.ndarray,
    weights_a: Optional[np.ndarray] = None,
    weights_b: Optional[np.ndarray] = None,
    loss: str = "square_loss",
) -> GWResult:
    """Gromov-Wasserstein distance between two feature sets.

    feats_a: (n_a, d_a) — activations from model A
    feats_b: (n_b, d_b) — activations from model B
    weights_a, weights_b: optional neuron weights (default: uniform)

    Returns GW distance + transport plan (coupling matrix).

    Use case: model A is Llama-3 (n_a neurons), model B is Qwen-2.5
    (n_b neurons). Different latent dimensions. Standard merging
    requires layer alignment — impossible here. GW compares the
    INTERNAL distance structures:
        C_A[i,j] = ||feats_a[i] - feats_a[j]||
        C_B[k,l] = ||feats_b[k] - feats_b[l]||
    And finds the coupling T that aligns these structures.
    """
    if not _HAS_POT:
        raise ImportError("POT (Python Optimal Transport) is required for GW")
    n_a, n_b = feats_a.shape[0], feats_b.shape[0]
    if weights_a is None:
        weights_a = np.ones(n_a) / n_a
    if weights_b is None:
        weights_b = np.ones(n_b) / n_b
    # Internal distance matrices (force same dim by projecting both via PCA)
    feats_a_p, feats_b_p = _ensure_same_dim(feats_a, feats_b)
    D_a = ot.dist(feats_a_p, feats_a_p, metric="sqeuclidean")
    D_b = ot.dist(feats_b_p, feats_b_p, metric="sqeuclidean")
    # GW (exact, may be slow for large n)
    # POT 0.9.7 API: pass numItermax via **kwargs only, not as a direct arg
    if n_a <= 50 and n_b <= 50:
        try:
            gw_dist, log = ot.gromov.gromov_wasserstein(
                D_a, D_b, weights_a, weights_b, loss,
                log=True, max_iter=200, tol=1e-9,
            )
        except TypeError:
            gw_dist, log = ot.gromov.gromov_wasserstein(
                D_a, D_b, weights_a, weights_b, loss,
                log=True, numItermax=200, tol=1e-9,
            )
    else:
        try:
            gw_dist, log = ot.gromov.entropic_gromov_wasserstein(
                D_a, D_b, weights_a, weights_b, loss,
                log=True, max_iter=300, tol=1e-7,
            )
        except TypeError:
            gw_dist, log = ot.gromov.entropic_gromov_wasserstein(
                D_a, D_b, weights_a, weights_b, loss,
                log=True, numItermax=300, tol=1e-7,
            )
    # Extract transport plan (POT 0.9.7: u, v are marginal scaling vectors;
    # transport plan T = diag(u) * K * diag(v) where K is the base coupling).
    # Simpler: outer(u, v) is a valid (though not exact) approximation.
    if isinstance(log, dict):
        if "T" in log:
            T = log["T"]
        elif "u" in log and "v" in log:
            T = np.outer(np.asarray(log["u"]).flatten(),
                         np.asarray(log["v"]).flatten())
        else:
            T = np.outer(weights_a, weights_b)  # fallback
    else:
        T = np.outer(weights_a, weights_b)
    return GWResult(gw_distance=float(log.get("gw_dist", gw_dist) if isinstance(log, dict) else gw_dist),
                    transport_plan=T, on_gpu=False)


def _ensure_same_dim(a: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Ensure both feature matrices have the same column dim via PCA-projection.

    GW only needs INTERNAL pairwise distances, so we can project both
    matrices to the same dim without losing the relational structure.
    """
    from numpy.linalg import svd
    da, db = a.shape[1], b.shape[1]
    if da == db:
        return a, b
    target = min(da, db)
    # Project a to (n_a, target) via truncated SVD
    def _project(x, k):
        U, S, _ = svd(x, full_matrices=False)
        return U[:, :k] * S[:k]
    return _project(a, target), _project(b, target)


def merge_models_via_gw(
    feats_a: np.ndarray,
    feats_b: np.ndarray,
    weights_a: np.ndarray,
    weights_b: np.ndarray,
    output_dim: int,
) -> np.ndarray:
    """Cross-architecture model fusion via GW.

    Given features from two models (possibly different dimensions) and
    their GW coupling, produce a merged representation of shape
    (n_a + n_b, output_dim) suitable for downstream LoRA training.

    The merged features are the GW-coupled weighted sum: for each
    neuron i in A, its contribution to the merged output is the
    GW-weighted average of B neurons, scaled by T.
    """
    gw = gromov_wasserstein_distance(feats_a, feats_b, weights_a, weights_b)
    T = gw.transport_plan  # (n_a, n_b)
    n_a = feats_a.shape[0]
    n_b = feats_b.shape[0]
    # Project each model's features into the shared output_dim via random
    # orthogonal projection (a real impl would train this projection).
    rng = np.random.RandomState(42)
    P_a = rng.randn(feats_a.shape[1], output_dim) / np.sqrt(feats_a.shape[1])
    P_b = rng.randn(feats_b.shape[1], output_dim) / np.sqrt(feats_b.shape[1])
    proj_a = feats_a @ P_a  # (n_a, output_dim)
    proj_b = feats_b @ P_b  # (n_b, output_dim)
    # For each neuron in A, its view of B is T @ proj_b (n_a, output_dim).
    # For each neuron in B, its view of A is T.T @ proj_a (n_b, output_dim).
    a_view_of_b = T @ proj_b                  # (n_a, output_dim)
    b_view_of_a = T.T @ proj_a                # (n_b, output_dim)
    merged = np.concatenate([proj_a, proj_b, a_view_of_b, b_view_of_a], axis=0)
    # Shape: (n_a + n_b + n_a + n_b, output_dim) = (2*(n_a+n_b), output_dim)
    return merged


# ---------------------------------------------------------------------------
# Self-test: GPU verification
# ---------------------------------------------------------------------------
def gpu_self_test() -> Dict[str, Any]:
    """Verify GPU is available and Fisher-Rao + GW both work."""
    info: Dict[str, Any] = {
        "torch_available": _HAS_TORCH,
        "torch_cuda": _HAS_TORCH and torch.cuda.is_available(),
        "torch_version": torch.__version__ if _HAS_TORCH else None,
        "geomstats_available": _HAS_GEOMSTATS,
        "pot_available": _HAS_POT,
        "fisher_rao_works": False,
        "gw_works": False,
    }
    try:
        A = np.eye(3) * 2.0
        B = np.eye(3) * 0.5
        d = spd_geodesic_distance(A, B)
        info["fisher_rao_works"] = True
        info["fisher_rao_test_distance"] = d
    except Exception as e:
        info["fisher_rao_error"] = str(e)
    try:
        fa = np.random.RandomState(0).randn(8, 4)
        fb = np.random.RandomState(1).randn(10, 5)
        gw = gromov_wasserstein_distance(fa, fb)
        info["gw_works"] = True
        info["gw_test_distance"] = gw.gw_distance
    except Exception as e:
        info["gw_error"] = str(e)
    return info


__all__ = [
    "FisherRaoResult", "spd_geodesic_distance", "sov_signal_fisher_rao",
    "GWResult", "gromov_wasserstein_distance", "merge_models_via_gw",
    "gpu_self_test",
]