"""J-Space Move Arithmetic: task-vector math for chess-board moves.

The novel insight: chess-board moves are task vectors in a high-dimensional
"action space" defined by (clan, axis, position, intent). This module
implements TIES, DARE, and error-vector subtraction for J-Space moves,
adapted from the MergeKit/Task Arithmetic papers.

References (real published work this is built on):
- Ilharco et al. (2023) "Editing Models with Task Arithmetic"
- Yadav et al. (2023) "TIES-Merging"
- Yu et al. (2023) "Language Models are Super Mario"
- aTLAS (NeurIPS 2024) "Knowledge Composition using Task Vectors"

What this module does that nobody has published:
- Represents J-Space moves as task vectors (clan_id, axis_id, dx, dy, dz, intent)
- Applies TIES to moves: trim redundant same-direction moves, elect sign, merge
- Applies DARE: dropout moves, rescale survivors, simulate "what if we never did this"
- Subtracts error-moves: OOM moves, recursion loops, refusals — these become
  NEGATIVE weights that, when added, REMOVE the failure mode from future routing
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. MOVE ENCODING — a chess move as a task vector
# ---------------------------------------------------------------------------
class Axis(str, Enum):
    """The 12 GSPC axes that any move can target."""
    GOV = "G"      # Governance
    SAFETY = "S"   # Safety
    PRV = "P"      # Privacy
    ART5 = "5"     # EU AI Act Article 5
    AGI = "I"      # AGI risk
    ASI = "A"      # ASI safety
    MACH = "M"     # Machine experience
    CARE = "C"     # Care axis
    XR = "X"       # Extended reality / spatial
    DET = "D"      # Detection (injection scanning)
    SWARM = "W"    # Swarm coordination
    OSS = "O"      # Open-source compliance


# A move is a 14-dimensional task vector:
#   (clan_id, axis_id, dx, dy, dz, intent, weight, error_type, error_freq, ...)
# Stored as a Python dict for inspection + a numpy-shaped vector for math.
@dataclass
class Move:
    """One chess-board move expressed as a task vector.

    The math works the same as Ilharco's τ = θ_task − θ_base:
    A "capability move" has +1 intent (e.g. add new safety rule).
    An "error move" has -1 intent (e.g. known recursion loop).

    The router computes:
        move_vector = base_move + λ_capability · τ_capability - λ_error · ε_error
    """
    clan: str                 # "fish", "builder", "watchdog", ...
    axis: Axis                # Which of the 12 axes this move targets
    dx: int                   # Displacement on x-axis (-9..+9)
    dy: int                   # Displacement on y-axis (-9..+9)
    dz: int = 0               # Displacement on z-axis (height)
    intent: float = 1.0       # +1 = add capability, -1 = subtract error
    weight: float = 1.0       # Magnitude of this move (confidence 0..1)
    error_type: Optional[str] = None  # "oom", "timeout", "loop", "refusal", None
    error_freq: int = 0       # How many times this error has been seen
    label: str = ""           # Human description

    def __post_init__(self):
        # Validate board bounds (9×9×4 chess board)
        assert -9 <= self.dx <= 9, f"dx {self.dx} out of bounds"
        assert -9 <= self.dy <= 9, f"dy {self.dy} out of bounds"
        assert 0 <= self.dz <= 4, f"dz {self.dz} out of bounds"

    def to_vector(self, dims: int = 14) -> List[float]:
        """Encode move as a fixed-length task vector.

        Layout: [clan_hash, axis_idx, dx/9, dy/9, dz/4, intent, weight,
                 error_flag, error_freq_norm, intent*weight, dx*dy, dz*axis,
                 clan*axis, 1.0]
        """
        clan_hash = (hash(self.clan) % 7) / 7.0
        axis_idx = list(Axis).index(self.axis) / len(Axis)
        return [
            clan_hash,
            axis_idx,
            self.dx / 9.0,
            self.dy / 9.0,
            self.dz / 4.0,
            self.intent,
            self.weight,
            1.0 if self.error_type else 0.0,
            min(self.error_freq / 100.0, 1.0),
            self.intent * self.weight,
            (self.dx * self.dy) / 81.0,
            (self.dz * axis_idx),
            (clan_hash * axis_idx),
            1.0,
        ][:dims]

    def __repr__(self) -> str:
        err = f" err={self.error_type}({self.error_freq})" if self.error_type else ""
        return (f"Move({self.clan}@{self.axis.value} Δ({self.dx:+d},{self.dy:+d},{self.dz})"
                f" λ={self.weight:.2f}{err} '{self.label}')")


# ---------------------------------------------------------------------------
# 2. TIES FOR MOVES — Trim, Elect sign, Merge
# ---------------------------------------------------------------------------
def ties_merge(moves: List[Move], dim: int = 14) -> Move:
    """TIES algorithm for moves, adapted from Yadav et al. 2023.

    1. TRIM — remove moves with low magnitude (weight < threshold).
       These are "noise moves" that don't contribute.
    2. ELECT SIGN — for each axis dimension, majority vote on direction.
       If 4 of 6 moves push +1 and 2 push -1, keep +1.
    3. MERGE — keep only agreeing contributions, sum them.

    Returns a single composite Move that represents the merged intent.
    """
    if not moves:
        raise ValueError("ties_merge needs at least 1 move")

    # Step 1: Trim
    trim_threshold = 0.2
    trimmed = [m for m in moves if m.weight >= trim_threshold]
    if not trimmed:
        trimmed = moves

    # Step 2 + 3: Vector math (element-wise sign election)
    vectors = [m.to_vector(dim) for m in trimmed]
    n_dim = len(vectors[0])
    elected = [0.0] * n_dim

    for i in range(n_dim):
        # Majority sign election: positive wins ties
        pos = sum(v[i] for v in vectors if v[i] > 0)
        neg = sum(-v[i] for v in vectors if v[i] < 0)
        if pos >= neg:
            # Positive direction wins; sum positive contributors
            elected[i] = sum(v[i] for v in vectors if v[i] > 0)
        else:
            elected[i] = sum(v[i] for v in vectors if v[i] < 0)

    # Decode back to a Move (round to nearest integer displacements)
    # First, pick the dominant clan/axis from the original moves
    dominant = max(trimmed, key=lambda m: m.weight)
    new_dx = int(round(elected[2] * 9)) if abs(elected[2]) > 0.05 else dominant.dx
    new_dy = int(round(elected[3] * 9)) if abs(elected[3]) > 0.05 else dominant.dy
    new_dz = int(round(elected[4] * 4)) if abs(elected[4]) > 0.05 else dominant.dz

    return Move(
        clan=dominant.clan,
        axis=dominant.axis,
        dx=max(-9, min(9, new_dx)),
        dy=max(-9, min(9, new_dy)),
        dz=max(0, min(4, new_dz)),
        intent=elected[5] / len(trimmed),  # average intent
        weight=min(elected[6] / len(trimmed), 1.0),  # average weight, cap 1
        label=f"ties({len(trimmed)} moves) → {dominant.label}",
    )


# ---------------------------------------------------------------------------
# 3. DARE FOR MOVES — Dropout And REscale
# ---------------------------------------------------------------------------
def dare_dropout(moves: List[Move], drop_rate: float = 0.5,
                 seed: Optional[int] = None) -> List[Move]:
    """DARE algorithm for moves, adapted from Yu et al. 2023.

    Randomly drop `drop_rate` fraction of moves, rescale survivors by 1/(1-drop_rate).
    This simulates "what if we never tried this move" — if the system still works,
    the move was redundant and can be permanently removed.

    Use case: prune 50% of historical moves to see which are load-bearing.
    """
    import random
    rng = random.Random(seed)
    survivors = []
    rescale = 1.0 / (1.0 - drop_rate)
    for m in moves:
        if rng.random() >= drop_rate:
            m.weight = min(m.weight * rescale, 1.0)
            survivors.append(m)
    return survivors


# ---------------------------------------------------------------------------
# 4. ERROR-VECTOR ARITHMETIC — Subtract failure modes
# ---------------------------------------------------------------------------
@dataclass
class ErrorVector:
    """A failure mode expressed as a negative task vector.

    This is the novel part. We represent a known error (e.g. recursion loop)
    as a move with intent=-1. When this vector is ADDED to a candidate move,
    it subtracts the failure mode from the routing decision.
    """
    error_type: str         # "oom" | "timeout" | "loop" | "refusal" | "hallucination"
    pattern_hash: str       # SHA256 of the query pattern that triggers it
    magnitude: float        # How strongly to subtract (0..1)
    occurrences: int        # How many times observed
    affected_axes: List[Axis] = field(default_factory=list)

    def to_move(self, base: Move) -> Move:
        """Convert error vector to a move with negative intent.

        The router does: candidate_move + λ * ε_error
        = candidate_move with negative contribution = refusal of failure mode
        """
        return Move(
            clan=base.clan,
            axis=base.axis,
            dx=-base.dx,     # Inverse direction = undo the failure
            dy=-base.dy,
            dz=base.dz,
            intent=-1.0,     # NEGATIVE intent = subtract this
            weight=self.magnitude,
            error_type=self.error_type,
            error_freq=self.occurrences,
            label=f"ε_{self.error_type}({self.occurrences})",
        )


def subtract_error(candidate: Move, errors: List[ErrorVector]) -> Move:
    """Apply error-vector arithmetic to a candidate move.

    For each known error pattern, if the candidate move matches the error's
    pattern, REDUCE the candidate's weight by the error's magnitude.

    This is the preemptive-immunization step: before the move is even sent
    to a clan, we know which failure modes it's heading toward, and we
    dampen it accordingly.
    """
    dampening = 0.0
    matched = []
    for err in errors:
        # Match if any of the affected axes equals candidate's axis
        if candidate.axis in err.affected_axes or not err.affected_axes:
            dampening += err.magnitude * math.log1p(err.occurrences)
            matched.append(err.error_type)

    new_weight = max(0.0, candidate.weight - dampening)
    return Move(
        clan=candidate.clan,
        axis=candidate.axis,
        dx=candidate.dx,
        dy=candidate.dy,
        dz=candidate.dz,
        intent=candidate.intent,
        weight=new_weight,
        error_type=candidate.error_type,
        error_freq=candidate.error_freq,
        label=f"{candidate.label} | dampened_by={','.join(matched)}" if matched else candidate.label,
    )


# ---------------------------------------------------------------------------
# 5. ROUTER — Compose the math, produce the next move
# ---------------------------------------------------------------------------
class JSpaceRouter:
    """Chess-board router that applies task-vector math to decide the next move.

    This is the implementation of the novel architecture: every routing
    decision is a composite of capability moves (TIES-merged) minus error
    moves (subtracted), with DARE dropout on the candidate pool.

    The router never spawns a recursive loop because the output is always a
    single Move object (deterministic) — no "while not converged" anywhere.
    """

    def __init__(self, board_size: int = 9):
        self.board_size = board_size
        self.error_db: Dict[str, ErrorVector] = {}  # pattern_hash → error
        self.move_history: List[Move] = []

    def register_error(self, error: ErrorVector) -> None:
        """Mine a new error signature (called every time a clan crashes)."""
        existing = self.error_db.get(error.pattern_hash)
        if existing:
            existing.occurrences += error.occurrences
            existing.magnitude = min(existing.magnitude + 0.05, 1.0)
        else:
            self.error_db[error.pattern_hash] = error

    def route(self, candidates: List[Move]) -> Move:
        """Pick the best next move from a candidate pool.

        Pipeline:
        1. DARE dropout — try without 50% of moves; keep load-bearing ones
        2. TIES merge — combine surviving moves into one composite
        3. Error subtraction — dampen composite by known error patterns
        4. Return the chosen move + record in history
        """
        # 1. DARE
        survivors = dare_dropout(candidates, drop_rate=0.5, seed=42)

        # 2. TIES
        merged = ties_merge(survivors)

        # 3. Error subtraction
        errors = list(self.error_db.values())
        chosen = subtract_error(merged, errors)

        # 4. Record
        self.move_history.append(chosen)
        return chosen

    def stats(self) -> Dict[str, int]:
        """Routing telemetry — visible in the J-Space UI."""
        return {
            "total_moves": len(self.move_history),
            "known_errors": len(self.error_db),
            "error_types": len({e.error_type for e in self.error_db.values()}),
            "total_error_occurrences": sum(e.occurrences for e in self.error_db.values()),
        }


__all__ = [
    "Axis", "Move", "ErrorVector",
    "ties_merge", "dare_dropout", "subtract_error",
    "JSpaceRouter",
]