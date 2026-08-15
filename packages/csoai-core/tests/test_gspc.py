import json

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from csoai_core import Axis, ETSI_304_223_PRINCIPLES, compliance_matrix, score_gspc


def _good_record() -> dict:
    """A governance record that satisfies every ETSI principle."""
    return {
        # P01
        "threat_model": True, "design_review": True, "owner": "CSOAI",
        # P02
        "data_map": True, "retention_policy": True, "lawful_basis": True,
        # P03
        "rbac": True, "mfa": True, "least_privilege": True,
        # P04
        "code_review": True, "dependency_scan": True, "unit_tests": True,
        # P05
        "sbom": True, "vendor_audit": True, "provenance": True,
        # P06
        "audit_log": True, "monitoring": True, "anomaly_detection": True,
        # P07
        "vuln_scan": True, "patch_sla": True,
        # P08
        "incident_plan": True, "containment_procedure": True, "recovery": True,
        # P09
        "config_scan": True, "baseline": True,
        # P10
        "backup": True, "failover": True, "rpo": True,
        # P11
        "human_review": True, "escalation_path": True, "named_owner": True,
        # P12
        "data_erasure": True, "credential_revocation": True, "asset_disposal": True,
        # P13
        "pdca_record": True, "independent_audit": True,
    }


def test_13_principles_defined():
    assert len(ETSI_304_223_PRINCIPLES) == 13
    ids = {p.id for p in ETSI_304_223_PRINCIPLES}
    assert ids == {f"P{i:02d}" for i in range(1, 14)}


def test_compliance_matrix_shape():
    matrix = compliance_matrix()
    assert len(matrix) == 13
    for row in matrix:
        assert "lifecycle_phases" in row and row["lifecycle_phases"]
        assert "axes" in row and row["axes"]


def test_fully_compliant_system_scores_1_0():
    result = score_gspc(_good_record())
    assert result.G == 1.0 and result.S == 1.0
    assert result.P == 1.0 and result.C == 1.0
    assert result.composite == 1.0
    assert result.grade == "A"
    assert len(result.passed_principles) == 13


def test_empty_system_scores_zero():
    result = score_gspc({})
    assert result.composite == 0.0
    assert result.grade == "F"


def test_partial_system_penalises_security_and_privacy():
    # Everything compliant except all security + privacy + commerce items.
    record = _good_record()
    for k in ("rbac", "mfa", "least_privilege", "vuln_scan", "patch_sla",
              "config_scan", "baseline", "dependency_scan"):
        record[k] = False
    for k in ("data_map", "retention_policy", "lawful_basis",
              "data_erasure", "credential_revocation"):
        record[k] = False
    result = score_gspc(record)
    # Removing security + privacy + commerce items must reduce those axes
    # (and implicitly G too, since P02/P04 are G-axis principles).
    assert result.S < 1.0
    assert result.P < 1.0
    assert result.composite < 1.0
    assert len(result.failed_principles) > 0


def test_falsey_strings_do_not_count_as_present():
    # "false"/"0"/"none" strings must not be treated as satisfied.
    record = _good_record()
    record["rbac"] = "false"
    record["mfa"] = "0"
    result = score_gspc(record)
    assert result.S < 1.0


def test_report_json_serialisable():
    json.dumps(score_gspc(_good_record()).report())


def test_every_axis_measured():
    result = score_gspc(_good_record())
    for axis in Axis:
        assert axis.value in result.axes_detail
        assert axis.value in result.report()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
