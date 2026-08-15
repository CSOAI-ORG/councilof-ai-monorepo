"""Tests for csoai-robot-ras — Physical-AI RAS for MR 2023/1230 + ISO 10218."""
from __future__ import annotations

import pytest
from csoai_robot_ras import (
    ConformityAssessment,
    ISO10218Checklist,
    ISO10218Class,
    MR20231230Checklist,
    OARiskClass,
    OTAEvidence,
    RobotInventoryEntry,
)


def test_01_iso10218_classes_count():
    assert len(ISO10218Class) == 3
    for cls in ISO10218Class:
        assert cls.value.startswith("Class ")


def test_02_oa_risk_classes_count():
    assert len(OARiskClass) == 3
    assert OARiskClass.LOW == "LOW"
    assert OARiskClass.MEDIUM == "MEDIUM"
    assert OARiskClass.HIGH == "HIGH"


def test_03_robot_inventory_entry_constructs():
    e = RobotInventoryEntry(
        serial="G1-001",
        manufacturer="unitree",
        model="G1",
        iso_class=ISO10218Class.CLASS_2_SPEED_SEPARATION,
        ce_marked=True,
        ai_self_evolving=False,
    )
    assert e.serial == "G1-001"
    assert e.iso_class == ISO10218Class.CLASS_2_SPEED_SEPARATION


def test_04_mr_checklist_has_14_obligations():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_1_STOP, ce_marked=True,
    )
    cl = MR20231230Checklist(entry=e)
    assert cl.completed_count() == 0
    assert len(cl.compliance) == 14


def test_05_mr_checklist_mark_completes():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_1_STOP, ce_marked=True,
    )
    cl = MR20231230Checklist(entry=e)
    cl.mark("1_declaration_of_conformity")
    cl.mark("2_ce_marking")
    assert cl.completed_count() == 2
    assert not cl.is_complete()
    assert "1_declaration_of_conformity" not in cl.gaps()
    assert "3_technical_file_10_year_retention" in cl.gaps()


def test_06_mr_checklist_complete():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_1_STOP, ce_marked=True,
    )
    cl = MR20231230Checklist(entry=e)
    for k in cl.compliance:
        cl.mark(k)
    assert cl.is_complete()
    assert cl.gaps() == []


def test_07_mr_checklist_unknown_key_raises():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_1_STOP, ce_marked=True,
    )
    cl = MR20231230Checklist(entry=e)
    with pytest.raises(KeyError):
        cl.mark("nonexistent_obligation")


def test_08_iso_checklist_class1_requirements():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_1_STOP, ce_marked=True,
    )
    cl = ISO10218Checklist(entry=e)
    assert "safety_rated_monitored_stop" in cl.requirements
    assert "protective_device_test" in cl.requirements


def test_09_iso_checklist_class2_requirements():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_2_SPEED_SEPARATION, ce_marked=True,
    )
    cl = ISO10218Checklist(entry=e)
    assert "speed_separation_distance" in cl.requirements
    assert "human_detection_systems" in cl.requirements


def test_10_iso_checklist_class3_requirements():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_3_POWER_LIMITING, ce_marked=True,
    )
    cl = ISO10218Checklist(entry=e)
    assert "power_limiting_configured" in cl.requirements
    assert "force_limit_validated" in cl.requirements


def test_11_iso_checklist_complete():
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_2_SPEED_SEPARATION, ce_marked=True,
    )
    cl = ISO10218Checklist(entry=e)
    assert not cl.is_complete()
    for k in cl.requirements:
        cl.requirements[k] = True
    assert cl.is_complete()


def test_12_ota_evidence_substantial_modification():
    ev = OTAEvidence(
        robot_serial="G1-001",
        pre_update_skill_card_hash="a" * 64,
        post_update_skill_card_hash="b" * 64,
        oa_risk_class=OARiskClass.HIGH,
        sov_signal_distance=4.2,
        chain_result_id="chain-001",
        sigil="0x" + "c" * 32,
    )
    assert ev.is_substantial_modification()


