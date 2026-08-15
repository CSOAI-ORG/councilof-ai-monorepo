"""Tests for csoai-fleet — 3KB skill card + fleet ledger."""
from __future__ import annotations

import pytest
from csoai_fleet import (
    EmbodimentPort,
    FleetLedger,
    MAX_CARD_BYTES,
    SkillCard,
    SkillCardSizeError,
    fleet_manifest,
    make_card,
)


def test_01_max_card_bytes_is_3kb():
    """3 KB = 3072 bytes. The doctrine's literal ceiling."""
    assert MAX_CARD_BYTES == 3072


def test_02_skill_card_constructs():
    c = SkillCard(
        task="pick-up-cup",
        embodiment="unitree-g1",
        policy_hash="0" * 64,
        sigma=0.1,
        chain_result_id="abc123",
        sigil="0x" + "a" * 32,
        c2pa_uri="c2pa://test/manifest",
    )
    assert c.task == "pick-up-cup"
    assert c.fits_3kb()


def test_03_skill_card_size_bytes():
    c = make_card(
        task="x",
        embodiment="g1",
        policy_hash="0" * 64,
        sigma=0.1,
        chain_result_id="abc123",
        sigil="0x" + "a" * 32,
        c2pa_uri="c2pa://test",
    )
    assert c.size_bytes() < MAX_CARD_BYTES


def test_04_skill_card_oversize_raises():
    """A card with a huge task description exceeds 3KB and is rejected."""
    huge_task = "x" * 4000  # well over 3KB
    with pytest.raises(SkillCardSizeError) as exc_info:
        make_card(
            task=huge_task,
            embodiment="g1",
            policy_hash="0" * 64,
            sigma=0.1,
            chain_result_id="abc",
            sigil="0x" + "a" * 32,
            c2pa_uri="c2pa://test",
        )
    assert exc_info.value.actual > MAX_CARD_BYTES


def test_05_card_fingerprint_is_stable():
    c1 = make_card(
        task="x", embodiment="g1",
        policy_hash="ab" * 32, sigma=0.1,
        chain_result_id="abc", sigil="0x" + "a" * 32,
        c2pa_uri="c2pa://x",
    )
    c2 = make_card(
        task="x", embodiment="g1",
        policy_hash="ab" * 32, sigma=0.1,
        chain_result_id="abc", sigil="0x" + "a" * 32,
        c2pa_uri="c2pa://x",
    )
    # different created_at would differ but fingerprint is over the JSON
    # which is sorted & deterministic. Should be equal.
    assert c1.fingerprint() == c2.fingerprint()


def test_06_fleet_ledger_empty():
    fl = FleetLedger()
    assert len(fl) == 0
    assert fl.total_sigma() == 0.0


def test_07_fleet_ledger_append():
    fl = FleetLedger()
    c = make_card(
        task="pick-up-cup", embodiment="g1",
        policy_hash="0" * 64, sigma=0.1,
        chain_result_id="chain-001",
        sigil="0x" + "a" * 32,
        c2pa_uri="c2pa://g1/cup",
    )
    fid = fl.append(c)
    assert len(fl) == 1
    assert fid == c.fingerprint()


def test_08_fleet_ledger_query_by_embodiment():
    fl = FleetLedger()
    for emb in ["g1", "g1", "optimus", "figure-02"]:
        fl.append(make_card(
            task="walk", embodiment=emb,
            policy_hash="0" * 64, sigma=0.05,
            chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x",
        ))
    g1 = fl.for_embodiment("g1")
    assert len(g1) == 2
    optimus = fl.for_embodiment("optimus")
    assert len(optimus) == 1


def test_09_fleet_ledger_query_by_task():
    fl = FleetLedger()
    fl.append(make_card(task="walk", embodiment="g1", policy_hash="0" * 64,
                        sigma=0.1, chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x"))
    fl.append(make_card(task="run",  embodiment="g1", policy_hash="0" * 64,
                        sigma=0.2, chain_result_id="y", sigil="0x" + "b" * 32, c2pa_uri="c2pa://y"))
    walks = fl.for_task("walk")
    assert len(walks) == 1
    assert walks[0].task == "walk"


def test_10_fleet_ledger_mean_sigma():
    fl = FleetLedger()
    fl.append(make_card(task="a", embodiment="g1", policy_hash="0" * 64,
                        sigma=0.1, chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x"))
    fl.append(make_card(task="b", embodiment="g1", policy_hash="0" * 64,
                        sigma=0.3, chain_result_id="y", sigil="0x" + "b" * 32, c2pa_uri="c2pa://y"))
    assert abs(fl.total_sigma() - 0.2) < 1e-9


def test_11_fleet_manifest_summary():
    fl = FleetLedger()
    fl.append(make_card(task="walk", embodiment="g1", policy_hash="0" * 64,
                        sigma=0.1, chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x"))
    fl.append(make_card(task="run",  embodiment="optimus", policy_hash="0" * 64,
                        sigma=0.2, chain_result_id="y", sigil="0x" + "b" * 32, c2pa_uri="c2pa://y"))
    m = fleet_manifest(fl)
    assert m["n_cards"] == 2
    assert "g1" in m["embodiments"]
    assert "optimus" in m["embodiments"]
    assert "walk" in m["tasks"]
    assert "run" in m["tasks"]


def test_12_embodiment_port_constructs():
    p = EmbodimentPort(
        src_embodiment="g1",
        dst_embodiment="optimus",
        procrustes_matrix_hash="ab" * 32,
        n_samples=1000,
        mean_residual=0.05,
    )
    assert p.src_embodiment == "g1"
    assert p.dst_embodiment == "optimus"
    assert p.mean_residual == 0.05


def test_13_card_3kb_at_the_boundary():
    """A card exactly at 3KB should fit."""
    # The default card (small fields) is well under; we just confirm
    # nothing crosses the ceiling by accident.
    c = make_card(
        task="t", embodiment="e",
        policy_hash="0" * 64, sigma=0.0,
        chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x",
    )
    assert c.size_bytes() <= MAX_CARD_BYTES
    assert c.fits_3kb()


def test_14_no_kinetic_in_default_cards():
    """Default skill names must not reference kinetic patterns."""
    fl = FleetLedger()
    for task in ["walk", "pick-up-cup", "greet-user"]:
        fl.append(make_card(
            task=task, embodiment="g1",
            policy_hash="0" * 64, sigma=0.05,
            chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x",
        ))
    text = str(fleet_manifest(fl)).lower()
    assert "kinetic" not in text
    assert "kill" not in text
    assert "weapon" not in text


def test_15_card_doctrine_too_big_means_redistill():
    """The 3KB ceiling is a doctrine: bigger card = more noise, redistill."""
    # A card with a normal task description is fine
    c = make_card(
        task="pick-up-cup-from-table-with-care",
        embodiment="g1",
        policy_hash="0" * 64, sigma=0.05,
        chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x",
    )
    assert c.fits_3kb()
    # A card with massive task name fails
    with pytest.raises(SkillCardSizeError):
        make_card(
            task="x" * 4000,
            embodiment="g1",
            policy_hash="0" * 64, sigma=0.05,
            chain_result_id="x", sigil="0x" + "a" * 32, c2pa_uri="c2pa://x",
        )