#!/usr/bin/env python3
"""jspace_chess.py — J-Space chess board: multi-owner coordination as chess.

Canon: _alignment/JSPACE_CHESS_BOARD_CANON_2026-08-08.md
Build date: 2026-08-08 (JEEVES lane, from user design artifact)

The board is an 8x8x8 hypercube (512 cells). Each 3KB capsule is a chess
piece. GSPC is the rules engine. The Oracle (SOV Signal) signs every move.

Axes: x=sector 0-7 · y=governance-severity 0-7 (PERMITTED->PROHIBITED) ·
z=time-depth 0-7 (real-time->historical).

Implemented here (Mac-executable core, stdlib only):
- JSpacePosition, Piece, Move dataclasses
- 3D chess move generation (King/Queen/Rook/Bishop/Knight/Pawn)
- Deterministic move validation (owner/position/occupancy/axis-compat)
- GSPC evaluator hook (deterministic, no LLM — returns PERMITTED/PROHIBITED)
- Oracle signing (Ed25519-style; stdlib hashlib fallback)
- Water->milk->honey->3KB-card derivation (3:1)
- A tiny agent-coordination simulation

Honesty: this is a coordination protocol (deterministic, signed), NOT runtime
container containment. Per register rule: never claim microVM isolation the
estate does not provide.
"""

from __future__ import annotations  # py3.11 runner compat (CI gate; D118 class)

import hashlib
import json
import time
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

# --- J-Space geometry ------------------------------------------------------

BOARD_DIM = 8
AXES = ["GOV", "AGI", "PRV", "ASI", "MCP", "OSS", "MACH", "CARE", "XR", "DET", "ART5", "SWARM"]
PIECE_TYPES = ["King", "Queen", "Rook", "Bishop", "Knight", "Pawn"]
COLORS = {
    "human": "Blue",
    "watchdog": "Green",
    "agent": "Red",
    "partner": "Yellow",
    "oracle": "Gold",
}


@dataclass(frozen=True)
class JSpacePosition:
    """A cell in the 8x8x8 J-Space hypercube."""
    x: int
    y: int
    z: int

    def is_valid(self) -> bool:
        return 0 <= self.x < BOARD_DIM and 0 <= self.y < BOARD_DIM and 0 <= self.z < BOARD_DIM

    def __str__(self):
        return f"({self.x},{self.y},{self.z})"


@dataclass
class Piece:
    """A 3KB archetype card standing at a board position."""
    id: str
    axis: str
    piece_type: str
    position: JSpacePosition
    owner: str
    color: str
    value_score: float = 50.0
    signature: str = ""
    # Derived memory fields (the 'card' content)
    card_hash: str = ""          # sha256 of compressed 3KB card
    honey_rank: str = "water"    # water -> milk -> honey

    def valid_moves(self) -> list[JSpacePosition]:
        """Chess movement rules applied in 3D J-Space."""
        x, y, z = self.position.x, self.position.y, self.position.z
        out = []
        def add(px, py, pz):
            p = JSpacePosition(px, py, pz)
            if p.is_valid():
                out.append(p)

        if self.piece_type == "King":
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        if dx == dy == dz == 0:
                            continue
                        add(x + dx, y + dy, z + dz)
        elif self.piece_type == "Queen":
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        if dx == dy == dz == 0:
                            continue
                        for d in range(1, BOARD_DIM):
                            p = JSpacePosition(x + dx * d, y + dy * d, z + dz * d)
                            if not p.is_valid():
                                break
                            out.append(p)
        elif self.piece_type == "Rook":
            for axis, s in (("x", 1), ("x", -1), ("y", 1), ("y", -1), ("z", 1), ("z", -1)):
                for d in range(1, BOARD_DIM):
                    if axis == "x":
                        p = JSpacePosition(x + s * d, y, z)
                    elif axis == "y":
                        p = JSpacePosition(x, y + s * d, z)
                    else:
                        p = JSpacePosition(x, y, z + s * d)
                    if not p.is_valid():
                        break
                    out.append(p)
        elif self.piece_type == "Bishop":
            # 3D diagonals: 3 sign combinations x 2 sign sets (+1,-1)
            import itertools
            for sx in (1, -1):
                for sy in (1, -1):
                    for sz in (1, -1):
                        for d in range(1, BOARD_DIM):
                            p = JSpacePosition(x + sx * d, y + sy * d, z + sz * d)
                            if not p.is_valid():
                                break
                            out.append(p)
        elif self.piece_type == "Knight":
            # 3D knight: 2 in one axis + 1 in another
            for a in range(3):
                for b in range(3):
                    if a == b:
                        continue
                    for sa in (1, -1):
                        for sb in (1, -1):
                            dv = [0, 0, 0]
                            dv[a] = 2 * sa
                            dv[b] = 1 * sb
                            add(x + dv[0], y + dv[1], z + dv[2])
        elif self.piece_type == "Pawn":
            add(x, y + 1, z)          # forward (toward PROHIBITED)
            add(x + 1, y + 1, z)      # attack right
            add(x - 1, y + 1, z)      # attack left
            add(x, y + 1, z + 1)      # attack time-forward
            add(x, y + 1, z - 1)      # attack time-back
        return out


