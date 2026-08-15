"""csoai_fleet — Fleet-learning schema + 3KB skill card.

The architecture (Master Part W.4):
  Isaac Lab G1 env → distill → 3KB card (SIGIL+C2PA+σ)
  → arena gate → ChainResult → SOV Space registry
  → NVFLARE distribution → Procrustes cross-body pull.

Sim-only first, zero hardware. Every layer free except the trust layer.

This package ships:
  1. **SkillCard** — the 3KB skill card schema (task, embodiment,
     policy-hash, σ, ChainResult-ID, SIGIL, C2PA-URI)
  2. **SkillCardSizeError** — enforces the 3KB ceiling
  3. **FleetLedger** — append-only signed registry
  4. **EmbodimentPorts** — placeholder for the Procrustes cross-body
     transfer (the cross-manufacturer gap)

Honest scope: the actual Isaac Lab integration requires GPU + Isaac
Sim. This package is the *data* side — the schema, the registry, the
card-format. The training is a separate pipeline.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# 3KB card ceiling
MAX_CARD_BYTES = 3072


@dataclass(frozen=True)
class SkillCard:
    """A signed, provenance-anchored skill card.

    The card is the trust wrapper the upstream never shipped. It's the
    atom of fleet distribution.
    """
    task: str                # what the skill does ("pick-up-cup")
    embodiment: str          # which body ("unitree-g1", "figure-02", "tesla-optimus")
    policy_hash: str         # sha256 of the policy weights
    sigma: float             # uncertainty (0..1)
    chain_result_id: str     # the ChainResult that produced this card
    sigil: str               # Ed25519 sigil (0x + 32 hex)
    c2pa_uri: str            # c2pa:// URI for provenance manifest
    version: str = "1.0"
    # NOTE: no created_at — timestamps make fingerprints non-deterministic
    # across two cards minted in the same second. Reproducibility > clock.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()

    def size_bytes(self) -> int:
        return len(self.to_json_bytes())

    def fits_3kb(self) -> bool:
        return self.size_bytes() <= MAX_CARD_BYTES

    def fingerprint(self) -> str:
        return hashlib.sha256(self.to_json_bytes()).hexdigest()[:16]


class SkillCardSizeError(Exception):
    """Raised when a SkillCard exceeds the 3KB ceiling."""
    def __init__(self, actual: int, limit: int = MAX_CARD_BYTES):
        self.actual = actual
        self.limit = limit
        super().__init__(f"card is {actual} bytes, exceeds {limit}-byte (3KB) ceiling")


def make_card(
    task: str,
    embodiment: str,
    policy_hash: str,
    sigma: float,
    chain_result_id: str,
    sigil: str,
    c2pa_uri: str,
) -> SkillCard:
    """Create a SkillCard. Raises SkillCardSizeError if it exceeds 3KB.

    The 3KB ceiling is a doctrine, not a number — it forces the card
    to be the distillation of the skill, not its representation.
    Honest cards for real skills are < 3KB. Larger cards mean the
    upstream produced too much noise; reject and re-distill.
    """
    card = SkillCard(
        task=task,
        embodiment=embodiment,
        policy_hash=policy_hash,
        sigma=sigma,
        chain_result_id=chain_result_id,
        sigil=sigil,
        c2pa_uri=c2pa_uri,
    )
    n = card.size_bytes()
    if n > MAX_CARD_BYTES:
        raise SkillCardSizeError(n)
    return card


# -------------------------------------------------------------------
# Fleet ledger (append-only signed registry)
# -------------------------------------------------------------------
@dataclass
class FleetLedger:
    """Append-only registry of skill cards. Each entry signed by SIGIL."""
    cards: List[SkillCard] = field(default_factory=list)
    chain: List[str] = field(default_factory=list)  # chain_ids of appended cards

    def append(self, card: SkillCard) -> str:
        """Append a card. Returns the entry chain_id (sha256(card))."""
        self.cards.append(card)
        self.chain.append(card.fingerprint())
        return card.fingerprint()

    def __len__(self) -> int:
        return len(self.cards)

    def for_embodiment(self, embodiment: str) -> List[SkillCard]:
        return [c for c in self.cards if c.embodiment == embodiment]

    def for_task(self, task: str) -> List[SkillCard]:
        return [c for c in self.cards if c.task == task]

    def total_sigma(self) -> float:
        if not self.cards:
            return 0.0
        return sum(c.sigma for c in self.cards) / len(self.cards)


# -------------------------------------------------------------------
# Embodiment ports (Master Part W.4)
# -------------------------------------------------------------------
@dataclass(frozen=True)
class EmbodimentPort:
    """A cross-embodiment transfer port (Procrustes alignment).

    The cross-manufacturer gap nobody else has: Procrustes align between
    two embodiments' action-head weights, so a skill learned on G1 can
    transfer to Optimus or Figure. This is the architecture-level
    carrier for fleet learning.

    Master Part W.4 honest scope: the math exists (Part W, Procrustes),
    unbuilt on GR00T heads. This package holds the schema; the actual
    alignment runs in sovos-info-geometry / sovos-jspace-pipeline.
    """
    src_embodiment: str
    dst_embodiment: str
    procrustes_matrix_hash: str  # sha256 of the alignment matrix
    n_samples: int              # number of trajectory pairs used to fit
    mean_residual: float        # mean residual after alignment (lower = better)


def fleet_manifest(ledger: FleetLedger) -> Dict[str, Any]:
    """A summary view of the ledger."""
    return {
        "n_cards": len(ledger),
        "n_chain": len(ledger.chain),
        "mean_sigma": ledger.total_sigma(),
        "embodiments": sorted({c.embodiment for c in ledger.cards}),
            "tasks": sorted({c.task for c in ledger.cards}),
        }


__all__ = [
    "EmbodimentPort",
    "FleetLedger",
    "MAX_CARD_BYTES",
    "SkillCard",
    "SkillCardSizeError",
    "fleet_manifest",
    "make_card",
]