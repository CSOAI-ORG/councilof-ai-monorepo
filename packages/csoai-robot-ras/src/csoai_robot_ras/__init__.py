"""csoai_robot_ras — Physical-AI RAS (Master Part U.4).

EU Machinery Regulation 2023/1230 (mandatory 20 Jan 2027) covers
AI-integrated machinery; "safety components with self-evolving
behaviour based on machine learning" = Annex I Part A notified-body
category.

The market currently buys 96-page PDF template kits — it pays for
documents. **We sell the machine that produces the evidence**:
  - MR 2023/1230 + ISO 10218-1/2:2025 crosswalk
  - ChainResult attestation per OTA update
  - SOV SIGNAL per fleet

This package ships:
  1. RobotInventoryEntry — one robot in the fleet
  2. OTAEvidence — every OTA update emits one of these
  3. MR20231230Checklist — the 14 mandatory obligations
  4. ISO10218Checklist — Class 1/2 collaborative robot requirements
  5. ConformityAssessment — DoC + technical file index

Honest scope: this is the data model + checklist logic. The actual
file generation (DoC, technical file PDFs) is downstream.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# -------------------------------------------------------------------
# Enums
# -------------------------------------------------------------------
class ISO10218Class(str, Enum):
    """ISO 10218-1:2025 collaborative robot class."""
    CLASS_1_STOP = "Class 1 — safety-rated monitored stop"
    CLASS_2_SPEED_SEPARATION = "Class 2 — speed and separation monitoring"
    CLASS_3_POWER_LIMITING = "Class 3 — power and force limiting"


class OARiskClass(str, Enum):
    """OA risk tier for the OTA evidence pipeline."""
    LOW = "LOW"             # pure model update, no behaviour change
    MEDIUM = "MEDIUM"       # model + skill update, behaviour-tested
    HIGH = "HIGH"           # architecture change, full re-cert


# -------------------------------------------------------------------
# Robot inventory entry
# -------------------------------------------------------------------
@dataclass(frozen=True)
class RobotInventoryEntry:
    """One robot in the fleet."""
    serial: str
    manufacturer: str
    model: str
    iso_class: ISO10218Class
    ce_marked: bool
    doc_signed_at: float = 0.0
    ai_self_evolving: bool = False  # if True → MR 2023/1230 Annex I Part A


# -------------------------------------------------------------------
# OTA evidence — every OTA update emits one
# -------------------------------------------------------------------
@dataclass(frozen=True)
class OTAEvidence:
    """Signed record of one OTA software update.

    Per MR 2023/1230: OTA updates can be "substantial modifications"
    transferring manufacturer obligations to operators. We capture
    the change, the evidence, the chain_result_id, and the SIGIL.
    """
    robot_serial: str
    pre_update_skill_card_hash: str  # sha256 of the card BEFORE update
    post_update_skill_card_hash: str
    oa_risk_class: OARiskClass
    sov_signal_distance: float       # Mahalanobis σ distance from permitted manifold
    chain_result_id: str
    sigil: str                       # 0x + 32 hex
    timestamp: float = 0.0

    def is_substantial_modification(self) -> bool:
        """MR 2023/1230 — if oa_risk_class is HIGH, this IS a substantial mod."""
        return self.oa_risk_class == OARiskClass.HIGH

    def fingerprint(self) -> str:
        import json
        from dataclasses import asdict
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]


# -------------------------------------------------------------------
# MR 2023/1230 — 14 mandatory obligations
# -------------------------------------------------------------------
@dataclass
class MR20231230Checklist:
    """The 14 mandatory obligations for AI-integrated machinery."""
    entry: RobotInventoryEntry
    compliance: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 14 canonical obligations
        defaults = {
            "1_declaration_of_conformity": False,
            "2_ce_marking": False,
            "3_technical_file_10_year_retention": False,
            "4_risk_assessment_self_evolving": False,
            "5_safety_function_validation": False,
            "6_cybersecurity_essential_requirements": False,
            "7_ai_act_art49_post_market": False,
            "8_dpia_data_protection_impact": False,
            "9_incident_reporting_mechanism": False,
            "10_registration_eu_database": False,
            "11_human_oversight_interface": False,
            "12_user_instructions": False,
            "13_logging_trail_per_decision": False,
            "14_conformity_assessment_procedure": False,
        }
        for k, v in defaults.items():
            self.compliance.setdefault(k, v)

    def mark(self, key: str, value: bool = True) -> None:
        if key not in self.compliance:
            raise KeyError(f"unknown obligation: {key}")
        self.compliance[key] = value

    def completed_count(self) -> int:
        return sum(1 for v in self.compliance.values() if v)

    def is_complete(self) -> bool:
        return self.completed_count() == 14

    def gaps(self) -> List[str]:
        return [k for k, v in self.compliance.items() if not v]


# -------------------------------------------------------------------
# ISO 10218 — Class 1/2/3 checklist
# -------------------------------------------------------------------
@dataclass
class ISO10218Checklist:
    """ISO 10218-1:2025 collaborative robot requirements per class."""
    entry: RobotInventoryEntry
    requirements: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Per-class requirements (subset)
        if self.entry.iso_class == ISO10218Class.CLASS_1_STOP:
            reqs = {
                "safety_rated_monitored_stop": False,
                "protective_device_test": False,
                "restart_procedure_documented": False,
            }
        elif self.entry.iso_class == ISO10218Class.CLASS_2_SPEED_SEPARATION:
            reqs = {
                "speed_separation_distance": False,
                "human_detection_systems": False,
                "protective_device_test": False,
            }
        else:
            reqs = {
                "power_limiting_configured": False,
                "force_limit_validated": False,
                "collision_force_test": False,
            }
        for k, v in reqs.items():
            self.requirements.setdefault(k, v)

    def is_complete(self) -> bool:
        return all(self.requirements.values())

    def gaps(self) -> List[str]:
        return [k for k, v in self.requirements.items() if not v]


# -------------------------------------------------------------------
# Conformity assessment
# -------------------------------------------------------------------
@dataclass(frozen=True)
class ConformityAssessment:
    """The signed Conformity package — DoC + technical file index."""
    robot_serial: str
    ce_mark_year: int
    technical_file_hash: str  # sha256 of the technical file
    chain_result_id: str
    sigil: str

    def fingerprint(self) -> str:
        import json
        from dataclasses import asdict
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]


__all__ = [
    "ConformityAssessment",
    "ISO10218Checklist",
    "ISO10218Class",
    "MR20231230Checklist",
    "OARiskClass",
    "OTAEvidence",
    "RobotInventoryEntry",
]