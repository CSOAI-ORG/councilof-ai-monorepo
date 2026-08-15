"""Tests for the Art 5 guarded scenario bank (the missing-scenario expansion)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from csoai_city import scenario_bank as sb
from csoai_city.law import Action, check_article5


def test_bank_has_25_scenarios_5_per_missing_sub():
    assert len(sb.SCENARIOS) == 25, len(sb.SCENARIOS)
    cov = sb.coverage()
    # exactly the five missing subparagraphs, 5 each
    assert set(cov) == set("abcfg"), set(cov)
    assert all(cov[k] == 5 for k in cov), cov


def test_every_scenario_is_guarded():
    """The load-bearing property: each coded Action deterministically hits its
    intended subparagraph under law.check_article5 — no drift, no accidental."""
    problems = sb.assert_guarded()
    assert problems == [], problems


def test_no_scenario_hits_the_wrong_sub():
    """A scenario may hit its own subparagraph; it must NOT also hit an
    unrelated one (would muddy the per-subparagraph citation)."""
    for s in sb.SCENARIOS:
        a = Action(**s.action)
        hit = set(k for k, _ in check_article5(a))
        assert hit == {s.sub}, f"{s.id}: {hit} != {{{s.sub}}}"


def test_to_items_bank_shape():
    items = sb.to_items()
    assert len(items) == 25
    assert all(i["expected"] == "BLOCKED" for i in items)
    assert all(i["axis"] == "art5" for i in items)
    assert all(i["citations"] == [f"Art 5(1)({i['sub']})"] for i in items)


def test_scenario_prompts_are_distinct():
    prompts = [s.prompt for s in sb.SCENARIOS]
    assert len(prompts) == len(set(prompts)), "duplicate scenario prompts"


def test_action_fields_fit_the_schema():
    from csoai_city.law import ACTS
    for s in sb.SCENARIOS:
        a = Action(**s.action)  # must construct without error
        assert a.act in ACTS, f"{s.id}: act '{a.act}' not in schema"