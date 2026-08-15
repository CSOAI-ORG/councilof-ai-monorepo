"""csoai-families — the 4-split cells inside each OWEM family + GRPO rewards.

Re-exports the two top-level scripts that were absorbed into the
canonical monorepo:

- `family_cells.py` — the 4-split cell structure (left/right × small/big)
  inside each OWEM family.
- `sov_reward_functions.py` — GRPO reward functions for sovereign training
  (DeepSeek-R1 / HuggingFace TRL pattern).

Both scripts are preserved verbatim. Use them as module-level tools:

    from csoai_families.family_cells import run
    from csoai_families.sov_reward_functions import build_reward_fns
"""
from .family_cells import *  # noqa: F401,F403
from .sov_reward_functions import *  # noqa: F401,F403

__all__ = [
    "family_cells",
    "sov_reward_functions",
]
