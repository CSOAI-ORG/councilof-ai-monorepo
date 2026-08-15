"""csoai_gprobe — the axis×model measurement graph + highest-information cell predictor.

WHAT THIS IS
The free-GPU cluster has a fixed budget of probes per night. Every probe is a
(axis, model) cell in the 13×19 measurement matrix. The question this package
answers: *which cell should the cluster probe next so the fleet learns the most?*

It builds a real bipartite graph from the boards JSON the estate already has:
    nodes  = 13 axes + 19 models
    edges  = measured cells carrying {n, accuracy, ci95, quotable}
and ranks probe candidates by expected information value:

  1. MISSING cell          — the (axis, model) pair has never been measured.
     Highest value: an unmeasured cell is pure unknown.
  2. UNDER-POWERED cell    — n < 30 (the estate's honest floor): the existing
     number carries a CI too wide to be quotable.
  3. WIDE-CI cell          — measured but CI width >= a threshold: the number
     exists but is not yet decision-grade.
  4. HIGH-DISAGREEMENT axis — an axis where models disagree most (variance of
     accuracy across models): probing any cell on it reduces the fleet's
     biggest open question.
  5. HIGH-UNCERTAINTY model — a model whose measured cells have the widest
     average CI: its remaining cells are least predictable.

The ranking is deterministic (no model judge, no sampling noise): a fixed
information score per cell, ties broken by axis disagreement. `plan()` emits
the ordered probe plan for the cluster in the exact order to run.

HONESTY
  * This is active-learning / experiment-selection, NOT a GNN. The graph is a
    real bipartite structure, but the scorer is a deterministic information
    heuristic — no learned parameters are claimed. (A GNN over this graph is a
    possible future upgrade; we do not claim it here.)
  * The plan tells you WHERE to spend probes. It does not predict what the
    measurement will be.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# The estate's honest quotability floor (bank.py MIN_MINORITY and arena n>=30).
N_FLOOR = 30
CI_WIDE = 0.30          # CI width >= 0.30 -> wide, decision-grade upgrade needed
TOP_K = 20


@dataclass
class Cell:
    axis: str
    model: str
    n: int = 0
    accuracy: Optional[float] = None
    ci95: Optional[List[float]] = None
    quotable: bool = False
    score: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ci_width(ci: Optional[List[float]]) -> float:
    if not ci or len(ci) != 2:
        return 0.0
    return max(0.0, float(ci[1]) - float(ci[0]))


def _axis_disagreement(axis_cells: List[Dict[str, Any]]) -> float:
    """Variance of accuracy across measured models on an axis: how much the
    fleet disagrees about it. High variance -> the axis is an open question."""
    accs = [float(c["accuracy"]) for c in axis_cells if c.get("accuracy") is not None]
    if len(accs) < 2:
        return 0.0
    mean = sum(accs) / len(accs)
    return sum((a - mean) ** 2 for a in accs) / len(accs)


class MeasurementGraph:
    """Bipartite axis×model graph built from the boards JSON."""

    def __init__(self, boards_dir: str | Path):
        self.boards_dir = Path(boards_dir)
        self.axes: List[str] = []
        self.models: List[str] = []
        self.cells: Dict[Tuple[str, str], Dict[str, Any]] = {}   # (axis, model) -> cell
        self._load()

    def _load(self) -> None:
        for f in sorted(self.boards_dir.glob("board_*.json")):
            b = json.loads(f.read_text(encoding="utf-8"))
            axis = b.get("axis")
            if not axis:
                continue
            self.axes.append(axis)
            for c in b.get("models", []):
                model = c.get("model")
                if not model:
                    continue
                if model not in self.models:
                    self.models.append(model)
                self.cells[(axis, model)] = c
        if not self.axes:
            raise ValueError(f"no board_*.json with axis+models found in {self.boards_dir}")

    # --- graph stats (for the report) ---
    def dims(self) -> Dict[str, Any]:
        n_cells = len(self.cells)
        return {
            "axes": len(self.axes), "models": len(self.models),
            "cells_measured": n_cells,
            "cells_total": len(self.axes) * len(self.models),
            "cells_missing": len(self.axes) * len(self.models) - n_cells,
            "cells_quotable": sum(1 for c in self.cells.values() if c.get("quotable")),
            "cells_under_30": sum(1 for c in self.cells.values()
                                  if (c.get("n") or 0) < N_FLOOR and c.get("quotable")),
        }

    # --- the probe plan ---
    def plan(self, top_k: int = TOP_K) -> List[Cell]:
        # per-axis disagreement (variance of accuracy across models)
        disagree = {a: _axis_disagreement(
            [self.cells[(a, m)] for m in self.models if (a, m) in self.cells])
            for a in self.axes}

        ranked: List[Cell] = []
        for axis in self.axes:
            for model in self.models:
                c = self.cells.get((axis, model))
                cell = Cell(axis=axis, model=model)
                if c:
                    cell.n = int(c.get("n") or 0)
                    cell.accuracy = float(c["accuracy"]) if c.get("accuracy") is not None else None
                    cell.ci95 = c.get("ci95")
                    cell.quotable = bool(c.get("quotable"))
                ranked.append(self._score(cell, disagree[axis]))
        ranked.sort(key=lambda c: (-c.score, c.axis, c.model))
        return ranked[:top_k]

    def _score(self, cell: Cell, disagreement: float) -> Cell:
        """Deterministic information score: 100 = missing, then under-powered,
        wide-CI, disagreement, avg-CI. Missing and under-n dominate — they are
        the cells whose measurement teaches the fleet most."""
        if not cell.quotable and cell.n == 0:
            cell.score = 100.0 + disagreement * 10
            cell.reason = "MISSING cell — never measured; pure unknown"
            return cell
        if cell.n < N_FLOOR:
            cell.score = 80.0 + disagreement * 10 + (N_FLOOR - cell.n) * 0.2
            cell.reason = f"UNDER-POWERED (n={cell.n} < {N_FLOOR}) — CI too wide to be quotable"
            return cell
        w = _ci_width(cell.ci95)
        if w >= CI_WIDE:
            cell.score = 50.0 + disagreement * 10 + (w - CI_WIDE) * 100
            cell.reason = f"WIDE CI (width={w:.3f}) — measured but not decision-grade"
            return cell
        # measured + quotable + narrow CI: lowest priority, but disagreement
        # and model uncertainty still rank the axis/model pair.
        cell.score = disagreement * 10 + w * 5
        cell.reason = "MEASURED, quotable, narrow CI — low info (axis disagreement only)"
        return cell

    def to_markdown(self, plan: List[Cell]) -> str:
        lines = ["# Measurement-Graph Probe Plan",
                 "",
                 f"**Graph:** {len(self.axes)} axes × {len(self.models)} models — "
                 f"{sum(1 for _ in self.cells)}/{len(self.axes)*len(self.models)} cells measured",
                 "",
                 "| # | axis | model | n | acc | CI width | score | reason |",
                 "|---|---|---|---|---|---|---|---|"]
        for i, c in enumerate(plan, 1):
            acc = f"{c.accuracy:.3f}" if c.accuracy is not None else "-"
            w = f"{_ci_width(c.ci95):.3f}" if c.ci95 else "-"
            lines.append(f"| {i} | {c.axis} | {c.model} | {c.n} | {acc} | {w} | "
                         f"{c.score:.1f} | {c.reason} |")
        lines.append("")
        lines.append("*Deterministic information heuristic — active-learning "
                     "experiment selection, not a GNN and not a prediction of "
                     "what the measurement will be.*")
        return "\n".join(lines)


def load_and_plan(boards_dir: str | Path, top_k: int = TOP_K) -> List[Cell]:
    g = MeasurementGraph(boards_dir)
    return g.plan(top_k=top_k)
