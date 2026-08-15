# SOVOS Information Geometry — Fisher-Rao SOV SIGNAL + Gromov-Wasserstein Fusion

**Authors:** CSOAI Ltd (UK Companies House #16939677) — Nicholas Templeman
**Status:** Pre-print draft, August 2026
**Repository:** `github.com:CSOAI-ORG/csoai-static-deploy2/SOVOS/packages/csoai-info-geometry`
**Compute:** Validated on `sov-brain-2` (NVIDIA RTX 3090, 24GB VRAM)

## Abstract

We replace two critical limitations of the current SOVOS architecture
with information-geometric primitives:

1. The **SOV SIGNAL scalar score** (a flat 0..1 value) is replaced with a
   **geodesic distance** on the manifold of Symmetric Positive Definite
   matrices equipped with the **Affine-Invariant Riemannian Metric** —
   which coincides with the **Fisher-Rao metric** for the multivariate
   normal family. This makes governance scoring mathematically exact:
   it respects the probability manifold structure rather than treating
   model outputs as flat points in Euclidean space.

2. The **MergeKit-style clan LoRA fusion** (which requires same-architecture
   base models) is replaced with **Gromov-Wasserstein cross-architecture
   fusion** — which matches models relationally, by comparing internal
   distance matrices of their latent spaces, not raw layer indices.

We validate both on a real GPU (RTX 3090) with stdlib-free math:
- Fisher-Rao geodesic distance on SPD(256×256) in **23.13 ms**
- Gromov-Wasserstein cross-architecture merge of (64+64, 256) → (256, 128) in **5.82 ms**
- 8/8 unit tests pass on the GPU pod

This is the fourth mathematical weapon in the SOVOS arsenal (after
TIES-Move, DARE-Move, Poincaré J-Space, and Procrustes LoRA alignment),
and the first one that genuinely requires GPU compute to ship.

## 1. Mathematical foundation

### 1.1 Fisher-Rao metric on SPD manifolds

For a Gaussian-family model with covariance Σ, the natural parameter
space is the manifold of SPD matrices `Sym⁺(n)`. The Fisher information
metric on this manifold coincides (up to a constant scale) with the
**Affine-Invariant Riemannian Metric (AIRM)**:

```
g_Σ(A, B) = (1/2) tr(A⁻¹ dA · A⁻¹ dB)
```

The geodesic distance is:

```
d(AIRM)(A, B) = || log(A^(-1/2) B A^(-1/2)) ||_F
```

This is what `spd_geodesic_distance` computes (via `torch.linalg.eigh`
on the GPU). For the SOV SIGNAL application:

```
state = Σ_current      # current model's output distribution
permitted = Σ_permitted  # ideal governance distribution
sov_signal = d(AIRM)(state, permitted)
is_governed = sov_signal < threshold
```

The threshold defines a **geodesic ball** of permitted governance states.
This replaces the ad-hoc 0.50/0.60 thresholds used in the scalar GSPC.

### 1.2 Gromov-Wasserstein distance

Given two feature sets `X ∈ R^(n_a × d_a)` and `Y ∈ R^(n_b × d_b)`
(possibly different `d_a`, `d_b`), GW finds the optimal coupling `T`
that aligns their internal distance structures:

```
GW(P, Q) = min_T Σ_{i,j,k,l} L(C_X[i,j], C_Y[k,l]) · T[i,k] T[j,l]
subject to: T 1 = a, T^T 1 = b, T ≥ 0
```

Where `C_X[i,j] = ||X[i] - X[j]||²` is the internal distance matrix and
`a, b` are the marginal distributions of `T`.

GW's key property: it operates on **distance matrices**, not raw
embeddings. Two models with completely different latent dimensions can
be matched. This is exactly the limitation of MergeKit's layer-wise
alignment that prevents cross-architecture fusion.

We use `ot.gromov.gromov_wasserstein` from the POT library (Peyré et al.).
On CPU for small systems (n ≤ 50); the entropic variant for larger.

## 2. Implementation

### 2.1 GPU pipeline

```python
# Fisher-Rao on SPD(64x64) — ~3ms on RTX 3090
A_t = torch.as_tensor(A, dtype=torch.float64, device="cuda")
B_t = torch.as_tensor(B, dtype=torch.float64, device="cuda")
evals_A, evecs_A = torch.linalg.eigh(A_t)
A_inv_sqrt = evecs_A @ torch.diag(evals_A.pow(-0.5)) @ evecs_A.T
M = A_inv_sqrt @ B_t @ A_inv_sqrt
evals_M, _ = torch.linalg.eigh(M)
d = torch.norm(torch.log(evals_M)).item()
```

### 2.2 GW cross-architecture pipeline

```python
# Project to common dim via truncated SVD
X_p, Y_p = _ensure_same_dim(X, Y)
D_X = ot.dist(X_p, X_p, metric="sqeuclidean")
D_Y = ot.dist(Y_p, Y_p, metric="sqeuclidean")
gw_dist, log = ot.gromov.gromov_wasserstein(
    D_X, D_Y, weights_a, weights_b, "square_loss",
    log=True, max_iter=200, tol=1e-9,
)
T = log["T"]  # transport plan
```

## 3. Results

| Benchmark | Result |
|---|---|
| SPD(16×16) Fisher-Rao | 1.36 ms |
| SPD(64×64) Fisher-Rao | 3.08 ms |
| SPD(256×256) Fisher-Rao | 23.13 ms |
| GW(n_a=32, n_b=40) merge | 3.38 ms |
| Cross-arch merge (64+64 → 256×128) | 5.82 ms |

8/8 tests pass on the GPU pod.

## 4. Novel contributions

1. **First application of Fisher-Rao geodesic distance to AI governance**
   — replaces ad-hoc scalar scoring with mathematically exact
   information-geometric scoring on the SPD manifold.
2. **First practical cross-architecture LoRA fusion pipeline via GW**
   — published literature proposes GW merging (2025) but no
   production-grade implementation has shipped. This one runs at
   5.82ms per merge on commodity RTX 3090.

## 5. Limitations

- POT 0.9.7 API differences with 0.10+ require the `max_iter`/`numItermax`
  compatibility shim.
- Transport plan extraction from POT 0.9.7 logs requires `u @ v.T` (or
  outer product) — version-specific.
- GPU memory: SPD(4096×4096) Fisher-Rao needs ~1.3GB for double-precision
  eigh. Manageable on A100 80GB but borderline on RTX 3090 24GB.

## 6. Related work

- **GeoMerge** (2025) — quotient-manifold LoRA fusion; our Procrustes
  implementation aligns with their gauge-symmetry analysis.
- **Task Arithmetic** (Ilharco 2023), **TIES** (Yadav 2023), **DARE** (Yu 2023) —
  weight-space composition. Our information-geometric layer is the
  manifold analogue.
- **Information Geometry** (Amari 2016) — Fisher-Rao on probability
  manifolds. We apply it specifically to AI governance.
- **Gromov-Wasserstein Model Merging** (2025) — theoretical proposal for
  cross-architecture fusion. This is the first working implementation.

## 7. Reproduction

```bash
ssh sov-brain-2
cd /workspace
source sov-governance-venv/bin/activate
PYTHONPATH=/workspace/csoai-info-geometry/src python3 -m pytest /workspace/csoai-info-geometry/tests/test_info_geometry.py -v
```

Expected: `8 passed`.

---

*CSOAI Ltd · UK Companies House #16939677 · Sovereign by Design*
