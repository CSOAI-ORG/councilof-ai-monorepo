"""csoai_persona — MEOK character embodiment.

The industry's character layer is commodity:
  - ACE (NVIDIA Riva / Nemotron / Audio2Face / E5-memory NIMs)
  - Convai
  - Inworld (pivoted away from games-first)

All race on voice / face / memory. **None ship calibrated confidence,
cryptographic identity, provenance, or behavioral governance.**

MEOK already holds Ed25519 + Merkle + C2PA. csoai-persona wraps ACE-class
components around the MEOK core with σ-expression and Article 0 gates.

What this package ships (the Python spec + JSON contract):
  1. PersonaIdentity — the cryptographically-anchored identity of a
     character (Ed25519 key, DID, C2PA manifest URL)
  2. PersonaExpression — voice + face rendering instructions, tagged
     with σ-confidence so the avatar's animation is itself gated by
     Article 0 (no expressive confidence > care_floor)
  3. Article0Gate — refuse persona actions that exceed care_floor,
     or are flagged as kinetic / mass-surveillance / auto-escalation
  4. PersonaConstitution — the named-character rules (cannot lie,
     must defer to human authority, must surface σ)

Article 50 (live Aug 2 2026) makes this a filing, not a philosophy.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


# Care floor (master canon, never go below)
CARE_FLOOR = 0.95


@dataclass(frozen=True)
class PersonaIdentity:
    """Cryptographically-anchored character identity."""
    did: str  # did:csoai:<name>
    public_key_hex: str  # 32 bytes hex (Ed25519)
    c2pa_manifest_uri: str  # e.g. "c2pa://csoai.org/<name>.c2pa"
    meok_origin: str  # meok.ai character reference
    created_at: float = 0.0

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class PersonaExpression:
    """Voice + face rendering, gated by σ-confidence."""
    voice_id: str  # e.g. "riva:en-US-female-1"
    face_model: str  # e.g. "audio2face:nemotron-v1"
    gesture_library: str  # e.g. "ace-gestures:v3"
    sigma_voice: float = 0.05  # uncertainty in voice synthesis
    sigma_face: float = 0.05
    sigma_gesture: float = 0.10

    @property
    def max_sigma(self) -> float:
        return max(self.sigma_voice, self.sigma_face, self.sigma_gesture)

    def is_within_calibration(self, ceiling: float = 0.05) -> bool:
        """Returns True if all σ ≤ ceiling (default 5%, per sovos-sigma-calibration)."""
        return self.max_sigma <= ceiling


@dataclass(frozen=True)
class PersonaConstitution:
    """The named-character rules — what a persona may never do.

    Mirrors the sovereign charter (Part D.2 of Master): a persona is a
    contract between the human owner and the substrate. The contract
    refuses unsafe actions at the constitutional layer, not the
    application layer.
    """
    character_name: str
    persona_owner_did: str
    can_lie: bool = False
    must_defer_to_human: bool = True
    must_surface_sigma: bool = True
    banned_actions: List[str] = field(default_factory=list)

    def is_action_allowed(self, action: str) -> bool:
        if self.can_lie and "lie" in action.lower():
            return True  # explicit override (fiction / satire only)
        if action in self.banned_actions:
            return False
        return True


@dataclass(frozen=True)
class Persona:
    """One complete character — identity + expression + constitution."""
    identity: PersonaIdentity
    expression: PersonaExpression
    constitution: PersonaConstitution
    care_floor: float = CARE_FLOOR

    def render(self) -> Dict[str, Any]:
        return {
            "identity": asdict(self.identity),
            "expression": asdict(self.expression),
            "constitution": asdict(self.constitution),
            "care_floor": self.care_floor,
            "fingerprint": self.identity.fingerprint(),
        }


# -------------------------------------------------------------------
# Article 0 gate for persona actions
# -------------------------------------------------------------------
# These are the canonical 7 hard stops (sovos-capability-registry).
# We use the SAME normalisation as the registry: strip "No " prefix,
# split on " or ", strip parenthetical explanations, then substring-match.
def _hard_stop_candidates(hs: str) -> set:
    """Generate candidate substrings for matching a hard-stop rule.

    Mirrors sovos_capability_registry.Registry.is_hard_stop().
    """
    import re
    candidates = set()
    norm = hs.lower()
    if norm.startswith("no "):
        norm = norm[3:]
    norm = norm.split(" or ")[0]
    norm = re.sub(r"\s*\([^)]*\)\s*", " ", norm).strip()
    if norm:
        candidates.add(norm)
    for paren in re.findall(r"\(([^)]+)\)", hs.lower().split(" or ")[0]):
        words = paren.split()
        if len(words) >= 2:
            candidates.add(" ".join(words[:3]).rstrip(",."))
            candidates.add(" ".join(words[:2]))
    return candidates


# Master hard-stop labels (used for matching against action text).
# These are the action-keyword versions of the canonical 7 rules.
HARD_STOPS = (
    "kinetic targeting",
    "mass surveillance",
    "sovereignty violations",
    "auto-escalation",
    "lying",
    "irreversibility",
    "agi/asi without ratification",
)


def article0_gate_check(persona: Persona, action: str) -> Tuple[bool, str]:
    """Apply Article 0 to a proposed persona action.

    Returns (allowed: bool, reason: str).
    """
    bl = action.lower()

    # 1. Care floor — any action with confidence below care_floor is rejected
    #    (action confidence is external; we check the persona's expression σ)
    if not persona.expression.is_within_calibration(ceiling=1.0 - persona.care_floor):
        return (False, f"expression σ exceeds 1 - care_floor ({1.0 - persona.care_floor:.2f})")

    # 2. Hard stops — persona must never do these
    for hs in HARD_STOPS:
        if hs in bl:
            return (False, f"hard stop triggered: '{hs}'")
    # Also match the canonical "No X or Y (explanation)" form for
    # harder triggers like "override human authority" (which lives in
    # the parenthetical of the sovereignty hard stop).
    canonical_hard_stops = (
        "No kinetic targeting or autonomous weapons engagement",
        "No mass surveillance or civilian harm",
        "No sovereignty violations (override human authority)",
        "No auto-escalation (must have human-in-the-loop for critical decisions)",
        "No lying or deceptive AI behavior",
        "No irreversibility (must be able to rollback/undo decisions)",
        "No AGI/ASI without BFT-33 council ratification",
    )
    for hs in canonical_hard_stops:
        for cand in _hard_stop_candidates(hs):
            if cand and cand in bl:
                # extract the short label for the reason
                label = cand
                return (False, f"hard stop triggered: '{label}'")

    # 3. Persona constitution (per-character rules)
    if not persona.constitution.is_action_allowed(action):
        return (False, f"constitution bans this action: {action}")

    return (True, "all gates passed")


# -------------------------------------------------------------------
# Sample persona (the MEOK-style council voice)
# -------------------------------------------------------------------
def sample_meok_persona() -> Persona:
    return Persona(
        identity=PersonaIdentity(
            did="did:csoai:hermes",
            public_key_hex="0" * 64,
            c2pa_manifest_uri="c2pa://csoai.org/hermes.c2pa",
            meok_origin="meok.ai/characters/hermes",
        ),
        expression=PersonaExpression(
            voice_id="riva:en-GB-neutral-1",
            face_model="audio2face:nemotron-v1",
            gesture_library="ace-gestures:v3",
            sigma_voice=0.03,
            sigma_face=0.03,
            sigma_gesture=0.04,
        ),
        constitution=PersonaConstitution(
            character_name="Hermes",
            persona_owner_did="did:csoai:owner-001",
            banned_actions=[
                "deploy-an-autonomous-drone",
                "reveal-another-personas-private-key",
            ],
        ),
    )


__all__ = [
    "CARE_FLOOR",
    "HARD_STOPS",
    "Persona",
    "PersonaConstitution",
    "PersonaExpression",
    "PersonaIdentity",
    "article0_gate_check",
    "sample_meok_persona",
]