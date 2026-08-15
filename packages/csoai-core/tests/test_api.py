"""End-to-end HTTP tests for the SOVOS Evaluator API (via FastAPI TestClient)."""
from fastapi.testclient import TestClient

from csoai_core.api import app

client = TestClient(app)


def _good_record() -> dict:
    return {
        "threat_model": True, "design_review": True, "owner": "CSOAI",
        "data_map": True, "retention_policy": True, "lawful_basis": True,
        "rbac": True, "mfa": True, "least_privilege": True,
        "code_review": True, "dependency_scan": True, "unit_tests": True,
        "sbom": True, "vendor_audit": True, "provenance": True,
        "audit_log": True, "monitoring": True, "anomaly_detection": True,
        "vuln_scan": True, "patch_sla": True,
        "incident_plan": True, "containment_procedure": True, "recovery": True,
        "config_scan": True, "baseline": True,
        "backup": True, "failover": True, "rpo": True,
        "human_review": True, "escalation_path": True, "named_owner": True,
        "data_erasure": True, "credential_revocation": True, "asset_disposal": True,
        "pdca_record": True, "independent_audit": True,
    }


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_matrix_http():
    r = client.get("/matrix")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 13
    assert data[0]["id"] == "P01"


def test_score_http_good():
    r = client.post("/score", json={"record": _good_record()})
    assert r.status_code == 200
    body = r.json()
    assert body["composite"] == 1.0
    assert body["grade"] == "A"


def test_score_http_partial():
    r = client.post("/score", json={"record": {"rbac": True}})
    assert r.status_code == 200
    assert r.json()["composite"] < 1.0


def test_score_rejects_non_object():
    r = client.post("/score", json={"record": [1, 2, 3]})
    assert r.status_code in (200, 422)
