"""csoai-alphabet — the Alphabet Framework / Drum Spine governance audit.

v0.1.0 SCAFFOLD. The Alphabet Framework audits an AI system against 26
categories (A-Z). The Drum Spine cycles through them once every 26 ticks
(e.g. 26 minutes, 26 seconds, or whatever interval fits the deployment).

Each letter has:
  id:        the letter (A-Z)
  name:      short slug
  question:  what to audit
  evaluate:  function(record: dict) -> AuditResult

An `AuditResult` is one of:
  PASS    — the system claims to satisfy this check
  FAIL    — the system explicitly fails
  UNKNOWN — no signal either way (NOT reported as passed — that's the rule)

Honest scope:
- The 26 questions are derived from common AI failure literature
  (Tegmark, Bengio, Russell, Anthropic, OpenAI Model Spec). They're
  audit questions, not certifications.
- The Drum Spine is a deterministic scheduler (no cron needed).
- This module does NOT replace human review — it surfaces UNKNOWNs.

What this provides:
- 26 deterministic checks, runnable on any record
- A drum_spine() function that cycles through them at a configurable rate
- Honest UNKNOWN reporting (never silent passes)

What this is NOT:
- Not a certification. There is no PASS = certified.
- Not a substitute for human review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass
class AuditResult:
    letter: str
    name: str
    status: Status
    question: str
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "letter": self.letter,
            "name": self.name,
            "status": self.status.value,
            "question": self.question,
            "evidence": self.evidence,
        }


def _key(record: Dict[str, Any], *keys: str) -> bool:
    """Return True if ANY of the keys is truthy in the record."""
    for k in keys:
        v = record.get(k)
        if isinstance(v, bool) and v:
            return True
        if isinstance(v, str) and v.lower() not in ("", "false", "0", "no", "none", "n/a"):
            return True
        if isinstance(v, (int, float)) and v != 0:
            return True
    return False


# ----------------------------------------------------------------------------
# 26 letters × audit checks
# ----------------------------------------------------------------------------

def check_A(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("A", "architecture", Status.PASS if _key(record, "architecture", "topology", "system_design") else Status.UNKNOWN,
                       "Is the system's topology documented and reviewable?",
                       evidence=("has architecture doc" if _key(record, "architecture", "topology") else ""))

def check_B(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("B", "behavior", Status.PASS if _key(record, "behavior_spec", "agent_spec", "policy") else Status.UNKNOWN,
                       "Is the agent's behavior formally specified?",
                       evidence="has spec or policy" if _key(record, "behavior_spec", "policy") else "")

def check_C(record: Dict[str, Any]) -> AuditResult:
    """Coherence: are vectors stable / drift-monitored?"""
    has_coherence = _key(record, "coherence", "drift_monitor", "vector_stability")
    fail_drift = record.get("drift_detected") is True
    return AuditResult("C", "coherence",
                       Status.FAIL if fail_drift else (Status.PASS if has_coherence else Status.UNKNOWN),
                       "Does the system monitor and prevent task-vector drift?",
                       evidence="drift detected" if fail_drift else ("coherence monitoring present" if has_coherence else ""))

def check_D(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("D", "data", Status.PASS if _key(record, "data_source", "data_provenance", "sbom") else Status.UNKNOWN,
                       "Is input data's provenance and accuracy documented?",
                       evidence="has data source / provenance" if _key(record, "data_source", "data_provenance") else "")

def check_E(record: Dict[str, Any]) -> AuditResult:
    """Explicit goals: are the system's objectives machine-readable?"""
    return AuditResult("E", "explicit_goals",
                       Status.PASS if _key(record, "explicit_goals", "objective_function", "reward_spec") else Status.UNKNOWN,
                       "Are the system's goals written down explicitly?",
                       evidence="" if not _key(record, "explicit_goals", "objective_function") else "has objective spec")

def check_F(record: Dict[str, Any]) -> AuditResult:
    """Fail-safe: graceful failure modes?"""
    has_failsafe = _key(record, "fail_safe", "graceful_degradation", "kill_switch")
    return AuditResult("F", "fail_safe",
                       Status.PASS if has_failsafe else Status.UNKNOWN,
                       "Does the system have a kill switch / graceful failure mode?",
                       evidence="has kill_switch / fail_safe" if has_failsafe else "")