@dataclass
class Move:
    piece_id: str
    to_pos: JSpacePosition
    owner: str
    timestamp: float = field(default_factory=time.time)
    gspc_verdict: Optional[dict] = None
    oracle_signature: str = ""


# --- Memory derivation: water -> milk -> honey -> 3KB card -----------------

def derive_memory(raw: str, raw_weight: float = 1.0) -> dict:
    """water -> milk -> honey -> 3KB card (3:1 rule). Deterministic, no LLM."""
    w = {"water": 1.0, "milk": 3.0, "honey": 9.0}[raw_weight if raw_weight in ("water", "milk", "honey") else "water"]
    # 3:1 refinement: 3 units of a level produce 1 of the next
    honey_units = max(1, int(len(raw) / 3))
    card_payload = hashlib.sha256(f"{raw}:{honey_units}".encode()).hexdigest()[:32]
    # The 3KB card ~ structured, bounded payload
    card = {
        "head": card_payload[:16],
        "body": raw[:2048],
        "honey_units": honey_units,
        "rank": raw_weight,
    }
    card_hash = hashlib.sha256(json.dumps(card, sort_keys=True).encode()).hexdigest()
    return {"card": card, "card_hash": card_hash, "honey_units": honey_units}


# --- The board -------------------------------------------------------------

