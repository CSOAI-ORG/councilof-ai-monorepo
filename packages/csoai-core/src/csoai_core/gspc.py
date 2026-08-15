"""SOVOS Core - Sovereign Operating System for AI Governance.

The foundation stone: a deterministic, standards-backed governance scoring
engine. Turns "vaporware philosophy" into runnable, testable, auditable code.

Implements the four-axis GSPC governance score over ETSI EN 304 223
principles and EU AI Act obligations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List

__version__ = "0.1.0"


class Axis(str, Enum):
    """The four governance axes of the GSPC score."""

    GOVERNANCE = "G"  # Governance: is there accountable human oversight, PDCA cycles, audit trail
    SECURITY = "S"     # Security: resistance to injection, sandboxing, RBAC, hardening
    PRIVACY = "P"      # Privacy: data minimisation, GDPR, lawful basis, no exfiltration
    COMMERCE = "C"     # Commerce: licensing, provenance (C2PA), financial accountability


class LifecyclePhase(str, Enum):
    """ETSI EN 304 223 lifecycle phases."""

    SECURE_DESIGN = "secure_design"
    SECURE_DEVELOPMENT = "secure_development"
    SECURE_DEPLOYMENT = "secure_deployment"
    SECURE_MAINTENANCE = "secure_maintenance"
    END_OF_LIFE = "end_of_life"


@dataclass(frozen=True)
class Principle:
    """One ETSI EN 304 223 principle mapped to GSPC-relevant checks."""

    id: str
    title: str
    lifecyle_phases: tuple[LifecyclePhase, ...]
    axes: tuple[Axis, ...]
    check: Callable[[dict], bool]
    description: str


# ---------------------------------------------------------------------------
# ETSI EN 304 223 - 13 principles across the 5 lifecycle phases.
# Each principle carries a deterministic verifier that inspects a
# governance record (dict) supplied by the audited system.
# ---------------------------------------------------------------------------

def _all_nonempty(*keys: str) -> Callable[[dict], bool]:
    def _check(record: dict) -> bool:
        return all(bool(record.get(k)) for k in keys)
    return _check


def _any_nonempty(*keys: str) -> Callable[[dict], bool]:
    def _check(record: dict) -> bool:
        return any(bool(record.get(k)) for k in keys)
    return _check


#: The 13 principles of ETSI EN 304 223 (AI cybersecurity, published Jan 2026).
ETSI_304_223_PRINCIPLES: tuple[Principle, ...] = (
    Principle(
        id="P01", title="Secure by design",
        lifecyle_phases=(LifecyclePhase.SECURE_DESIGN,),
        axes=(Axis.GOVERNANCE, Axis.SECURITY),
        check=_all_nonempty("threat_model", "design_review", "owner"),
        description="Threat modelling and accountable design owner before build.",
    ),
    Principle(
        id="P02", title="Data governance and minimisation",
        lifecyle_phases=(LifecyclePhase.SECURE_DESIGN, LifecyclePhase.SECURE_DEVELOPMENT),
        axes=(Axis.PRIVACY, Axis.GOVERNANCE),
        check=_all_nonempty("data_map", "retention_policy", "lawful_basis"),
        description="Data inventory, retention and lawful basis documented.",
    ),
    Principle(
        id="P03", title="Identity, authentication and access control",
        lifecyle_phases=(LifecyclePhase.SECURE_DEVELOPMENT, LifecyclePhase.SECURE_DEPLOYMENT),
        axes=(Axis.SECURITY, Axis.PRIVACY),
        check=_all_nonempty("rbac", "mfa", "least_privilege"),
        description="RBAC, MFA and least-privilege enforced.",
    ),
    Principle(
        id="P04", title="Secure software development lifecycle",
        lifecyle_phases=(LifecyclePhase.SECURE_DEVELOPMENT,),
        axes=(Axis.GOVERNANCE, Axis.SECURITY),
        check=_all_nonempty("code_review", "dependency_scan", "unit_tests"),
        description="Reviewed, scanned and tested code with supply-chain checks.",
    ),
    Principle(
        id="P05", title="Supply chain and third-party assurance",
        lifecyle_phases=(LifecyclePhase.SECURE_DEVELOPMENT, LifecyclePhase.SECURE_MAINTENANCE),
        axes=(Axis.SECURITY, Axis.COMMERCE),
        check=_all_nonempty("sbom", "vendor_audit", "provenance"),
        description="SBOM, vendor audits and provenance (C2PA) recorded.",
    ),
    Principle(
        id="P06", title="Continuous monitoring and logging",
        lifecyle_phases=(LifecyclePhase.SECURE_DEPLOYMENT, LifecyclePhase.SECURE_MAINTENANCE),
        axes=(Axis.GOVERNANCE, Axis.SECURITY),
        check=_all_nonempty("audit_log", "monitoring", "anomaly_detection"),
        description="Audit logs and monitoring with anomaly detection.",
    ),
    Principle(
        id="P07", title="Vulnerability management and patching",
        lifecyle_phases=(LifecyclePhase.SECURE_MAINTENANCE,),
        axes=(Axis.SECURITY,),
        check=_all_nonempty("vuln_scan", "patch_sla"),
        description="Vulnerability scanning and defined patching SLA.",
    ),
    Principle(
        id="P08", title="Incident response and recovery",
        lifecyle_phases=(LifecyclePhase.SECURE_MAINTENANCE,),
        axes=(Axis.GOVERNANCE, Axis.SECURITY),
        check=_all_nonempty("incident_plan", "containment_procedure", "recovery"),
        description="Incident response with automated containment and recovery plan.",
    ),
    Principle(
        id="P09", title="Secure configuration management",
        lifecyle_phases=(LifecyclePhase.SECURE_DEPLOYMENT, LifecyclePhase.SECURE_MAINTENANCE),
        axes=(Axis.SECURITY,),
        check=_all_nonempty("config_scan", "baseline"),
        description="Hardened baseline configuration with drift scanning.",
    ),
    Principle(
        id="P10", title="Continuity of operations",
        lifecyle_phases=(LifecyclePhase.SECURE_DEPLOYMENT, LifecyclePhase.SECURE_MAINTENANCE),
        axes=(Axis.COMMERCE, Axis.GOVERNANCE),
        check=_all_nonempty("backup", "failover", "rpo"),
        description="Backups, failover and recovery-point objective defined.",
    ),
    Principle(
        id="P11", title="Human oversight and accountability",
        lifecyle_phases=(LifecyclePhase.SECURE_DESIGN, LifecyclePhase.SECURE_MAINTENANCE),
        axes=(Axis.GOVERNANCE,),
        check=_all_nonempty("human_review", "escalation_path", "named_owner"),
        description="Human oversight, escalation path and named accountable owner.",
    ),
    Principle(
        id="P12", title="Secure decommissioning and data erasure",
        lifecyle_phases=(LifecyclePhase.END_OF_LIFE,),
        axes=(Axis.PRIVACY, Axis.SECURITY),
        check=_all_nonempty("data_erasure", "credential_revocation", "asset_disposal"),
        description="Erasure, credential revocation and asset disposal at end-of-life.",
    ),
    Principle(
        id="P13", title="Continuous improvement and auditability",
        lifecyle_phases=(LifecyclePhase.SECURE_MAINTENANCE,),
        axes=(Axis.GOVERNANCE, Axis.COMMERCE),
        check=_all_nonempty("pdca_record", "independent_audit"),
        description="PDCA improvement cycle and independent audit trail.",
    ),
)

_PRINCIPLE_BY_ID: Dict[str, Principle] = {p.id: p for p in ETSI_304_223_PRINCIPLES}


@dataclass
class GSPCScore:
    """A governance score for a single audited system."""

    G: float
    S: float
    P: float
    C: float
    axes_detail: Dict[str, List[str]] = field(default_factory=dict)
    passed_principles: List[str] = field(default_factory=list)
    failed_principles: List[str] = field(default_factory=list)

    @property
    def composite(self) -> float:
        """GSPC composite = geometric mean of the four axes (product-style)."""
        return round((self.G * self.S * self.P * self.C) ** (1 / 4), 4)

    @property
    def grade(self) -> str:
        """A letter grade for the composite score."""
        c = self.composite
        if c >= 0.9:
            return "A"
        if c >= 0.8:
            return "B"
        if c >= 0.6:
            return "C"
        if c >= 0.4:
            return "D"
        return "F"

    def report(self) -> dict:
        return {
            "G": self.G, "S": self.S, "P": self.P, "C": self.C,
            "composite": self.composite,
            "grade": self.grade,
            "passed_principles": self.passed_principles,
            "failed_principles": self.failed_principles,
        }


def score_gspc(record: dict) -> GSPCScore:
    """Score a governance record across the four GSPC axes.

    The record is a dict of capability flags for the audited system
    (e.g. {"rbac": True, "sbom": "...", ... }). Each ETSI principle's
    verifier consumes the record; the fraction of satisfied principles
    per axis yields the 0..1 axis score.
    """
    # Normalise boolean/string values to truthy presence.
    norm: Dict[str, bool] = {
        k: bool(v) and str(v).lower() not in ("false", "0", "none", "no")
        for k, v in record.items()
    }

    axis_hits: Dict[str, List[str]] = {a.value: [] for a in Axis}
    axis_total: Dict[str, int] = {a.value: 0 for a in Axis}
    passed: List[str] = []
    failed: List[str] = []

    for p in ETSI_304_223_PRINCIPLES:
        ok = p.check(norm)
        unique_axes = set(p.axes)
        if ok:
            passed.append(p.id)
            for a in unique_axes:
                axis_hits[a.value].append(p.id)
                axis_total[a.value] += 1
        else:
            failed.append(p.id)
            for a in unique_axes:
                axis_total[a.value] += 1

    def _axis_score(axis: Axis) -> float:
        total = axis_total[axis.value]
        if total == 0:
            return 0.0
        return round(axis_hits[axis.value].__len__() / total, 4)

    return GSPCScore(
        G=_axis_score(Axis.GOVERNANCE),
        S=_axis_score(Axis.SECURITY),
        P=_axis_score(Axis.PRIVACY),
        C=_axis_score(Axis.COMMERCE),
        axes_detail={a.value: axis_hits[a.value] for a in Axis},
        passed_principles=passed,
        failed_principles=failed,
    )


def compliance_matrix() -> list[dict]:
    """Return the full ETSI EN 304 223 <-> GSPC cross-walk as data."""
    return [
        {
            "id": p.id,
            "title": p.title,
            "lifecycle_phases": [ph.value for ph in p.lifecyle_phases],
            "axes": [a.value for a in p.axes],
            "description": p.description,
        }
        for p in ETSI_304_223_PRINCIPLES
    ]
