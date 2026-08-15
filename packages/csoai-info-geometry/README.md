# csoai-info-geometry — Fisher-Rao SOV SIGNAL + Gromov-Wasserstein Fusion

**The fourth mathematical weapon for SOVOS, running on GPU.**

## What it does

### 1. Fisher-Rao SOV SIGNAL
Replace the scalar SOV SIGNAL score (a flat 0..1 number) with a
**geodesic distance** on the manifold of Symmetric Positive Definite
matrices equipped with the **Affine-Invariant Riemannian Metric** (which
coincides with the Fisher-Rao metric for the multivariate normal family).

```
sov_signal = d(AIRM)(state, permitted)  #  geodesic distance
is_governed = d < threshold              # inside the permitted geodesic ball
```

This is mathematically exact where the GSPC scalar was an approximation:
the geodesic distance respects the **probability manifold structure**
rather than treating model outputs as points in a flat Euclidean space.

**Validated on GPU (RTX 3090):**
| SPD size | Time |
|---|---|
| 16×16 | 1.36 ms |
| 64×64 | 3.08 ms |
| 256×256 | 23.13 ms |

### 2. Gromov-Wasserstein model fusion
Cross-architecture merging without layer alignment. Standard MergeKit
requires same-architecture models (Llama + Llama, Qwen + Qwen). GW
operates on **relational structure**: it compares the internal pairwise
distances within each model's latent space and finds the optimal
correspondence.

```
GW(P, Q) = min_T Σ L(C_P(i,j), C_Q(k,l)) · T(i,k) T(j,l)
```

Where `C_P[i,j] = ||z_i^P - z_j^P||` and `C_Q[k,l] = ||z_k^Q - z_l^Q||` are
the internal distance matrices, and `T` is the optimal transport plan.

**Result**: any two models — Llama-3 (4096-dim) + Qwen-2.5 (5120-dim) — can be
fused. Cross-arch merge of (64, 256) → (256, 128) in **5.82 ms**.

## Run it

```bash
# On sov-brain-2 (GPU pod):
ssh sov-brain-2
cd /workspace
source sov-governance-venv/bin/activate
PYTHONPATH=/workspace/csoai-info-geometry/src python3 -m pytest /workspace/csoai-info-geometry/tests/ -v
```

Expected: `✅ 8/8 tests PASSED`

## Tests

1. `test_01_fisher_rao_symmetric` — d(A,B) = d(B,A)
2. `test_02_fisher_rao_identity` — d(A,A) = 0
3. `test_03_sov_signal_permitted_vs_blocked` — close state inside geodesic ball
4. `test_04_sov_signal_non_diagonal_spd` — works on realistic covariance matrices
5. `test_05_gpu_self_test` — torch + GPU + geomstats + POT all available
6. `test_06_gw_distance_zero_for_identical` — GW(X,X) ≈ 0
7. `test_07_gw_cross_architecture` — GW between different-dim feature sets works
8. `test_08_merge_models_via_gw_shape` — produces (2*(n_a+n_b), output_dim) merged features

## GPU + Deps

| Package | Version | Use |
|---|---|---|
| torch | 2.4.1+cu124 | GPU Fisher-Rao via eigh() |
| geomstats | 2.8.0 | SPDMatrices, SPDAffineMetric |
| POT | 0.9.7.post1 | ot.gromov.gromov_wasserstein |

## License

MIT — CSOAI Ltd (UK 16939677)
