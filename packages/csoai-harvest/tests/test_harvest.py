"""Tests for csoai-harvest — license-governed intake machine."""
from __future__ import annotations

import pytest
from csoai_harvest import (
    LICENSE_ALLOW,
    LICENSE_DENY,
    LICENSE_QUARANTINE,
    TRACKED_ORGS,
    HarvestVerdict,
    TrackedOrg,
    Verdict,
    gate_license,
    render_regogo_policy,
)


def test_01_apache_20_absorb():
    """Apache 2.0 (NVIDIA Isaac GR00T code, mergekit) → ABSORB."""
    v = gate_license("Apache-2.0", org="NVIDIA", repo="Isaac-GR00T")
    assert v.verdict == Verdict.ABSORB
    assert v.is_actionable()


def test_02_mit_absorb():
    v = gate_license("MIT")
    assert v.verdict == Verdict.ABSORB


def test_03_bsd3_absorb():
    """BSD-3-Clause (unitree_rl_gym) → ABSORB."""
    v = gate_license("BSD-3-Clause", org="unitreerobotics", repo="unitree_rl_gym")
    assert v.verdict == Verdict.ABSORB


def test_04_ccby40_absorb():
    v = gate_license("CC-BY-4.0")
    assert v.verdict == Verdict.ABSORB


def test_05_agpl_deny():
    """AGPL viral license — NEVER absorb."""
    v = gate_license("AGPL-3.0")
    assert v.verdict == Verdict.DENY
    assert not v.is_actionable()


def test_06_cc_by_nc_deny():
    """CC-BY-NC-* — non-commercial, deny."""
    for lic in ("CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-NC-ND-4.0"):
        v = gate_license(lic)
        assert v.verdict == Verdict.DENY, f"{lic} should DENY"


def test_07_sspl_deny():
    v = gate_license("SSPL-1.0")
    assert v.verdict == Verdict.DENY


def test_08_commons_clause_deny():
    v = gate_license("Commons-Clause")
    assert v.verdict == Verdict.DENY


def test_09_oxe_quarantine():
    """Open X-Embodiment = 60+ upstream licenses → QUARANTINE."""
    v = gate_license("Open-X-Embodiment")
    assert v.verdict == Verdict.QUARANTINE
    assert v.is_actionable()  # actionable, just needs review


def test_10_unknown_license_quarantines_by_default():
    """Article 0 dogfood: unknown licenses go to QUARANTINE, never auto-ABSORB."""
    v = gate_license("SomeUnknown-License-1.0")
    assert v.verdict == Verdict.QUARANTINE


def test_11_research_only_quarantine():
    v = gate_license("Research-Only")
    assert v.verdict == Verdict.QUARANTINE


def test_12_nvidia_open_model_license_absorb():
    """NVIDIA Open Model License — commercially licensable per Isaac GR00T."""
    v = gate_license("NVIDIA-Open-Model-License")
    assert v.verdict == Verdict.ABSORB


def test_13_llama_community_absorb():
    v = gate_license("Llama-3.3-Community")
    assert v.verdict == Verdict.ABSORB


def test_14_tracked_orgs_count():
    """10 tracked orgs per Master Part X.1."""
    assert len(TRACKED_ORGS) == 10


def test_15_tracked_orgs_include_nvidia_unitree_huggingface():
    names = {o.name for o in TRACKED_ORGS}
    assert "NVIDIA" in names
    assert "unitreerobotics" in names
    assert "huggingface" in names
    assert "arcee-ai" in names


def test_16_each_tracked_org_has_a_why():
    for o in TRACKED_ORGS:
        assert o.why, f"org {o.name} missing rationale"


def test_17_tracked_orgs_can_have_repos():
    nvidia = next(o for o in TRACKED_ORGS if o.name == "NVIDIA")
    assert "Isaac-GR00T" in nvidia.repos


def test_18_license_lists_are_disjoint():
    """Allow ∩ Deny = ∅, Allow ∩ Quarantine = ∅, Deny ∩ Quarantine = ∅."""
    assert LICENSE_ALLOW & LICENSE_DENY == set()
    assert LICENSE_ALLOW & LICENSE_QUARANTINE == set()
    assert LICENSE_DENY & LICENSE_QUARANTINE == set()


def test_19_rego_policy_renders():
    """The Rego policy must render with all three lists."""
    text = render_regogo_policy()
    assert "package sovos.harvest.license" in text
    assert "allow" in text
    assert "deny" in text
    assert "quarantine" in text
    assert "Apache-2.0" in text
    assert "AGPL-3.0" in text


def test_20_rego_policy_lists_match_python():
    """The Rego policy lists must match the Python constants.

    This is the cross-implementation consistency rule (the same one
    Article 0 enforces — see test_az18 in sovos-article-zero).
    """
    text = render_regogo_policy()
    # extract allow block content
    import re
    allow_block = re.search(r"allow := \{(.+?)\}\n", text, re.DOTALL)
    assert allow_block, "could not extract allow block"
    found = re.findall(r'"([^"]+)"', allow_block.group(1))
    assert set(found) == LICENSE_ALLOW, (
        f"Rego allow != Python: missing {LICENSE_ALLOW - set(found)}, "
        f"extra {set(found) - LICENSE_ALLOW}"
    )


def test_21_harvest_verdict_dataclass():
    v = HarvestVerdict(org="NVIDIA", repo="x", license="MIT", verdict=Verdict.ABSORB, reason="ok")
    assert v.org == "NVIDIA"
    assert v.verdict == Verdict.ABSORB
    assert v.is_actionable()


def test_22_known_kinetic_targets_not_in_tracked_orgs():
    """No tracked org name or repo should reference kinetic / weapons patterns."""
    bad = ["kinetic", "kill", "weapon", "strike package", "find-fix-finish"]
    for o in TRACKED_ORGS:
        for term in bad:
            assert term not in o.name.lower()
            assert term not in o.why.lower()
            for r in o.repos:
                assert term not in r.lower()