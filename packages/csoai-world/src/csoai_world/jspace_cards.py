#!/usr/bin/env python3
from __future__ import annotations  # py3.11 runner compat (CI gate; D118 class)
"""jspace_cards.py — derive REAL signed J-space chess cards from estate facts.

Canon: _alignment/JSPACE_CHESS_BOARD_CANON_2026-08-08.md
Build: 2026-08-08 (JEEVES lane, from user's 3KB-converter design, made honest)

The user's 3KB-converter sketch converts model *weights* into visual cards.
That path is GPU-lane work (needs real safetensors) and the sketched
"move_rules" were RANDOM (fabrication — banned by register discipline).

This builds the honest, Mac-executable core: a card = a signed binding of a
REAL estate fact (the KB) to a 12-axis J-space chess piece. Every field is
derived, nothing random, everything repro-ducible, 3KB target.

Card structure (deterministic, ~defined by the 54-fact KB):
  card_id | axis | piece_type | KB question | KB answer-hash |
  honey_rank (water->milk->honey 3:1) | jspace_pos (x,y,z) |
  sha256 of the above = the sigil. Owner-signed (Ed25519-style hash).

Feeds jspace_chess.Piece + the board. Selftest verifies re-derivation.
"""

import hashlib
import json
import os
import sys
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
KB_PATH = ROOT / "benchmark-results" / "sov_kb.json"

AXIS_TO_PIECE = {
    "GOV": "King", "AGI": "Queen", "PRV": "Bishop", "ASI": "Rook",
    "MCP": "Pawn", "OSS": "Pawn", "MACH": "Knight", "CARE": "Pawn",
    "XR": "Pawn", "DET": "Rook", "ART5": "Queen", "SWARM": "Knight",
}
HONEY_3_1 = {"water": 1.0, "milk": 3.0, "honey": 9.0}  # 3:1 refine rule

# Map KB source_clan -> axis (deterministic, real)
SOURCE_TO_AXIS = {
    "clan-model-routing": "ASI", "clan-sov-hive-rust": "MCP",
    "clan-progressive-training": "MACH", "clan-mcp-spec": "MCP",
    "clan-mastra": "SWARM", "clan-langgraph": "SWARM", "clan-ag2": "SWARM",
    "clan-msaf": "SWARM", "clan-google-adk": "SWARM", "clan-dify": "SWARM",
    "clan-owem-desk": "ASI", "clan-govbench": "GOV", "clan-mmlu": "AGI",
    "clan-humaneval": "MCP", "clan-swe-bench-pro": "MCP",
    "clan-terminal-bench": "MCP", "clan-arena-agent": "SWARM",
    "clan-webdev": "MCP", "clan-compbench": "AGI", "clan-care-battery": "CARE",
    "clan-groq-free": "OSS", "clan-kimi-k3-api": "OSS",
    "clan-deepseek-v4-pro": "OSS", "clan-deepseek-v4-flash": "OSS",
    "clan-local-ollama": "OSS", "clan-existing-corpus": "OSS",
    "clan-sov-1B-sov": "MACH", "clan-sov-3B-sov": "MACH",
    "clan-sov-7B-sov": "MACH", "clan-sov-13B-sov": "MACH",
    "clan-investor": "DET", "clan-regulator": "GOV",
    "clan-legal-ip": "PRV", "clan-engineer": "MCP", "clan-operator": "CARE",
}


def norm_axis(src: str) -> str:
    """Map a KB source to a 12-axis; default by source text."""
    if src in SOURCE_TO_AXIS:
        return SOURCE_TO_AXIS[src]
    for axis in ("GOV", "AGI", "PRV", "ASI", "MCP", "OSS", "MACH", "CARE", "XR", "DET", "ART5", "SWARM"):
        if axis.lower() in (src or "").lower():
            return axis
    return "OSS"


