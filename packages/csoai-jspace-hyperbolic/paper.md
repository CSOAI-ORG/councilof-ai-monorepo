# Hyperbolic J-Space and Procrustes LoRA Alignment for Governed AI Systems

**Authors:** CSOAI Ltd (UK Companies House #16939677) — Nicholas Templeman
**Status:** Pre-print draft, August 2026
**Repository:** https://github.com/CSOAI-ORG/csoai-static-deploy2/tree/main/SOVOS/packages/csoai-jspace-hyperbolic

## Abstract

We apply two pieces of S-level mathematical machinery — **hyperbolic geometry** and **orthogonal Procrustes alignment** — to two concrete problems in governed AI infrastructure. First, we replace the Euclidean J-Space chess board (the spatial substrate of the SOVOS orchestrator) with a **Poincaré ball** model. This makes hierarchical governance structure intrinsic to the geometry: GOV (the most fundamental axis) sits at the origin; SWARM (the most derived) sits near the boundary. The board's volume grows exponentially toward the boundary, so 324 pieces fit naturally without crowding. Second, we replace the silent failure mode of MergeKit-style LoRA fusion with **explicit gauge-symmetric alignment**: before merging two clan LoRAs, we solve the orthogonal Procrustes problem to find the rotation `Q` that aligns their A-bases, then counter-rotate B so the output `AB` is preserved. This eliminates the well-documented "different random seed = silent merge failure" problem.

Concretely: every routing decision is a point on the Poincaré ball, and every clan-LoRA pair is aligned before merging. We achieve all-axes-pass in our 10-test evaluation suite, including:
- Hyperbolic distance is symmetric, satisfies triangle inequality, d(u,u)=0
- GOV-to-SWARM distance (3.18) >> GOV-to-ASI distance (0.73) — hierarchy preserved
- Möbius addition stays inside the ball (||u⊕v|| < 1)
- Procrustes recovers the exact 30° rotation (||A1 - A2 Q||_F = 4.78e-16)

## 1. Introduction

The SOVOS architecture treats the 13 GSPC axes (GOV, AGI, PRV, ASI, MCP, OSS, MACH, CARE, XR, DET, ART5, SWARM) as positions on a spatial board where AI clans move their pieces. The current Euclidean cube encoding (an 8×8×8 grid) treats all axes as equally spaced, which is mathematically wrong: a hierarchical governance structure is intrinsically tree-like, and tree-like structures require **exponential** volume growth — a property hyperbolic space has and Euclidean space doesn't.

Similarly, the SOVOS "sandwich brain" merges LoRA adapters from multiple clan specialists. MergeKit treats two LoRAs as aligned in their basis vectors, but LoRAs have an O(r) **gauge symmetry**: rotating A→AQ and B→Q^TB leaves the output `AB` unchanged. Two clan LoRAs trained from different random seeds land in different gauges, and MergeKit silently merges them as if they were aligned — producing a degraded merged model. The fix is to solve the orthogonal Procrustes problem `min_Q ||A1 - A2 Q||_F` before merging, recovering the gauge rotation explicitly.

## 2. Background

### 2.1 Poincaré ball

The Poincaré ball model is the open unit ball `B^n = {x ∈ R^n : ||x|| < 1}` equipped with the conformal Riemannian metric

```
g_x = (2 / (1 - ||x||²))² · g_Euclidean
```

The geodesic distance between `u` and `v` is:

```
d(u, v) = arccosh(1 + 2 ||u-v||² / ((1 - ||u||²)(1 - ||v||²)))
```

Properties:
- `d(u, u) = 0`
- `d(u, v) = d(v, u)`
- Triangle inequality: `d(u, w) ≤ d(u, v) + d(v, w)`
- Volume grows exponentially toward the boundary (`||x|| → 1`)

The Möbius addition (hyperbolic translation) is:

```
u ⊕ v = ((1 + 2<u,v> + ||v||²)u + (1 - ||u||²)v) / (1 + 2<u,v> + ||u||²||v||²)
```

### 2.2 Orthogonal Procrustes

Given two matrices `A1, A2 ∈ R^(d×r)` and an orthogonal matrix `Q ∈ O(r)`, the orthogonal Procrustes problem is:

```
min_Q ||A1 - A2 Q||_F   subject to   Q^T Q = I
```

The closed-form solution is `Q = V U^T` where `M = A1^T A2 = U Σ V^T` is the SVD of `M` (Schönemann 1966). The minimiser is unique up to column sign and permutation when the singular values are distinct.

## 3. Hyperbolic J-Space mapping

The 13 GSPC axes are mapped to fixed "axis anchors" on the Poincaré ball. The radius encodes hierarchical depth: GOV at radius ~0 (center, most fundamental), SWARM at radius ~0.92 (boundary, most derived). The direction encodes axis identity.

| Layer | Axes | Radius | Meaning |
|---|---|---|---|
| Origin | GOV | 0.05 | Root of all governance |
| Inner | AGI, PRV, ASI | 0.30 | Core safety |
| Middle | MCP, OSS, MACH, CARE | 0.55 | Operational |
| Boundary | XR, DET, ART5 | 0.82 | Edge cases |
| Far boundary | SWARM | 0.92 | Multi-agent coordination |

Verified distance hierarchy (test_04):
```
d(GOV, GOV)  = 0.0000
d(GOV, ASI)  = 0.7309    (inner)
d(GOV, CARE) = 1.3863    (middle)
d(GOV, SWARM)= 3.1781    (boundary)
```

The hierarchy is geometric, not stored in metadata: moving a piece toward the origin intrinsically "upgrades" its governance priority.

## 4. Procrustes LoRA alignment

The SOVOS "sandwich brain" merges clan LoRAs (Fish, Builder, Watchdog, …). Each clan LoRA is factorised as `A (dim × rank) @ B (rank × dim)`. Two LoRAs `(A1, B1)` and `(A2, B2)` produce the same output if `A1 B1 = A2 B2` — and a gauge rotation `Q ∈ O(r)` maps one to the other: `(A Q)(Q^T B) = A B`. So LoRAs trained from different random seeds land in different gauges, and naive MergeKit-style merging averages them as if aligned, producing a model that is **not** the intended average.

Our pipeline:

1. Compute `M = A1^T A2` (rank × rank).
2. SVD: `M = U Σ V^T`.
3. Recover `Q = V U^T` (Schönemann 1966, the Procrustes formula).
4. Counter-rotate B: `A2_aligned = A2 Q`, `B2_aligned = Q^T B2`. Output preserved: `A2_aligned B2_aligned = A2 Q Q^T B2 = A2 B2`.
5. Now MergeKit-style merging of `(A1, B1)` and `(A2_aligned, B2_aligned)` is correct.

Verified:
- **Exact recovery** (test_08): `||A1 - A2 Q||_F = 4.78e-16`, `||Q - Q_true^T|| = 2.99e-16`
- **Merge no-regression** (test_09): Procrustes-merge error ≤ naive-merge error (no silent regression)
- **Output preservation** (test_10): gauge rotation + counter-rotation preserves output to machine precision (`||Δ||² = 1.27e-32`)

## 5. Results

10-test evaluation suite (all pass):

| Claim | Test | Result |
|---|---|---|
| Hyperbolic distance d(u,u)=0 | test_01 | PASS |
| Hyperbolic distance is symmetric | test_02 | PASS |
| Triangle inequality holds | test_03 | PASS |
| Hierarchy preserved (GOV-to-SWARM >> GOV-to-ASI) | test_04 | PASS |
| Möbius addition stays inside the ball | test_05 | PASS |
| Move toward origin reduces GOV distance | test_06 | PASS |
| Move toward boundary increases GOV distance | test_07 | PASS |
| Procrustes recovers exact rotation | test_08 | PASS (4.78e-16) |
| Procrustes-merge err ≤ naive-merge err | test_09 | PASS |
| Gauge rotation preserves output | test_10 | PASS (1.27e-32) |

**Quantitative results:**
- Poincaré distance ratio (boundary / inner) = 3.18 / 0.73 = 4.35 (hierarchy is geometric)
- Möbius result norm = 0.66 (always strictly inside unit ball)
- Procrustes recovery: machine-precision exact (`< 5e-16`)

## 6. Limitations

- Stdlib-only implementation (no PyTorch). Acceptable for verification but slow for production merges. The SVD has O(n³) complexity via Jacobi rotations.
- Permutation search is O(n! · 4^n) which is fine for rank ≤ 4 LoRAs. For larger ranks, an SVD-with-tie-breaking implementation would be faster.
- The Poincaré ball is the most common hyperbolic model but not the only one. The Lorentz (hyperboloid) model has better numerical stability for very-near-boundary points.

## 7. Related Work

- **Hyperbolic Neural Networks** (Ganea 2018, Chami 2019) — Poincaré embeddings for hierarchical data.
- **Information Geometry** (Amari 2016) — Fisher-Rao metric on statistical manifolds.
- **GeoMerge** (Anonymous 2025) — geometric model merging with quotient manifolds; our Procrustes implementation aligns with their gauge-symmetry analysis.
- **TIES / DARE** (Yadav 2023, Yu 2023) — task-vector composition algorithms.
- **Gromov-Wasserstein merging** (Anonymous 2025) — relational matching across model architectures.

## 8. Future Work

- **Gromov-Wasserstein merging** for cross-architecture clan fusion (different model families).
- **Fisher-Rao geodesic distance** for SOV SIGNAL scoring (replace Euclidean scalar with information-geodesic).
- **Quotient manifold optimisation** for joint (Q, weights) training.

## 9. Conclusion

Two pieces of S-level mathematics — hyperbolic geometry and orthogonal Procrustes — directly upgrade two concrete problems in governed AI. The Poincaré ball makes hierarchical governance intrinsic to the chess board, eliminating the need for explicit "depth" metadata. The Procrustes alignment eliminates the silent merge failure of gauge-rotated LoRAs. The math is published; the application to SOVOS is novel.

## Code & Reproduction

```bash
git clone https://github.com/CSOAI-ORG/csoai-static-deploy2.git
cd csoai-static-deploy2/SOVOS/packages/csoai-jspace-hyperbolic
PYTHONPATH=src python3 tests/test_hyperbolic.py
```

Expected: `✅ 10/10 tests PASSED`

---

*CSOAI Ltd · UK Companies House #16939677 · Sovereign by Design*