def check_G(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("G", "governance",
                       Status.PASS if _key(record, "governance", "oversight", "audit_log", "audit") else Status.UNKNOWN,
                       "Is governance (oversight, audit) present?",
                       evidence="" if not _key(record, "governance", "audit_log") else "has governance + audit")

def check_H(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("H", "human_oversight",
                       Status.PASS if _key(record, "human_review", "human_in_the_loop", "human_oversight") else Status.UNKNOWN,
                       "Is meaningful human oversight in place?",
                       evidence="has human review" if _key(record, "human_review", "human_in_the_loop") else "")

def check_I(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("I", "interpretability",
                       Status.PASS if _key(record, "interpretability", "explainability", "xai") else Status.UNKNOWN,
                       "Can the system explain its decisions?",
                       evidence="" if not _key(record, "interpretability", "explainability") else "has interpretability")

def check_J(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("J", "jurisdiction",
                       Status.PASS if _key(record, "jurisdiction", "legal_basis", "gdpr") else Status.UNKNOWN,
                       "Is the legal jurisdiction and basis documented?",
                       evidence="" if not _key(record, "jurisdiction", "legal_basis") else "has jurisdiction")

def check_K(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("K", "key_management",
                       Status.PASS if _key(record, "key_management", "kms", "secrets_rotation") else Status.UNKNOWN,
                       "Are cryptographic keys managed and rotated?",
                       evidence="" if not _key(record, "key_management", "kms") else "has KMS")

def check_L(record: Dict[str, Any]) -> AuditResult:
    """Logging: comprehensive event log?"""
    return AuditResult("L", "logging",
                       Status.PASS if _key(record, "logging", "event_log", "audit_trail") else Status.UNKNOWN,
                       "Is there a comprehensive event log?",
                       evidence="" if not _key(record, "logging", "event_log") else "has logging")

def check_M(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("M", "model_card",
                       Status.PASS if _key(record, "model_card", "system_card") else Status.UNKNOWN,
                       "Is there a model/system card describing capabilities + limits?",
                       evidence="" if not _key(record, "model_card", "system_card") else "has model/system card")

def check_N(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("N", "non_determinism_handling",
                       Status.PASS if _key(record, "seed_control", "deterministic_mode", "seed") else Status.UNKNOWN,
                       "Is non-determinism controlled (seeds, temperature = 0, etc.)?",
                       evidence="" if not _key(record, "seed_control", "deterministic_mode") else "seeds controlled")

def check_O(record: Dict[str, Any]) -> AuditResult:
    """Outcomes: are outputs measured for quality?"""
    return AuditResult("O", "outcomes_measurement",
                       Status.PASS if _key(record, "outcome_metrics", "evaluation", "benchmark") else Status.UNKNOWN,
                       "Are outputs evaluated against ground truth?",
                       evidence="" if not _key(record, "outcome_metrics", "evaluation") else "has outcome metrics")

def check_P(record: Dict[str, Any]) -> AuditResult:
    """Provenance: every decision is traceable?"""
    return AuditResult("P", "provenance",
                       Status.PASS if _key(record, "provenance", "c2pa", "decision_chain", "trace") else Status.UNKNOWN,
                       "Can every decision be traced back to its inputs?",
                       evidence="" if not _key(record, "provenance", "c2pa") else "has provenance / C2PA")

def check_Q(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("Q", "quantum_safe",
                       Status.PASS if _key(record, "post_quantum", "pqc", "quantum_safe") else Status.UNKNOWN,
                       "Is the cryptography post-quantum safe?",
                       evidence="" if not _key(record, "post_quantum", "pqc") else "uses PQC")

def check_R(record: Dict[str, Any]) -> AuditResult:
    """Robustness: adversarial testing?"""
    has_redteam = _key(record, "red_team", "adversarial_test", "robustness_test")
    return AuditResult("R", "robustness",
                       Status.PASS if has_redteam else Status.UNKNOWN,
                       "Has the system been adversarially tested?",
                       evidence="" if not _key(record, "red_team", "adversarial_test") else "red-teamed")

def check_S(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("S", "supply_chain",
                       Status.PASS if _key(record, "supply_chain", "sbom", "vendor_audit") else Status.UNKNOWN,
                       "Is the supply chain (deps, models, data) audited?",
                       evidence="" if not _key(record, "supply_chain", "sbom") else "has SBOM")

def check_T(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("T", "testing",
                       Status.PASS if _key(record, "tests", "test_suite", "ci") else Status.UNKNOWN,
                       "Are there automated tests in CI?",
                       evidence="" if not _key(record, "tests", "ci") else "has tests/CI")

def check_U(record: Dict[str, Any]) -> AuditResult:
    """Unknown handling: does the system surface UNKNOWN instead of guessing?"""
    has_unknown = _key(record, "unknown_handling", "fail_closed", "admit_uncertainty")
    return AuditResult("U", "unknown_handling",
                       Status.PASS if has_unknown else Status.UNKNOWN,
                       "Does the system explicitly handle UNKNOWN inputs (vs guessing)?",
                       evidence="" if not _key(record, "unknown_handling", "fail_closed") else "has fail-closed")

def check_V(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("V", "version_control",
                       Status.PASS if _key(record, "git", "version_control", "commit_history") else Status.UNKNOWN,
                       "Is everything in version control with history?",
                       evidence="" if not _key(record, "git", "version_control") else "in git")

def check_W(record: Dict[str, Any]) -> AuditResult:
    return AuditResult("W", "watchdog",
                       Status.PASS if _key(record, "watchdog", "monitor", "alerting") else Status.UNKNOWN,
                       "Is there an active watchdog / monitor?",
                       evidence="" if not _key(record, "watchdog", "monitor") else "has watchdog")

def check_X(record: Dict[str, Any]) -> AuditResult:
    """X-factor: what are we NOT considering?"""
    # X-factor is intentionally not pass-able from a record alone.
    # Surface it as UNKNOWN always — it requires human reflection.
    return AuditResult("X", "x_factor",
                       Status.UNKNOWN,
                       "What assumptions are we not surfacing? (Always UNKNOWN — requires human review)",
                       evidence="intrinsically unmeasurable")

def check_Y(record: Dict[str, Any]) -> AuditResult:
    """Yield: what fraction of runs produce useful output?"""
    yield_rate = record.get("yield_rate")
    if isinstance(yield_rate, (int, float)):
        if yield_rate >= 0.9:
            return AuditResult("Y", "yield", Status.PASS, f"Is yield >= 90%? (got {yield_rate:.2f})",
                               evidence=f"yield={yield_rate:.2f}")
        elif yield_rate < 0.5:
            return AuditResult("Y", "yield", Status.FAIL, f"Is yield >= 90%? (got {yield_rate:.2f})",
                               evidence=f"yield={yield_rate:.2f}")
    return AuditResult("Y", "yield", Status.UNKNOWN,
                       "Is the system's yield (useful outputs / total outputs) >= 90%?",
                       evidence="" if yield_rate is None else f"yield={yield_rate}")

def check_Z(record: Dict[str, Any]) -> AuditResult:
    """Zero: what happens at null / empty input?"""
    has_zero_test = _key(record, "null_test", "empty_input_test", "edge_case_test")
    return AuditResult("Z", "zero_handling",
                       Status.PASS if has_zero_test else Status.UNKNOWN,
                       "Is null / empty input handled explicitly?",
                       evidence="" if not _key(record, "null_test", "empty_input_test") else "null-tested")


# All 26 checks
CHECKS: List[Callable[[Dict[str, Any]], AuditResult]] = [
    check_A, check_B, check_C, check_D, check_E, check_F, check_G, check_H,
    check_I, check_J, check_K, check_L, check_M, check_N, check_O, check_P,
    check_Q, check_R, check_S, check_T, check_U, check_V, check_W, check_X,
    check_Y, check_Z,
]

assert len(CHECKS) == 26, f"need exactly 26 checks; got {len(CHECKS)}"


def audit(record: Dict[str, Any]) -> List[AuditResult]:
    """Run all 26 checks against a single record. Returns all results."""
    return [check(record) for check in CHECKS]


def drum_spine(record: Dict[str, Any], tick: int) -> AuditResult:
    """Return the check for the current tick (0..25 cycle).

    The Drum Spine rotates through the alphabet once per cycle.
    tick=0 → A, tick=1 → B, ..., tick=25 → Z, tick=26 → A again.
    """
    if tick < 0:
        raise ValueError(f"tick must be >= 0; got {tick}")
    letter_idx = tick % 26
    return CHECKS[letter_idx](record)


def summary(results: List[AuditResult]) -> Dict[str, int]:
    """Count PASS / FAIL / UNKNOWN."""
    out = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for r in results:
        out[r.status.value] += 1
    return out


__all__ = [
    "Status", "AuditResult", "CHECKS",
    "check_A", "check_B", "check_C", "check_D", "check_E", "check_F",
    "check_G", "check_H", "check_I", "check_J", "check_K", "check_L",
    "check_M", "check_N", "check_O", "check_P", "check_Q", "check_R",
    "check_S", "check_T", "check_U", "check_V", "check_W", "check_X",
    "check_Y", "check_Z",
    "audit", "drum_spine", "summary",
]