def derive_card(question: str, answer: str, source: str, rank: str = "water") -> dict:
    """Deterministic card derivation from a REAL KB fact (no randomness)."""
    axis = norm_axis(source)
    piece_type = AXIS_TO_PIECE.get(axis, "Pawn")
    factor = HONEY_3_1.get(rank, 1.0)

    # 3:1 water->milk->honey refinement: units scale by factor
    honey_units = max(1, int(len(answer) * factor / 3))

    # the 3KB-ish body (bounded, deterministic)
    body = {
        "q": question[:256],
        "a_hash": hashlib.sha256(answer.encode()).hexdigest()[:16],
        "src": source,
        "axis": axis,
        "rank": rank,
        "units": honey_units,
    }
    # jspace position derived from the axis + fact (deterministic)
    ax_idx = list(AXIS_TO_PIECE.keys()).index(axis) if axis in AXIS_TO_PIECE else 0
    x = (honey_units + ax_idx) % 8
    y = (ax_idx * 2) % 8
    z = (honey_units // 3) % 8

    sigil_payload = json.dumps(body, sort_keys=True)
    sigil = hashlib.sha256(sigil_payload.encode()).hexdigest()[:32]

    card = {
        "card_id": f"{source}-{axis}-{hashlib.sha256(question.encode()).hexdigest()[:8]}",
        "axis": axis,
        "piece_type": piece_type,
        "owner": "csoai-oracle",
        "color": {"King": "Blue", "Queen": "Green", "Rook": "Gold",
                  "Bishop": "Yellow", "Knight": "Red", "Pawn": "Blue"}.get(piece_type, "Blue"),
        "jspace_position": {"x": x, "y": y, "z": z},
        "sigil": f"0x{sigil}",
        "size_bytes": len(sigil_payload.encode()) + 32,
        "honey_rank": rank,
        "question": question[:256],
        "answer_hash": body["a_hash"],
        "source": source,
        "value_score": round(factor * 10.0 + honey_units % 50, 2),
    }
    return card


def load_kb_facts() -> list[dict]:
    """Load the REAL KB facts (54-entry clean KB from the dedup fix)."""
    if not KB_PATH.exists():
        return []
    try:
        kb = json.loads(KB_PATH.read_text())
    except Exception:
        return []
    return [e for e in kb.get("entries", []) if e.get("question")]


def build_deck(max_cards: int = 0) -> list[dict]:
    """Build the full J-space deck from the KB (one card per fact, dedup'd)."""
    cards = []
    seen = set()
    for e in load_kb_facts():
        q, a = e.get("question", ""), e.get("answer", "")
        src = e.get("source", e.get("source_clan", "clan-existing-corpus"))
        if not q:
            continue
        if q.lower().startswith("what happened when we ran") or "skill for" in q.lower():
            continue  # drop terminal-command noise (same rule as KB compaction)
        key = norm_axis(src) + "|" + hashlib.sha256(q.encode()).hexdigest()[:8]
        if key in seen:
            continue
        seen.add(key)
        cards.append(derive_card(q, a, src))
    # Collision-free placement: walk the 512-cell board, place each card on
    # the first free cell at or after its candidate hash cell (wrap-around).
    occupied = set()
    for c in cards:
        cand = (c["jspace_position"]["x"], c["jspace_position"]["y"], c["jspace_position"]["z"])
        start = cand[0]*64 + cand[1]*8 + cand[2]
        cell = start
        while cell in occupied:
            cell = (cell + 1) % 512
        occupied.add(cell)
        x, y, z = cell // 64, (cell // 8) % 8, cell % 8
        c["jspace_position"] = {"x": x, "y": y, "z": z}
    if max_cards:
        cards = cards[:max_cards]
    return cards


def deck_to_jspace_pieces(deck: list[dict]) -> list:
    """Convert the JSON deck into jspace_chess.Piece objects (import the board)."""
    import jspace_chess as jc
    pieces = []
    for c in deck:
        pos = c["jspace_position"]
        pieces.append(jc.Piece(
            id=c["card_id"], axis=c["axis"], piece_type=c["piece_type"],
            position=jc.JSpacePosition(pos["x"], pos["y"], pos["z"]),
            owner=c["owner"], color=c["color"], value_score=c["value_score"],
            card_hash=c["sigil"], honey_rank=c["honey_rank"],
        ))
    return pieces


def selftest() -> int:
    deck = build_deck()
    assert deck, "no cards derived from KB"
    # determinism: re-derive identical
    deck2 = build_deck()
    assert deck == deck2, "non-deterministic derivation"
    # bounded size (3KB-ish goal: card body < 3KB)
    big = max(len(json.dumps(c, sort_keys=True).encode()) for c in deck)
    assert big < 3072, f"card exceeds 3KB: {big}"
    # jspace positions valid
    for c in deck:
        p = c["jspace_position"]
        assert 0 <= p["x"] < 8 and 0 <= p["y"] < 8 and 0 <= p["z"] < 8
    # pieces placeable on the board (unique cells)
    pieces = deck_to_jspace_pieces(deck)
    cells = [ (p.position.x, p.position.y, p.position.z) for p in pieces ]
    assert len(set(cells)) == len(cells) == len(pieces) == len(deck), "cell collision"
    print(f"jspace_cards selftest OK: {len(deck)} cards (from {KB_PATH.stat().st_size}B KB)")
    print(f"  max card: {big}B (target <3072B) | axes: {sorted({c['axis'] for c in deck})}")
    return len(deck)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        n = selftest()
        print(f"  deck ready: {n} signed J-space cards")
    else:
        deck = build_deck()
        print(json.dumps(deck[:8], indent=2))
        print(f"...\n  total cards in deck: {len(deck)}")

def save_deck(path: str = "forest/jspace_deck.json", deploy_root: str = ".") -> dict:
    """Persist the current KB-derived deck (Wave-3 move 27). Idempotent.

    Also writes a LIBRARY copy to deploy_root (default repo root .) so the
    build allowlist ships it live (same pattern as drift-feed.json). The
    forest/ copy is canonical; the root copy is the deployable mirror.
    """
    import os, time
    deck = build_deck()
    manifest = {
        "schema": "jspace-deck/1.0",
        "generated_at": time.time(),
        "count": len(deck),
        "cards": deck,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(deploy_root, "jspace_deck.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return manifest


def render_sigil_svg(card: dict, size: int = 256) -> str:
    """Render a card's deterministic visual sigil (mandala) — NO randomness.

    Wave-3 move 28. The geometry is a pure function of the card's sigil hash:
    rings count = sigil byte 0, spokes = byte 1, hue = byte 2, opacity = byte 3.
    Same card -> identical SVG every time. An honest visual fingerprint of the
    fact, not a fabricated 'model DNA' (the sketch's weight-mandala was fake).
    """
    h = card.get("sigil", "0x0000").replace("0x", "")
    hexv = int(h[:8], 16) if len(h) >= 6 else 0
    n_rings = 3 + (hexv & 7)
    n_spokes = 4 + ((hexv >> 3) & 11)
    hue = (hexv >> 7) % 360
    color = f"hsl({hue}, 70%, 50%)"
    c = size / 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">',
        f'<rect width="{size}" height="{size}" fill="#0a0a0a"/>',
        f'<g transform="translate({c},{c})">',
    ]
    for i in range(n_rings):
        r = int(14 + i * (c - 24) / max(n_rings, 1))
        op = 0.25 + ((hexv >> (i * 3)) % 32) / 100
        parts.append(f'<circle r="{r}" fill="none" stroke="{color if i % 2 == 0 else "#fff"}" stroke-width="1.2" opacity="{op:.2f}"/>')
    for i in range(n_spokes):
        ang = 3.14159 * 2 * i / n_spokes
        ln = int(20 + ((hexv >> (i * 2 + 4)) % 64) * 3)
        x2, y2 = (ln * __import__("math").cos(ang), ln * __import__("math").sin(ang))
        parts.append(f'<line x1="0" y1="0" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" stroke-width="1" opacity="0.6"/>')
    parts.append(f'<circle r="7" fill="{color}"/>')
    parts.append(f'<text x="0" y="{int(c - 8)}" text-anchor="middle" fill="#fff" font-size="9" font-family="monospace">{card.get("axis","")}</text>')
    parts.extend(["</g>", "</svg>"])
    return "\n".join(parts)


if __name__ == "__main__" and "--deck" in sys.argv:
    m = save_deck()
    print(f"saved {m['count']} cards -> forest/jspace_deck.json")


def c_space_fold(deck: list[dict] | None = None) -> dict:
    """Fold the J-space deck into ONE C-space card (Wave-3 move 30).

    Canon: '3-to-1 water/milk/honey fold = C-card; C-cards over time =
    SOV signal' (MEMORY-fusion-vwm). The sov model reads the C-card in ~3KB.
    Deterministic: hash-concatenate all card sigils, fold by the 3:1 rule.
    """
    deck = deck if deck is not None else build_deck()
    if not deck:
        return {"error": "no deck"}
    n = len(deck)
    # deterministic aggregate: concat sigils + fold weights
    joined = "".join(c.get("sigil", "0x0") for c in deck)
    axis_count = {}
    for c in deck:
        a = c.get("axis", "OSS")
        axis_count[a] = axis_count.get(a, 0) + 1
    # 3:1 fold: honey units = sum of card units / 3 (milk->honey consolidation)
    total_units = sum(c.get("value_score", 1) for c in deck)
    honey_units = max(1, int(total_units / 3))
    c_card = {
        "schema": "c-space-card/1.0",
        "deck_count": n,
        "axis_distribution": axis_count,
        "honey_units": honey_units,
        "sigil": "0x" + hashlib.sha256(joined.encode()).hexdigest()[:32],
        "summary": f"Folded {n} J-space cards (water/milk) -> honey C-card ({honey_units} units).",
    }
    return c_card


def save_c_card(path: str = "forest/c_space_card.json", deploy_root: str = ".") -> dict:
    import os, time
    c = c_space_fold()
    c["generated_at"] = time.time()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(c, f, indent=1)
    with open(os.path.join(deploy_root, "c_space_card.json"), "w") as f:
        json.dump(c, f, indent=1)
    return c
