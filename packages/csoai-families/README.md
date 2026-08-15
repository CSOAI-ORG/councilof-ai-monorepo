# csoai-families

The 4-split cell structure inside each OWEM family, plus the GRPO
reward functions for sovereign training.

Absorbed 2026-08-11:

| File | Originally at | LOC |
|---|---|---|
| `src/csoai_families/family_cells.py`           | `family_cells.py` (top-level)           | 230 |
| `src/csoai_families/sov_reward_functions.py`   | `sov_reward_functions.py` (top-level)   | 423 |

## Use

```python
from csoai_families import family_cells, sov_reward_functions
```

Or directly:

```python
from csoai_families.family_cells import main as run_family_cells
from csoai_families.sov_reward_functions import build_reward_fns
```

The original scripts run standalone too:

```bash
python3 SOVOS/packages/csoai-families/src/csoai_families/family_cells.py --help
```

## What's in here (per brief)

- `family_cells.py` — each OWEM family holds a 4-cell brain
  (left/right × small/big). Cells hold the per-family lineage weights.
- `sov_reward_functions.py` — GRPO reward functions (DeepSeek-R1 / HF
  TRL pattern) for: sovereign knowledge, BFT, SIGIL, care floor,
  reasoning (ARC/GSM8K/logic), and calibration.

These are *operational substrate tooling* — not the chain math (that
lives in `sovos-chain` + `sovos-fisher-rao` + `sovos-jspace-hyperbolic`).
They back the training pipeline and the Hive (the absorbed
`sovos-hive` Rust kernel talks to these via the runtime).
