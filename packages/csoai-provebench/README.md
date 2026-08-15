# csoai-provebench

The bench suite that measures SOVOS substrate against external
benchmarks on a per-axis basis. Brought together from
`kaggle/gspc_axes/` (Kaggle-targeted task cards) plus the top-level
`provbench_*.py` scripts into one canonical package.

## Provenance

Absorbed 2026-08-11:

| File | Originally at |
|---|---|
| `govbench_task.py`           | `kaggle/gspc_axes/govbench_task.py`           |
| `provbench_task.py`         | `kaggle/gspc_axes/provbench_task.py`         |
| `ossbench_task.py`          | `kaggle/gspc_axes/ossbench_task.py`          |
| `mcpbench_task.py`          | `kaggle/gspc_axes/mcpbench_task.py`          |
| `defbench_task.py`          | `kaggle/gspc_axes/defbench_task.py`          |
| `pqcbench_task.py`          | `kaggle/gspc_axes/pqcbench_task.py`          |
| `provbench_15asset_rerun.py` | `provbench_15asset_rerun.py` (top-level)      |
| `provbench_canonical_bound.py` | `provbench_canonical_bound.py` (top-level)   |

## Files

| File | Purpose |
|---|---|
| `govbench_task.py`         | Governance benchmark task — measure policy knowledge of a target system |
| `provbench_task.py`        | Provenance benchmark task — measure C2PA / provenance behaviour |
| `ossbench_task.py`         | Open-source-software benchmark — measure OSS-licensing awareness |
| `mcpbench_task.py`         | MCP-defence benchmark — measure injection defence |
| `defbench_task.py`         | Defence benchmark task (cross-cuts the SOV bundle) |
| `pqcbench_task.py`         | Post-quantum-crypto benchmark task |
| `provbench_15asset_rerun.py` | Script that measures the system against a 15-asset benchmark set |
| `provbench_canonical_bound.py` | Script that sets the canonical accuracy bound for provbench |

All files preserve their byte-content — copied line-for-line from
the original locations.

## Run

The bench tasks are intended to be invoked from a Kaggle kernel or
from the substrate's verification script. Use either pattern:

```python
import sys; sys.path.insert(0, "SOVOS/packages/csoai-provebench")
import govbench_task
import provbench_task
# ...
```

Or run the scripts standalone:

```bash
python3 SOVOS/packages/csoai-provebench/provbench_15asset_rerun.py
```

## Dependencies

These scripts were originally Kaggle-notebook-bound. **All 6 task
cards import `kaggle_benchmarks`** — a Kaggle-platform-provided
module that ships only inside Kaggle notebooks. As a consequence:

| Where | What works |
|---|---|
| Inside a Kaggle notebook (kaggle.com/code or kaggle.com/notebooks)  | All 6 cards import cleanly; bench runs operate against real Kaggle datasets |
| Off Kaggle (Mac, RunPod, Vercel, etc.)                          | All 6 cards require a `kaggle_benchmarks` stub to import; for real bench numbers, run on Kaggle |

The two top-level `provbench_*.py` scripts (`provbench_15asset_rerun.py`,
`provbench_canonical_bound.py`) **do not** import `kaggle_benchmarks`
— they read prior bench output from disk and recompute. They work
off-Kaggle as long as the output JSON from a prior Kaggle run is on
disk.

This package is therefore **two-faced**: the `provbench_*.py` scripts
are run-anywhere tools; the 6 task cards are Kaggle-bound instruments
preserved verbatim for historical + reproducibility reasons. None of
the provebench bench tasks are required for any other SOVOS package —
the live measurement surface is `sovos-arena`, which uses its own
probe bank (`GSPC_AXES`, `PROBE_BANK`).

## Cross-link

These task cards are the **input** to `sovos-arena`. The arena runs
each probe-bank through a target system and produces the Wilson-CI
per-axis profile; this package supplies the probes + scorers for
the canonical bench suite.
