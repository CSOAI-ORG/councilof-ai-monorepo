"""csoai-hive — Python facade for the SOVOS Fractal Monotric Hive.

The Rust kernel lives at `rust-kernel/` (the canonical implementation).
This module exposes the same surface as a Python module so the rest of
the SOVOS monorepo can drive the hive without writing Rust.

Absorbed 2026-08-11 from the standalone `sov-hive/` crate. Read
`README.md` for the operator-grade one-paragraph summary, and
`SOVOS_MEMORY.md` (under `rust-kernel/`) for the live runtime status
(2026-08-01 snapshot — agentmemory, cognee, mem0, Graphiti, NVIDIA NIM).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Scale constants — same node, different zoom levels.
# byte-sized so they pack into the IWM 128-bit fractal address space.
# ---------------------------------------------------------------------------
class Scale:
    TOKEN = 0        # single token / embedding
    AGENT = 8        # individual AI agent
    CLAN = 16        # framework clan (Mastra, LangGraph, ...)
    CLUSTER = 24     # OWEM cluster (CSOAI, MEOK, DEFONEOS)
    ECOSYSTEM = 32   # entire SOV ecosystem


# ---------------------------------------------------------------------------
# GSPC (sovos-core's existing 4-axis score, see sovos-core/sovos_core/gspc.py)
# ---------------------------------------------------------------------------
@dataclass
class GSPCAxes:
    """The 4 GSPC axes — Governance, Security, Privacy, Commerce (each 0..1)."""
    governance: float = 0.0
    security: float = 0.0
    privacy: float = 0.0
    commerce: float = 0.0

    def as_array(self) -> List[float]:
        return [self.governance, self.security, self.privacy, self.commerce]

    @classmethod
    def from_array(cls, values: List[float]) -> "GSPCAxes":
        if len(values) != 4:
            raise ValueError(f"GSPCAxes needs 4 values, got {len(values)}")
        return cls(*values)


# ---------------------------------------------------------------------------
# The immutable withdrawn registry — every level of the hive consults it
# before routing a query to a model. Absorbed from withdrawn.py.
# ---------------------------------------------------------------------------
WITHDRAWN_MODELS = {
    # The most prominent one is the withdrawn.py "anomaly registry" —
    # models that have shown miscalibrated behavior on a critical axis
    # and must never be routed to without a bandit override.
    "claude-opus-4.5-haunted":   "Anomalous citation behaviour (2026-Q3 sandbox sigil); withdrawn from default routing.",
    "sov-agi-v4-unbound":        "Failed Article 50 boundaries; model cards do not declare OWEM wrappers.",
    "gpt-realtime-corporate-v0": "Provenance C2PA inconsistent; not bound to sovereign substrate yet.",
    "gemini-2.5-attribution":    "Failed provenance test (provbench-15asset 2026-07-30): cannot route to absence of C2PA.",
}


# ---------------------------------------------------------------------------
# J-Space Cards (symbolic knowledge tarot, 54 archetypes)
# Absorbed from /forest/jspace_deck.json (54 cards).
# ---------------------------------------------------------------------------
@dataclass
class JSpaceCard:
    card_id: str
    axis: str                 # "ASI" / "ASI-X" / etc
    piece_type: str           # Rook / Knight / ...
    owner: str
    color: str
    jspace_position: Tuple[int, int, int]
    sigil: str
    size_bytes: int
    honey_rank: str           # water / air / fire / earth
    question: str
    answer_hash: str
    source: str
    value_score: float


@dataclass
class JSpaceDeck:
    cards: List[JSpaceCard]
    schema: str
    generated_at: float

    def by_axis(self, axis: str) -> List[JSpaceCard]:
        return [c for c in self.cards if c.axis == axis]

    def by_owner(self, owner: str) -> List[JSpaceCard]:
        return [c for c in self.cards if c.owner == owner]


def _jspace_data_dir() -> Path:
    """Locate the canonical SOVOS/data/hive/ directory.

    Walks up from this module to find a sibling `data/hive/` dir. If not
    found, falls back to the package's local `data/` (forward-compat).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "data" / "hive"
        if cand.is_dir():
            return cand
    return here.parent.parent.parent / "data"  # fallback


def jspace_deck() -> JSpaceDeck:
    """Load the 54-card J-Space deck from data/jspace_deck.json."""
    p = _jspace_data_dir() / "jspace_deck.json"
    if not p.exists():
        return JSpaceDeck(cards=[], schema="jspace-deck/1.0", generated_at=0.0)
    d = json.loads(p.read_text())
    cards = [JSpaceCard(
        card_id=c["card_id"], axis=c["axis"], piece_type=c["piece_type"],
        owner=c["owner"], color=c["color"],
        jspace_position=tuple(c["jspace_position"].values()) if isinstance(c["jspace_position"], dict) else tuple(c["jspace_position"]),
        sigil=c["sigil"], size_bytes=c["size_bytes"], honey_rank=c["honey_rank"],
        question=c["question"], answer_hash=c["answer_hash"], source=c["source"],
        value_score=c["value_score"],
    ) for c in d.get("cards", [])]
    return JSpaceDeck(cards=cards, schema=d.get("schema", ""),
                      generated_at=d.get("generated_at", 0.0))


