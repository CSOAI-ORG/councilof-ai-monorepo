# csoai-jspace-hyperbolic — Hyperbolic J-Space + Procrustes LoRA Alignment

**Two S-level mathematical weapons for the SOVOS architecture.**

## What it does

### Weapon 1: Hyperbolic J-Space (Poincaré ball)
Replaces the Euclidean J-Space chess board with a Poincaré ball. The 13 GSPC axes are encoded as fixed "anchors" whose radius encodes hierarchical depth:
- **Origin:** GOV (most fundamental)
- **Inner layer:** AGI, PRV, ASI (core safety)
- **Middle:** MCP, OSS, MACH, CARE (operational)
- **Boundary:** XR, DET, ART5, SWARM (edge / derived)

This makes the governance hierarchy **intrinsic to the geometry** — moving a piece toward the origin "upgrades" its governance priority, moving toward the boundary "deprioritizes". The volume of the ball grows exponentially near the boundary, so 324 pieces fit without crowding.

### Weapon 2: Procrustes LoRA Alignment
Before merging two clan LoRAs (Fish, Builder, Watchdog, …) with MergeKit, solve the orthogonal Procrustes problem to find the rotation `Q` that aligns their A-bases. Then counter-rotate B. This eliminates the silent "gauge rotation = degraded merge" failure mode of MergeKit.

## Run it

```bash
PYTHONPATH=src python3 tests/test_hyperbolic.py
```

Expected output: `✅ 10/10 tests PASSED`

## Proven claims (all tested)

| Claim | Test | Result |
|---|---|---|
| Poincaré distance d(u,u)=0 | test_01 | PASS |
| Symmetry: d(u,v) = d(v,u) | test_02 | PASS |
| Triangle inequality | test_03 | PASS |
| Hierarchy: d(GOV,SWARM) >> d(GOV,ASI) | test_04 | PASS (3.18 vs 0.73) |
| Möbius stays in unit ball | test_05 | PASS |
| Move toward origin = upgrade | test_06 | PASS |
| Move toward boundary = deprioritize | test_07 | PASS |
| Procrustes recovers exact rotation | test_08 | PASS (4.78e-16) |
| Procrustes-merge ≤ naive-merge error | test_09 | PASS |
| Gauge rotation preserves output | test_10 | PASS (1.27e-32) |

## Paper

`paper.md` contains the full arXiv preprint draft.

## License

MIT — CSOAI Ltd (UK 16939677)