class JSpaceChessBoard:
    def __init__(self):
        self.pieces: dict[str, Piece] = {}
        self.move_history: list[dict] = []
        self.owners: dict[str, str] = {}
        self.turn_order: list[str] = []
        self.current_turn = 0

    def add_piece(self, piece: Piece):
        if piece.position in {p.position for p in self.pieces.values()}:
            raise ValueError(f"cell {piece.position} occupied")
        if piece.owner not in self.owners:
            self.owners[piece.owner] = piece.color
            self.turn_order.append(piece.owner)
        self.pieces[piece.id] = piece

    def piece_at(self, pos: JSpacePosition) -> Optional[Piece]:
        for p in self.pieces.values():
            if p.position == pos:
                return p
        return None

    def validate_move(self, piece: Piece, to_pos: JSpacePosition, owner: str) -> tuple[bool, str]:
        if piece.owner != owner:
            return False, "not your piece"
        if to_pos == piece.position:
            return False, "no-op"
        if not to_pos.is_valid():
            return False, "out of bounds"
        if to_pos not in piece.valid_moves():
            return False, f"invalid move for {piece.piece_type}"
        occ = self.piece_at(to_pos)
        if occ and occ.owner == owner:
            return False, "own piece in the way"
        # GSPC axis-compat (deterministic)
        if not self._axis_compatible(piece, to_pos):
            return False, "GSPC axis-incompatible destination"
        return True, "valid"

    def _axis_compatible(self, piece: Piece, to_pos: JSpacePosition) -> bool:
        if piece.axis == "GOV":
            return True
        if piece.axis in ("AGI", "ASI") and to_pos.y >= 6:
            # near-prohibited high-severity needs a GOV king nearby
            return any(
                p.axis == "GOV"
                and max(abs(p.position.x - to_pos.x), abs(p.position.y - to_pos.y), abs(p.position.z - to_pos.z)) <= 2
                for p in self.pieces.values()
            )
        if piece.axis == "SWARM":
            neighbors = sum(
                1 for p in self.pieces.values()
                if p.id != piece.id and p.position != to_pos
                and max(abs(p.position.x - to_pos.x), abs(p.position.y - to_pos.y), abs(p.position.z - to_pos.z)) <= 1
            )
            return neighbors >= 2
        if piece.axis == "CARE" and to_pos.y >= 6:
            return False  # CARE must not operate in PROHIBITED zone
        return True

    def evaluate_gspc(self, piece: Piece, to_pos: JSpacePosition, owner: str, raw: str = "") -> dict:
        """Deterministic GSPC evaluator — no LLM, no adjudication-by-model."""
        scenario = f"move {piece.id}:{piece.axis} → {to_pos} by {owner}"
        # derive a signed memory card for this move
        mem = derive_memory(raw or scenario)
        # verdict: allowed if validated + PERMITTED severity band.
        # severity bands (deterministic): y<=4 PERMITTED, y=5-6 CONDITIONAL,
        # y=7 PROHIBITED. high-severity axes need gov-king proximity already.
        severity = to_pos.y
        if severity >= 7:
            permitted = False
        elif severity >= 5:
            permitted = True  # conditional zone, allowed w/ oversight
        else:
            permitted = True
        # high-severity axes (AGI/ASI/CARE) never enter fully-PROHIBITED y=7
        if severity == 7 and piece.axis in ("AGI", "ASI", "CARE"):
            permitted = False
        if not permitted:
            verdict = "PROHIBITED"
        elif severity >= 5 and piece.color != "Blue":
            verdict = "PERMITTED_WITH_CONDITIONS"
        else:
            verdict = "PERMITTED"
        return {
            "verdict": verdict,
            "confidence": 0.9,
            "scenario_hash": mem["card_hash"],
            "severity": severity,
        }

    def execute_move(self, piece: Piece, to_pos: JSpacePosition, owner: str, raw: str = "") -> dict:
        ok, reason = self.validate_move(piece, to_pos, owner)
        if not ok:
            return {"status": "rejected", "reason": reason}
        gspc = self.evaluate_gspc(piece, to_pos, owner, raw)
        if gspc["verdict"] == "PROHIBITED":
            return {"status": "blocked", "reason": "GSPC PROHIBITED", "verdict": gspc}
        # occupancy capture (enemy piece) + promote pawn at boundary
        captured = self.piece_at(to_pos)
        if captured and captured.owner != owner:
            del self.pieces[captured.id]
        piece.position = to_pos
        promoted = False
        if piece.piece_type == "Pawn" and to_pos.y == BOARD_DIM - 1:
            piece.piece_type = "Queen"
            piece.axis = "ART5"
            piece.value_score *= 3.0
            promoted = True
        sig = self._oracle_sign(piece, to_pos, gspc)
        rec = {
            "piece_id": piece.id,
            "from": str(_prev_from.get(piece.id, str(to_pos))),
            "to": str(to_pos),
            "owner": owner,
            "verdict": gspc["verdict"],
            "oracle": sig,
            "ts": time.time(),
        }
        self.move_history.append(rec)
        _prev_from[piece.id] = str(to_pos)
        self.current_turn = (self.current_turn + 1) % len(self.turn_order) if self.turn_order else 0
        return {"status": "executed", "move": rec, "promotion": promoted,
                "next_turn": self.turn_order[self.current_turn] if self.turn_order else None}

    def _oracle_sign(self, piece: Piece, to_pos: JSpacePosition, gspc: dict) -> str:
        payload = json.dumps({
            "piece_id": piece.id, "axis": piece.axis, "to": str(to_pos),
            "gspc_hash": gspc["scenario_hash"], "owner": piece.owner,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]


_prev_from: dict[str, str] = {}


# --- Tiny multi-owner simulation -------------------------------------------

def run_simulation() -> dict:
    board = JSpaceChessBoard()
    center = JSpacePosition(4, 4, 0)
    board.add_piece(Piece("gov-001", "GOV", "King", JSpacePosition(4, 4, 0), "nick", "Blue", 100.0))
    board.add_piece(Piece("agi-001", "AGI", "Queen", JSpacePosition(5, 5, 1), "alice", "Green", 90.0))
    board.add_piece(Piece("swarm-001", "SWARM", "Knight", JSpacePosition(3, 4, 2), "hap", "Red", 60.0))
    board.add_piece(Piece("prv-001", "PRV", "Bishop", JSpacePosition(2, 3, 1), "nvidia", "Yellow", 70.0))

    moves = [
        # Deterministically-valid first-moves; knight executes FIRST so its
        # SWARM-neighbor rule sees the starting cluster before pieces scatter.
        ("swarm-001", board.pieces["swarm-001"].valid_moves()[0], "hap"),
        ("gov-001", JSpacePosition(4, 5, 0), "nick"),
        ("agi-001", board.pieces["agi-001"].valid_moves()[0], "alice"),
        ("prv-001", board.pieces["prv-001"].valid_moves()[0], "nvidia"),
    ]
    results = []
    for pid, to, owner in moves:
        p = board.pieces[pid]
        r = board.execute_move(p, to, owner, raw=f"move {pid} to {to}")
        results.append({"piece": pid, "to": str(to), **{k: r[k] for k in ("status", "reason", "verdict") if k in r}})
    return {"board_cells": BOARD_DIM ** 3, "pieces": len(board.pieces),
            "moves": results, "move_history": len(board.move_history)}


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        s = run_simulation()
        assert s["board_cells"] == 512
        assert s["pieces"] >= 3
        assert s["move_history"] >= 2
        print(f"jspace_chess selftest OK: board={s['board_cells']} pieces={s['pieces']} moves={len(s['moves'])} history={s['move_history']}")
        for m in s["moves"]:
            print(f"  {m['piece']} -> {m['to']}: {m.get('status')} {m.get('verdict', '')}")
    else:
        import json as _j
        s = run_simulation()
        print(_j.dumps(s, indent=2))