# ---------------------------------------------------------------------------
# OWEM Swarm — the registry of clans (Mastra, LangGraph, AG2, MSAF, ...)
# Absorbed from /forest/owem_clan_swarm.json.
# ---------------------------------------------------------------------------
@dataclass
class OWEMClan:
    clan_id: str              # e.g. "clan-mastra"
    framework: str            # e.g. "mastra"
    role: str                 # e.g. "agent_routing"
    joined_at: str            # ISO timestamp
    status: str               # active / paused / retired


@dataclass
class OWEMSwarm:
    swarm_id: str
    created_at: str
    paradigm: str
    clans: List[OWEMClan]

    @property
    def active_clans(self) -> List[OWEMClan]:
        return [c for c in self.clans if c.status == "active"]

    def clan_for(self, role: str) -> Optional[OWEMClan]:
        for c in self.clans:
            if c.role == role and c.status == "active":
                return c
        return None


def owem_swarm() -> OWEMSwarm:
    p = _jspace_data_dir() / "owem_clan_swarm.json"
    if not p.exists():
        return OWEMSwarm(swarm_id="", created_at="", paradigm="", clans=[])
    d = json.loads(p.read_text())
    clans = [OWEMClan(
        clan_id=c["clan_id"], framework=c["framework"], role=c["role"],
        joined_at=c["joined_at"], status=c["status"],
    ) for c in d.get("clans", [])]
    return OWEMSwarm(swarm_id=d.get("swarm_id", ""),
                     created_at=d.get("created_at", ""),
                     paradigm=d.get("paradigm", ""),
                     clans=clans)


# ---------------------------------------------------------------------------
# HiveNode — the fractal monotric cell (mirrors Rust struct in
# rust-kernel/src/hive.rs). Same node, different zoom levels.
# ---------------------------------------------------------------------------
@dataclass
class NodeState:
    energy: float                   # cognitive activity 0..1
    gspc: GSPCAxes
    kind: str                       # "Token" | "Agent:..." | "Clan:..." | "Cluster:..." | "Ecosystem"
    is_dreaming: bool
    last_action: str
    memory: List[str]               # recent glyph memory (text)


@dataclass
class HiveNode:
    """A node in the SOVOS hive. Fractal: same structure at every scale."""
    id: int
    epoch: int
    scale: int                      # Scale.TOKEN / AGENT / CLAN / CLUSTER / ECOSYSTEM
    axes: GSPCAxes
    state: NodeState
    children_ids: List[int] = field(default_factory=list)
    parent_id: Optional[int] = None
    label: str = ""

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    def is_withdrawn(self, label: str) -> bool:
        """Returns True if this node's label is in the WITHDRAWN registry."""
        return label in WITHDRAWN_MODELS


# ---------------------------------------------------------------------------
# Lazy reference to the Rust kernel (not all host machines have cargo).
# Tests will assert this is None on Python-only environments.
# ---------------------------------------------------------------------------
def _try_load_rust_kernel():
    """Try to load the compiled sov_hive Rust extension. Returns None if absent."""
    try:
        import sov_hive_rs  # type: ignore
        return sov_hive_rs
    except ImportError:
        return None


RUST_KERNEL = _try_load_rust_kernel()
RUST_KERNEL_LOADED = RUST_KERNEL is not None


def _scale_name(scale: int) -> str:
    return {0: "TOKEN", 8: "AGENT", 16: "CLAN",
            24: "CLUSTER", 32: "ECOSYSTEM"}.get(scale, f"SCALE-{scale}")


def describe_scale(scale: int) -> str:
    return f"Scale {scale} = {_scale_name(scale)} (fractal self-similar)"


# ---------------------------------------------------------------------------
# Self-test (offline-safe — no Rust needed, no kernel compile needed)
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    return {
        "rust_kernel_loaded": RUST_KERNEL_LOADED,
        "scales": {0: "TOKEN", 8: "AGENT", 16: "CLAN", 24: "CLUSTER", 32: "ECOSYSTEM"},
        "n_withdrawn": len(WITHDRAWN_MODELS),
        "n_jspace_cards": len(jspace_deck().cards) if jspace_deck().cards else 0,
        "n_active_clans": len(owem_swarm().active_clans) if owem_swarm().clans else 0,
    }


__all__ = [
    "Scale",
    "GSPCAxes",
    "HiveNode",
    "NodeState",
    "OWEMClan",
    "OWEMSwarm",
    "JSpaceCard",
    "JSpaceDeck",
    "WITHDRAWN_MODELS",
    "owem_swarm",
    "jspace_deck",
    "describe_scale",
    "self_test",
    "RUST_KERNEL",
    "RUST_KERNEL_LOADED",
]
