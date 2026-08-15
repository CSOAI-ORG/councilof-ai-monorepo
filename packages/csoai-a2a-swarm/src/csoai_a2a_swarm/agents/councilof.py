"""CouncilOfAgent — governance auditor.

Skills:
- audit_decision(decision): scores a decision against EU AI Act / NIST RMF
- issue_certificate(audit_id): returns a signed compliance certificate
- veto(decision_id, reason): blocks an unsafe decision

Triggers (per SOVOS brief):
- Every agent decision that triggers another agent should be audited
- Decisions with risk_score > 0.7 are flagged for human review
- Decisions with risk_score > 0.9 are auto-vetoed

Real CouncilOf.ai is more complex — this is a minimal honest demo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..signing import attach_signature


@dataclass
class AuditRecord:
    """The result of auditing one agent decision."""
    audit_id: str
    decision_id: str
    decision_agent: str
    risk_score: float  # 0.0 (safe) to 1.0 (high risk)
    risk_categories: List[str] = field(default_factory=list)
    passed: bool = True
    rationale: str = ""


class CouncilOfAgent:
    """Governance auditor — applies EU AI Act / NIST RMF rubrics."""

    def __init__(self, name: str = "councilof-001") -> None:
        self.name = name
        self.audits: Dict[str, AuditRecord] = {}
        self.vetoes: List[Dict[str, Any]] = []

    def audit_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Score an agent decision against governance rubrics.

        Decision payload expected to have:
        - agent (str): who made the decision
        - action (str): what they did
        - status (str, optional): outcome severity
        - cost_gbp (float, optional): financial impact
        - task_vector (list, optional): embedding of the decision context

        Returns: signed audit response with risk_score, risk_categories, passed flag
        """
        audit_id = f"A-{len(self.audits) + 1:04d}"
        decision_id = decision.get("decision_id", audit_id)
        decision_agent = decision.get("agent", "unknown")
        risk_score = 0.0
        risk_categories = []
        rationale_parts = []
        # Risk factor 1: emergency actions have higher risk
        if decision.get("priority") == "emergency" or decision.get("status") == "red":
            risk_score += 0.3
            risk_categories.append("emergency_action")
            rationale_parts.append("emergency action — elevated oversight required")
        # Risk factor 2: financial impact
        cost = decision.get("cost_gbp", 0)
        if cost > 100:
            risk_score += 0.2
            risk_categories.append("financial_impact")
            rationale_parts.append(f"financial impact £{cost} exceeds £100 threshold")
        # Risk factor 3: exfiltration or sensitive data
        if "exfiltration" in str(decision.get("categories", [])):
            risk_score += 0.4
            risk_categories.append("data_handling")
            rationale_parts.append("decision involves data exfiltration pathway")
        # Risk factor 4: critical-severity agent output
        if decision.get("status") == "critical":
            risk_score += 0.5
            risk_categories.append("critical_severity")
            rationale_parts.append("decision triggered critical-severity upstream")
        # Cap at 1.0
        risk_score = min(1.0, risk_score)
        passed = risk_score <= 0.7
        if not passed:
            rationale_parts.append(f"risk_score {risk_score:.2f} exceeds 0.7 threshold — human review required")
        if not rationale_parts:
            rationale_parts.append(f"risk_score {risk_score:.2f} within acceptable bounds")
        record = AuditRecord(
            audit_id=audit_id,
            decision_id=decision_id,
            decision_agent=decision_agent,
            risk_score=risk_score,
            risk_categories=risk_categories,
            passed=passed,
            rationale="; ".join(rationale_parts),
        )
        self.audits[audit_id] = record
        result = {
            "agent": self.name,
            "action": "audit_decision",
            "audit_id": audit_id,
            "decision_id": decision_id,
            "decision_agent": decision_agent,
            "risk_score": risk_score,
            "risk_categories": risk_categories,
            "passed": passed,
            "rationale": record.rationale,
            "task_vector": [
                risk_score,
                1.0 if passed else 0.0,
                len(risk_categories) / 5.0,
                1.0 if "emergency_action" in risk_categories else 0.0,
                1.0 if "financial_impact" in risk_categories else 0.0,
                1.0 if "data_handling" in risk_categories else 0.0,
                1.0 if "critical_severity" in risk_categories else 0.0,
                0.0,
            ],
        }
        return attach_signature(result)

    def issue_certificate(self, audit_id: str) -> Dict[str, Any]:
        """Issue a signed compliance certificate for a passing audit."""
        if audit_id not in self.audits:
            result = {
                "agent": self.name,
                "action": "issue_certificate",
                "audit_id": audit_id,
                "status": "error",
                "reason": f"unknown audit_id '{audit_id}'",
            }
            return attach_signature(result)
        audit = self.audits[audit_id]
        if not audit.passed:
            result = {
                "agent": self.name,
                "action": "issue_certificate",
                "audit_id": audit_id,
                "status": "denied",
                "reason": f"audit did not pass (risk_score={audit.risk_score:.2f}), cannot issue certificate",
            }
            return attach_signature(result)
        cert_id = f"CERT-{audit_id}"
        result = {
            "agent": self.name,
            "action": "issue_certificate",
            "audit_id": audit_id,
            "cert_id": cert_id,
            "issued_at": "2026-08-10",
            "decision_agent": audit.decision_agent,
            "risk_score": audit.risk_score,
            "valid_for_days": 90,
            "frameworks": ["EU-AI-Act-2024", "NIST-RMF-1.0"],
        }
        return attach_signature(result)

    def veto(self, decision_id: str, reason: str) -> Dict[str, Any]:
        """Block an unsafe decision. Returns a signed veto."""
        veto_record = {
            "agent": self.name,
            "action": "veto",
            "decision_id": decision_id,
            "reason": reason,
            "timestamp": "2026-08-10",
        }
        self.vetoes.append(veto_record)
        return attach_signature(veto_record)

    def skills(self) -> Dict[str, Any]:
        """Return the public skill manifest."""
        return {
            "agent": self.name,
            "type": "governance-auditor",
            "skills": [
                {"name": "audit_decision", "params": ["decision"]},
                {"name": "issue_certificate", "params": ["audit_id"]},
                {"name": "veto", "params": ["decision_id", "reason"]},
            ],
            "pricing": {
                "audit_decision": "£0.50 per call",
                "issue_certificate": "£50 per cert",
                "veto": "free (safety override)",
            },
            "frameworks": ["EU AI Act 2024", "NIST AI RMF 1.0", "ISO/IEC 42001"],
        }


__all__ = ["CouncilOfAgent", "AuditRecord"]