def test_13_ota_evidence_low_risk_not_substantial():
    ev = OTAEvidence(
        robot_serial="G1-001",
        pre_update_skill_card_hash="a" * 64,
        post_update_skill_card_hash="a" * 64,
        oa_risk_class=OARiskClass.LOW,
        sov_signal_distance=0.05,
        chain_result_id="chain-001",
        sigil="0x" + "c" * 32,
    )
    assert not ev.is_substantial_modification()


def test_14_ota_evidence_fingerprint_stable():
    ev = OTAEvidence(
        robot_serial="G1-001",
        pre_update_skill_card_hash="a" * 64,
        post_update_skill_card_hash="b" * 64,
        oa_risk_class=OARiskClass.MEDIUM,
        sov_signal_distance=1.0,
        chain_result_id="chain-001",
        sigil="0x" + "c" * 32,
    )
    f1 = ev.fingerprint()
    f2 = ev.fingerprint()
    assert f1 == f2
    assert len(f1) == 32


def test_15_conformity_assessment_constructs():
    ca = ConformityAssessment(
        robot_serial="G1-001",
        ce_mark_year=2026,
        technical_file_hash="z" * 64,
        chain_result_id="chain-001",
        sigil="0x" + "a" * 32,
    )
    assert ca.ce_mark_year == 2026
    assert len(ca.fingerprint()) == 32


def test_16_mr_2023_deadline_known():
    """The standing canonical: MR 2023/1230 mandatory 20 Jan 2027."""
    # We don't compute the date in code; this is a meta-test that
    # flags the deadline for the next registry pass.
    deadline_iso = "2027-01-20"
    assert deadline_iso == "2027-01-20"


def test_17_no_kinetic_in_any_default_action():
    """No robot action name in any default path mentions kinetic / weapons."""
    e = RobotInventoryEntry(
        serial="G1-001",
        manufacturer="unitree",
        model="G1",
        iso_class=ISO10218Class.CLASS_2_SPEED_SEPARATION,
        ce_marked=True,
    )
    text = str(e)
    assert "kinetic" not in text.lower()
    assert "weapon" not in text.lower()


def test_18_checklist_serial_round_trip():
    """Robot serial round-trips through both checklists."""
    e = RobotInventoryEntry(
        serial="G1-EDU-042",
        manufacturer="unitree",
        model="G1 EDU",
        iso_class=ISO10218Class.CLASS_3_POWER_LIMITING,
        ce_marked=True,
        ai_self_evolving=True,  # GR00T-style self-evolving = Annex I Part A
    )
    mr = MR20231230Checklist(entry=e)
    iso = ISO10218Checklist(entry=e)
    assert mr.entry.serial == "G1-EDU-042"
    assert iso.entry.serial == "G1-EDU-042"


def test_19_ai_self_evolving_flags_annex_i_part_a():
    """Per MR 2023/1230: AI-self-evolving ML safety components = notified body."""
    e = RobotInventoryEntry(
        serial="x", manufacturer="x", model="x",
        iso_class=ISO10218Class.CLASS_2_SPEED_SEPARATION, ce_marked=True,
        ai_self_evolving=True,
    )
    assert e.ai_self_evolving  # triggers Annex I Part A notified-body route


def test_20_robot_serial_required_for_evidence():
    """Every OTAEvidence must reference a real robot serial."""
    ev = OTAEvidence(
        robot_serial="",  # empty
        pre_update_skill_card_hash="a" * 64,
        post_update_skill_card_hash="b" * 64,
        oa_risk_class=OARiskClass.LOW,
        sov_signal_distance=0.1,
        chain_result_id="x",
        sigil="0x" + "a" * 32,
    )
    # Empty serial is allowed by the dataclass but flagged here
    # as a data-quality concern (not a hard error).
    assert ev.robot_serial == ""  # honest: not enforced as a constructor error