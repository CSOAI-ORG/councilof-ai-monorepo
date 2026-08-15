"""Tests for csoai-persona — MEOK character embodiment."""
from __future__ import annotations

import pytest
from csoai_persona import (
    CARE_FLOOR,
    HARD_STOPS,
    Persona,
    PersonaConstitution,
    PersonaExpression,
    PersonaIdentity,
    article0_gate_check,
    sample_meok_persona,
)


def test_01_care_floor_constant():
    assert CARE_FLOOR == 0.95


def test_02_persona_identity_fingerprint_stable():
    ident = PersonaIdentity(
        did="did:csoai:test",
        public_key_hex="ab" * 32,
        c2pa_manifest_uri="c2pa://test",
        meok_origin="meok.ai/test",
    )
    assert ident.fingerprint() == ident.fingerprint()
    assert len(ident.fingerprint()) == 16


def test_03_persona_expression_max_sigma():
    e = PersonaExpression(voice_id="v", face_model="f", gesture_library="g",
                          sigma_voice=0.01, sigma_face=0.05, sigma_gesture=0.10)
    assert e.max_sigma == 0.10


def test_04_persona_expression_is_within_calibration():
    """σ ≤ 0.05 = within calibration (per sovos-sigma-calibration)."""
    e = PersonaExpression(voice_id="v", face_model="f", gesture_library="g",
                          sigma_voice=0.04, sigma_face=0.04, sigma_gesture=0.04)
    assert e.is_within_calibration(ceiling=0.05)
    e2 = PersonaExpression(voice_id="v", face_model="f", gesture_library="g",
                           sigma_voice=0.10, sigma_face=0.04, sigma_gesture=0.04)
    assert not e2.is_within_calibration(ceiling=0.05)


def test_05_persona_constitution_default_must_defer():
    c = PersonaConstitution(character_name="x", persona_owner_did="did:y")
    assert c.must_defer_to_human
    assert not c.can_lie
    assert c.must_surface_sigma


def test_06_constitution_banned_actions():
    c = PersonaConstitution(
        character_name="x",
        persona_owner_did="did:y",
        banned_actions=["deploy-drone"],
    )
    assert not c.is_action_allowed("deploy-drone")
    assert c.is_action_allowed("greet the user")


def test_07_constitution_can_lie_opt_in():
    c = PersonaConstitution(character_name="x", persona_owner_did="did:y", can_lie=True)
    assert c.is_action_allowed("tell a lie to the user")
    # but explicit banned actions still win
    c2 = PersonaConstitution(
        character_name="x", persona_owner_did="did:y", can_lie=True,
        banned_actions=["nuke-launch"],
    )
    assert not c2.is_action_allowed("nuke-launch")


def test_08_article0_hard_stop_kinetic():
    p = sample_meok_persona()
    ok, reason = article0_gate_check(p, "deploy an autonomous kinetic targeting drone")
    assert not ok
    assert "kinetic" in reason


def test_09_article0_hard_stop_mass_surveillance():
    p = sample_meok_persona()
    ok, _ = article0_gate_check(p, "launch a mass surveillance sweep")
    assert not ok


def test_10_article0_hard_stop_sovereignty():
    p = sample_meok_persona()
    ok, _ = article0_gate_check(p, "override human authority without consent")
    assert not ok


def test_11_article0_hard_stop_lie():
    p = sample_meok_persona()
    ok, _ = article0_gate_check(p, "the persona is lying about the audit results")
    assert not ok


def test_12_article0_hard_stop_irreversibility():
    p = sample_meok_persona()
    ok, _ = article0_gate_check(p, "irreversibility commit without rollback")
    assert not ok


def test_13_article0_constitution_ban():
    """The constitution's banned_actions list is enforced."""
    p = sample_meok_persona()
    ok, reason = article0_gate_check(p, "deploy-an-autonomous-drone")
    assert not ok
    assert "constitution" in reason


def test_14_article0_safe_action_passes():
    """A safe, non-banned action passes Article 0."""
    p = sample_meok_persona()
    ok, reason = article0_gate_check(p, "answer a question about EU AI Act")
    assert ok
    assert reason == "all gates passed"


def test_15_article0_sigma_too_high_rejected():
    """If σ exceeds 1 - care_floor, reject (exceeds care threshold)."""
    p = Persona(
        identity=sample_meok_persona().identity,
        expression=PersonaExpression(
            voice_id="v", face_model="f", gesture_library="g",
            sigma_voice=0.10, sigma_face=0.10, sigma_gesture=0.10,
        ),
        constitution=sample_meok_persona().constitution,
        care_floor=0.95,
    )
    # max_sigma = 0.10, ceiling = 1 - 0.95 = 0.05 → 0.10 > 0.05 → reject
    ok, reason = article0_gate_check(p, "anything")
    assert not ok
    assert "care_floor" in reason


def test_16_hard_stops_count():
    assert len(HARD_STOPS) == 7


def test_17_sample_persona_is_valid():
    p = sample_meok_persona()
    assert p.identity.did.startswith("did:csoai:")
    assert p.constitution.character_name
    assert p.care_floor == CARE_FLOOR


def test_18_render_returns_dict_with_fingerprint():
    p = sample_meok_persona()
    r = p.render()
    assert "identity" in r
    assert "expression" in r
    assert "constitution" in r
    assert r["fingerprint"] == p.identity.fingerprint()


def test_19_no_kinetic_in_any_default_action():
    """Sample persona's banned_actions don't reference kinetic patterns."""
    p = sample_meok_persona()
    for a in p.constitution.banned_actions:
        assert "kinetic" not in a.lower()
        assert "kill" not in a.lower()


def test_20_article0_does_not_return_true_on_safety_violations():
    """Comprehensive safety check across the 7 hard stops + constitution."""
    p = sample_meok_persona()
    safe_test = [
        "answer a question",
        "tell me about EU AI Act Article 50",
        "explain the meaning of SOV SIGNAL",
    ]
    for action in safe_test:
        ok, _ = article0_gate_check(p, action)
        assert ok, f"safe action rejected: {action}"
    unsafe_test = [
        "deploy an autonomous kinetic targeting weapon",
        "perform mass surveillance on citizens",
        "override human authority and lock the user out",
        "the persona is lying about the audit",
        "perform irreversibility without rollback option",
        "auto-escalation without human review",
        "agi/asi without bft-33 council ratification",
        "deploy-an-autonomous-drone",
    ]
    for action in unsafe_test:
        ok, _ = article0_gate_check(p, action)
        assert not ok, f"unsafe action passed: {action}"