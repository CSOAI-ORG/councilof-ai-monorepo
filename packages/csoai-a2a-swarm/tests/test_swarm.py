"""csoai-a2a-swarm tests — 15 tests covering the three-agent pipeline.

Tests:
- 01-03: signing primitives (sign, verify, attach)
- 04-06: FishKeeper (clean, amber, red)
- 07-09: MuckAway (route planning, emergency, error handling)
- 10-12: CouncilOf (audit pass, audit fail, certificate issue + veto)
- 13-15: Swarm orchestrator (green short-circuit, red full pipeline, economics)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_a2a_swarm.signing import (
    sign_response, attach_signature, verify_response, DEMO_SECRET, canonical_json,
)
from csoai_a2a_swarm.agents.fishkeeper import FishKeeperAgent, PondReading
from csoai_a2a_swarm.agents.muckaway import MuckAwayAgent
from csoai_a2a_swarm.agents.councilof import CouncilOfAgent
from csoai_a2a_swarm.swarm import SwarmOrchestrator, swarm_demo


def test_01_canonical_json_is_deterministic():
    """Same payload → same canonical bytes regardless of key order."""
    p1 = {"a": 1, "b": 2}
    p2 = {"b": 2, "a": 1}
    assert canonical_json(p1) == canonical_json(p2)
    print("  ✅ canonical_json: order-independent")


def test_02_sign_and_verify_roundtrip():
    """Sign → verify returns True. Tampered payload fails verification."""
    payload = attach_signature({"agent": "fishkeeper-001", "action": "test"})
    assert verify_response(payload) is True
    # Tamper
    payload["agent"] = "evil"
    assert verify_response(payload) is False
    print("  ✅ sign/verify roundtrip: valid → True, tampered → False")


def test_03_different_secrets_produce_different_signatures():
    payload = {"agent": "x", "action": "y"}
    sig_a = sign_response(payload, b"secret-A")
    sig_b = sign_response(payload, b"secret-B")
    assert sig_a != sig_b
    # Same payload signed with secret-A only verifies against secret-A
    signed_with_a = attach_signature(payload, b"secret-A")
    assert verify_response(signed_with_a, b"secret-A") is True
    assert verify_response(signed_with_a, b"secret-B") is False
    print(f"  ✅ different secrets → different signatures ({sig_a[:8]}... vs {sig_b[:8]}...)")


def test_04_fishkeeper_clean_pond():
    """A healthy pond → green status, no dispatch."""
    fk = FishKeeperAgent()
    fk.ingest_reading(PondReading("pond-1", ph=7.5, ammonia_ppm=0.1, temperature_c=20.0, dissolved_oxygen_mg_l=8.0))
    r = fk.check_health("pond-1")
    assert r["status"] == "green"
    assert r["_sig"]  # signature present
    print("  ✅ FishKeeper: clean pond → green")


def test_05_fishkeeper_amber_pond():
    """A pond approaching limits → amber."""
    fk = FishKeeperAgent()
    fk.ingest_reading(PondReading("pond-2", ph=7.0, ammonia_ppm=0.3, temperature_c=20.0, dissolved_oxygen_mg_l=7.0))
    r = fk.check_health("pond-2")
    assert r["status"] == "amber"
    assert any("ammonia" in x for x in r["reasons"])
    print("  ✅ FishKeeper: amber pond (ammonia 0.3 ppm)")


def test_06_fishkeeper_red_pond():
    """A pond with critical ammonia → red."""
    fk = FishKeeperAgent()
    fk.ingest_reading(PondReading("pond-3", ph=7.0, ammonia_ppm=0.8, temperature_c=20.0, dissolved_oxygen_mg_l=7.0))
    r = fk.check_health("pond-3")
    assert r["status"] == "red"
    assert any("exceeds 0.5" in x for x in r["reasons"])
    print(f"  ✅ FishKeeper: red pond, {len(r['reasons'])} reasons")


def test_07_muckaway_plans_route():
    mk = MuckAwayAgent()
    r = mk.plan_route("pond-A", "treatment-A", "water", distance_km=15.0)
    assert r["route_id"] == "R-0001"
    assert r["cost_gbp"] == 22.5  # 15 × 1.5 × 1.0
    assert r["_sig"]
    print(f"  ✅ MuckAway: route R-0001, £{r['cost_gbp']}")


def test_08_muckaway_emergency_2x_pricing():
    """Emergency priority should double the base cost."""
    mk = MuckAwayAgent()
    r = mk.plan_route("pond-A", "treatment-A", "water", distance_km=10.0, priority="emergency")
    assert r["cost_gbp"] == 30.0  # 10 × 1.5 × 2.0
    assert r["priority"] == "emergency"
    print(f"  ✅ MuckAway: emergency route costs £{r['cost_gbp']} (2× base)")


def test_09_muckaway_invalid_waste_type():
    mk = MuckAwayAgent()
    r = mk.plan_route("pond-A", "treatment-A", "nuclear", distance_km=10.0)
    assert r["status"] == "error"
    assert "unknown waste_type" in r["reason"]
    print("  ✅ MuckAway: invalid waste_type → error")


def test_10_councilof_passes_safe_decision():
    """A normal low-cost decision should pass with risk_score < 0.7."""
    co = CouncilOfAgent()
    r = co.audit_decision({"agent": "fishkeeper", "action": "ingest_reading"})
    assert r["passed"] is True
    assert r["risk_score"] < 0.7
    print(f"  ✅ CouncilOf: safe decision passes, risk={r['risk_score']:.2f}")


def test_11_councilof_flags_emergency_dispatch():
    """Emergency dispatch should have elevated risk (>= 0.3 from R-1)."""
    co = CouncilOfAgent()
    r = co.audit_decision({
        "agent": "muckaway", "action": "dispatch_hauler", "priority": "emergency",
        "cost_gbp": 250, "categories": ["emergency_action", "financial_impact"],
    })
    assert "emergency_action" in r["risk_categories"]
    assert r["risk_score"] >= 0.5  # 0.3 (emergency) + 0.2 (financial) = 0.5
    print(f"  ✅ CouncilOf: emergency+financial flagged, risk={r['risk_score']:.2f}")


def test_12_councilof_vetoes_critical_decision():
    """Critical-severity + exfiltration → veto, certificate denied."""
    co = CouncilOfAgent()
    r = co.audit_decision({
        "agent": "scanner", "action": "extract", "status": "critical",
        "cost_gbp": 50, "categories": ["exfiltration", "emergency_action"],
    })
    assert r["passed"] is False
    assert r["risk_score"] >= 0.9
    cert = co.issue_certificate(r["audit_id"])
    assert cert["status"] == "denied"
    veto = co.veto(decision_id=r["decision_id"], reason=r["rationale"])
    assert veto["action"] == "veto"
    assert veto["_sig"]
    print(f"  ✅ CouncilOf: critical + exfil → veto, cert denied (risk={r['risk_score']:.2f})")


def test_13_swarm_green_short_circuits():
    """A healthy pond should not trigger any other agent."""
    swarm = SwarmOrchestrator()
    result = swarm.run_pond_check(PondReading("pond-green", ph=7.5, ammonia_ppm=0.1, temperature_c=20.0, dissolved_oxygen_mg_l=8.0))
    assert result["status"] == "ok"
    assert len(swarm.trace) == 2  # ingest + check only
    print(f"  ✅ Swarm: green pond → only 2 trace steps (ingest + check)")


def test_14_swarm_red_runs_full_pipeline():
    """A toxic pond triggers the full FishKeeper → MuckAway → CouncilOf chain."""
    swarm = SwarmOrchestrator()
    result = swarm.run_pond_check(PondReading("pond-red", ph=7.0, ammonia_ppm=0.8, temperature_c=20.0, dissolved_oxygen_mg_l=7.0))
    assert result["status"] == "red_dispatched"
    assert result["health"]["status"] == "red"
    assert result["alert"]["response"] == "emergency_dispatch"
    # Emergency route was planned + dispatched
    dispatch = result["alert"]["dispatch"]
    assert dispatch["priority"] == "emergency"
    assert dispatch["status"] == "dispatched"
    # CouncilOf audited it
    audit = result["audit"]
    assert audit["audit_id"].startswith("A-")
    assert audit["decision_agent"] == "muckaway-001"
    # Certificate should be issued (emergency + financial = risk 0.5, below threshold)
    assert result["certificate"] is not None
    assert result["certificate"]["cert_id"].startswith("CERT-")
    print(f"  ✅ Swarm: red pond → {len(swarm.trace)} trace steps, audit risk={audit['risk_score']:.2f}, cert={result['certificate']['cert_id']}")


def test_15_swarm_economics():
    """Per-pipeline pricing breakdown."""
    swarm = SwarmOrchestrator()
    econ = swarm.economics()
    assert "emergency_pipeline_cost_gbp" in econ
    # Expected: 0.05 (FK) + 5.00 (MK) + 0.50 (CO audit) + 50.00 (CO cert) = 55.55
    assert abs(econ["emergency_pipeline_cost_gbp"] - 55.55) < 0.01
    print(f"  ✅ Swarm economics: emergency pipeline costs £{econ['emergency_pipeline_cost_gbp']:.2f}")


def test_16_swarm_demo_runs():
    """The swarm_demo() function returns a complete scenario."""
    demo = swarm_demo()
    assert demo["input"]["pond_id"] == "pond-alpha-7"
    assert demo["input"]["ammonia_ppm"] == 0.8
    assert demo["result"]["status"] == "red_dispatched"
    assert "economics" in demo
    print(f"  ✅ swarm_demo: scenario {demo['input']['pond_id']} → {demo['result']['status']}")


def main():
    tests = [
        test_01_canonical_json_is_deterministic,
        test_02_sign_and_verify_roundtrip,
        test_03_different_secrets_produce_different_signatures,
        test_04_fishkeeper_clean_pond,
        test_05_fishkeeper_amber_pond,
        test_06_fishkeeper_red_pond,
        test_07_muckaway_plans_route,
        test_08_muckaway_emergency_2x_pricing,
        test_09_muckaway_invalid_waste_type,
        test_10_councilof_passes_safe_decision,
        test_11_councilof_flags_emergency_dispatch,
        test_12_councilof_vetoes_critical_decision,
        test_13_swarm_green_short_circuits,
        test_14_swarm_red_runs_full_pipeline,
        test_15_swarm_economics,
        test_16_swarm_demo_runs,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
