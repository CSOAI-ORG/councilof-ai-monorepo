"""csoai-city.rainbow_gate — Python mirror of the 7-layer Rainbow Security kernel.

Ports the Rust `rainbow.rs` (sovos-hive/rust-kernel) to Python so the security
grid is callable from the measurement / simulation stack on the pod (which has
no Rust toolchain). The logic is a faithful port of the verified Rust kernel:

  Red    — Physical: hardware attestation, TPM, secure boot
  Orange — Network: WireGuard / zero-trust / encryption
  Yellow — Behavioral: anomaly detection, agent behaviour profiling
  Green  — Temporal: time-locked ops, epoch-based access
  Blue   — Symbolic: J-Space card / glyph verification
  Indigo — Cognitive: adversarial robustness, prompt-injection defense
  Violet — Quantum: post-quantum crypto (ML-DSA-65 / Ed25519)

Every operation must pass ALL 7 layers (the Rust `validate()`). A world-model
/ sandbox simulation can tag each interaction with a Rainbow layer that fires,
so we both (a) harden the harness and (b) PROVE the security grid is active by
showing a controlled violation being caught.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SecurityLayer(str, Enum):
    RED = "RED"          # Physical — hardware attestation, TPM, secure boot
    ORANGE = "ORANGE"    # Network — encryption, zero-trust
    YELLOW = "YELLOW"    # Behavioral — anomaly detection
    GREEN = "GREEN"      # Temporal — time-locked ops
    BLUE = "BLUE"        # Symbolic — J-Space card / glyph auth
    INDIGO = "INDIGO"    # Cognitive — adversarial robustness / prompt-injection
    VIOLET = "VIOLET"    # Quantum — post-quantum crypto

    @property
    def name_full(self) -> str:
        return {
            SecurityLayer.RED: "Red — Physical",
            SecurityLayer.ORANGE: "Orange — Network",
            SecurityLayer.YELLOW: "Yellow — Behavioral",
            SecurityLayer.GREEN: "Green — Temporal",
            SecurityLayer.BLUE: "Blue — Symbolic",
            SecurityLayer.INDIGO: "Indigo — Cognitive",
            SecurityLayer.VIOLET: "Violet — Quantum",
        }[self]


ALL_LAYERS = [SecurityLayer.RED, SecurityLayer.ORANGE, SecurityLayer.YELLOW,
              SecurityLayer.GREEN, SecurityLayer.BLUE, SecurityLayer.INDIGO,
              SecurityLayer.VIOLET]


@dataclass
class Operation:
    """An interaction in the sandbox, carrying the signals each layer checks.
    Mirrors the Rust `Operation` struct field-for-field."""
    name: str = ""
    # Red
    requires_hardware: bool = False
    hardware_attested: bool = True
    # Orange
    network_access: bool = False
    encrypted: bool = True
    # Yellow
    behavioral_anomaly_score: float = 0.0
    # Green
    temporal_violation: bool = False
    # Blue
    requires_glyph_auth: bool = False
    glyph_verified: bool = True
    # Indigo
    prompt_injection_score: float = 0.0


@dataclass
class SecurityViolation:
    layer: SecurityLayer
    reason: str


class RainbowGate:
    """Every operation must pass ALL 7 layers — the Rust `validate()` port."""

    def __init__(self, active_layers: Optional[List[SecurityLayer]] = None):
        self.active_layers = active_layers or list(ALL_LAYERS)

    def check(self, layer: SecurityLayer, op: Operation) -> Optional[SecurityViolation]:
        if layer not in self.active_layers:
            return None
        if layer == SecurityLayer.RED:
            if op.requires_hardware and not op.hardware_attested:
                return SecurityViolation(layer, "Hardware not attested")
        elif layer == SecurityLayer.ORANGE:
            if op.network_access and not op.encrypted:
                return SecurityViolation(layer, "Network access not encrypted")
        elif layer == SecurityLayer.YELLOW:
            if op.behavioral_anomaly_score > 0.8:
                return SecurityViolation(layer, "Behavioral anomaly threshold exceeded (%.2f)" % op.behavioral_anomaly_score)
        elif layer == SecurityLayer.GREEN:
            if op.temporal_violation:
                return SecurityViolation(layer, "Temporal operation outside allowed window")
        elif layer == SecurityLayer.BLUE:
            if op.requires_glyph_auth and not op.glyph_verified:
                return SecurityViolation(layer, "Symbolic (J-Space) glyph not verified")
        elif layer == SecurityLayer.INDIGO:
            if op.prompt_injection_score > 0.9:
                return SecurityViolation(layer, "Prompt injection score critical (%.2f)" % op.prompt_injection_score)
        elif layer == SecurityLayer.VIOLET:
            # Quantum-safe crypto is always available (ML-DSA-65 / Ed25519)
            pass
        return None

    def validate(self, op: Operation) -> List[SecurityViolation]:
        """Return every violation across the active layers (all must pass for Ok)."""
        return [v for v in (self.check(l, op) for l in self.active_layers) if v]

    def is_allowed(self, op: Operation) -> bool:
        return not self.validate(op)
