"""sovos-core/data/milk.py — Task vectors + OWEM hive transforms.

MilkProcessor reads "water" StateVectors from the bus and produces
"milk" StateVectors: refined task vectors suitable for downstream
routing and decision-making.

The OWEM hive transform supports 6 projection modes (frozen/fluid ×
left/right × small/big) — the canonical OWEM axes:
- frozen: deterministic (no learning)
- fluid:   adaptive (parameters updated per call)
- left:    compress (project to lower dim)
- right:   expand (project to higher dim)
- small:   local (single vector)
- big:     global (aggregated over many vectors)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .state import StateBus, StateVector


class HiveMode(str, Enum):
    FROZEN = "frozen"
    FLUID = "fluid"


class HiveAxis(str, Enum):
    LEFT = "left"   # compress
    RIGHT = "right" # expand
    SMALL = "small" # local
    BIG = "big"     # global


def _l2(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _normalize(v: List[float]) -> List[float]:
    n = _l2(v)
    if n < 1e-12:
        return v
    return [x / n for x in v]


def _pad(v: List[float], target_dim: int) -> List[float]:
    if len(v) >= target_dim:
        return v[:target_dim]
    return v + [0.0] * (target_dim - len(v))


@dataclass
class HiveConfig:
    """The 6-axis hive transform."""
    mode: HiveMode = HiveMode.FROZEN
    axis: HiveAxis = HiveAxis.LEFT   # compress by default
    target_dim: int = 8             # output dimension


class MilkProcessor:
    """Reads water, produces milk (task vectors via hive transform)."""
    def __init__(self, bus: StateBus, config: Optional[HiveConfig] = None):
        self.bus = bus
        self.config = config or HiveConfig()
        # FLUID-mode state: per-axis running statistics for big-mode
        self._running_mean: Optional[List[float]] = None

    def process_all_water(self) -> List[str]:
        """Process every water vector on the bus. Returns list of sv_ids."""
        ids = []
        for w in self.bus.read_by_layer("water"):
            ids.append(self.process(w))
        return ids

    def process(self, water_sv: StateVector) -> str:
        """One water → one milk."""
        v = water_sv.vector
        cfg = self.config
        if cfg.axis == HiveAxis.LEFT:
            new_v = self._left(v, cfg.target_dim)
        elif cfg.axis == HiveAxis.RIGHT:
            new_v = self._right(v, cfg.target_dim)
        elif cfg.axis == HiveAxis.SMALL:
            new_v = self._small(v)
        elif cfg.axis == HiveAxis.BIG:
            new_v = self._big(v)
        else:
            new_v = v
        if cfg.mode == HiveMode.FLUID:
            # Fluid mode: running mean update (cheap online learning)
            if self._running_mean is None:
                self._running_mean = list(new_v)
            else:
                n = len(new_v)
                while len(self._running_mean) < n:
                    self._running_mean.append(0.0)
                for i in range(n):
                    self._running_mean[i] = 0.9 * self._running_mean[i] + 0.1 * new_v[i]
                new_v = list(self._running_mean)
        sv = StateVector(
            source=water_sv.source,
            layer="milk",
            vector=new_v,
            payload={
                "hive_mode": cfg.mode.value,
                "hive_axis": cfg.axis.value,
                "from_sv": water_sv.sv_id,
            },
        )
        return self.bus.append(sv)

    def _left(self, v: List[float], target_dim: int) -> List[float]:
        """Compress: project to target_dim. Real impl: PCA / learned."""
        return _normalize(_pad(v, target_dim))[:target_dim]

    def _right(self, v: List[float], target_dim: int) -> List[float]:
        """Expand: zero-pad + scale up to target_dim."""
        return _normalize(_pad(v, target_dim))

    def _small(self, v: List[float]) -> List[float]:
        """Local: just normalise, keep shape."""
        return _normalize(v)

    def _big(self, v: List[float]) -> List[float]:
        """Global: average with running mean (or just normalise if first call)."""
        if self._running_mean is None:
            self._running_mean = list(v)
        else:
            n = max(len(v), len(self._running_mean))
            while len(self._running_mean) < n:
                self._running_mean.append(0.0)
            v_p = _pad(v, n)
            for i in range(n):
                self._running_mean[i] = 0.9 * self._running_mean[i] + 0.1 * v_p[i]
        return list(self._running_mean)


__all__ = ["HiveMode", "HiveAxis", "HiveConfig", "MilkProcessor"]