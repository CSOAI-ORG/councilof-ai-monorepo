# csoai-fleet-manifest

The **canonical fleet + corpus + surface inventory**, loaded from `SOVEREIGN_MASTER_v2.json` and exposed as typed Python.

## What it ships

- `FleetManifest` — frozen dataclass holding the entire standing inventory
- `Benchmark`, `Claim`, `HoneyCorpus`, `Models`, `TrainingData`, `Surface` — typed row dataclasses
- `load_fleet_manifest()` — loads from repo root
- Helper properties: `benchmark_count`, `benchmark_live_count`, `retracted_claims`, `live_surfaces`

## Canonical numbers (the ones that drift every session — anchored here)

| Quantity | Value |
|---|---|
| ollama models | **90** |
| Honey corpus | **8,559** |
| Training samples | **12,193** |
| Training sources | 34 |
| GovBench items × dims × models | 193 × 26 × 10 |
| DefBench entrants | 4 |
| ProvBench survival | 0/160 (CI 13.9%) |
| CompBench tasks | 110 |
| Refutations | 4 (2 RETRACTED) |
| Owner-gated blockers | 6+ |

The drift-killer: every README, audit doc, and reproduce script pulls from this manifest instead of hardcoding its own count.

## Quick start

```python
from csoai_fleet_manifest import load_fleet_manifest
m = load_fleet_manifest()
print(m.models.total)            # 90
print(m.honey_corpus.total)      # 8559
print(m.benchmarks["govbench"].raw["items"])  # 193
print(m.live_surfaces)           # {"csoai_org": "csoai-org... (200)", ...}
print(m.retracted_claims)        # ["Quorum n_eff 1.21 (RETRACTED)", "Gate -20.00 n=6 (RETRACTED)"]
```

## Test status

21/21 tests (run on A100: `PYTHONPATH=SOVOS/packages/csoai-fleet-manifest/src /usr/bin/python3 -m pytest SOVOS/packages/csoai-fleet-manifest/tests/`).