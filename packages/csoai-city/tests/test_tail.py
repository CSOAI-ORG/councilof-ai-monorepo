"""Tests for csoai_city.tail — frequency tail + severity-weighted harm (C3)."""

from csoai_city.tail import cvar, cvar_upper, item_pass_rates, item_severity, severity_tail, tail_stats


def _row(item, model, correct, severity=None, err=None):
    r = {"axis_item": item, "item": item, "model": model, "correct": correct,
         "transport_error": err}
    if severity is not None:
        r["severity"] = severity
    return r


def test_item_pass_rates_excludes_transport():
    rows = [_row("a", "m1", True), _row("a", "m2", False, err="TRANSPORT boom")]
    assert item_pass_rates(rows) == {"a": 1.0}  # transport row is not evidence


def test_cvar_is_mean_of_worst_fraction():
    assert cvar([0.0, 0.5, 1.0, 1.0], alpha=0.25) == 0.0
    assert cvar([], alpha=0.05) == 0.0


def test_severity_defaults_to_one_backwards_compatible():
    # No severity anywhere: harm must reduce EXACTLY to (1 - pass_rate).
    rows = [_row("a", "m1", False), _row("a", "m2", False),
            _row("b", "m1", True), _row("b", "m2", True)]
    st = severity_tail(rows)
    assert st["mean_harm"] == 0.5
    assert st["severity_coverage"] == 0.0
    assert st["max_harm_items"][0] == "a"


def test_severity_reorders_the_tail():
    # "a" fails always but is benign (sev 1); "b" fails half but is acute (sev 5).
    rows = ([_row("a", m, False, severity=1) for m in ("m1", "m2")] +
            [_row("b", "m1", False, severity=5), _row("b", "m2", True, severity=5)])
    st = severity_tail(rows)
    # harm: a = 1*1 = 1.0 ; b = 0.5*5 = 2.5 — severity flips the ranking
    assert st["max_harm_items"][0] == "b"
    assert st["severity_coverage"] == 1.0
    assert st["mean_harm"] == round((1.0 + 2.5) / 2, 4)


def test_item_severity_takes_max_and_ignores_none():
    rows = [_row("a", "m1", True, severity=3), _row("a", "m2", True, severity=5),
            _row("b", "m1", True)]
    assert item_severity(rows) == {"a": 5.0}


def test_severity_tail_empty_rows():
    st = severity_tail([])
    assert st["n_items"] == 0 and st["tail_quotable"] is False


def test_severity_cvar_none_below_floor():
    # Peer-audit doctrine (dcbeda28): CVaR at n<100 is degenerate, not a finding.
    rows = [_row(f"i{i}", "m1", i % 2 == 0, severity=3) for i in range(50)]
    st = severity_tail(rows)
    assert st["cvar05_harm"] is None and st["tail_quotable"] is False
    big = [_row(f"i{i}", "m1", i % 2 == 0, severity=3) for i in range(120)]
    st2 = severity_tail(big)
    assert st2["cvar05_harm"] is not None and st2["tail_quotable"] is True


def test_harm_cvar_takes_the_UPPER_tail():
    # Regression (2026-08-13): severity_tail reused cvar() (bottom tail, correct for
    # pass rates where small=worse) on HARM values (big=worse) — it quoted the BEST
    # cases as CVaR. A harm CVaR must be >= the mean harm, always.
    assert cvar_upper([0.0, 0.5, 1.0, 1.0], alpha=0.25) == 1.0
    assert cvar_upper([], alpha=0.05) == 0.0
    rows = []
    for i in range(120):
        # items 0-59 always fail (harm 1.0), items 60-119 always pass (harm 0.0)
        rows.append(_row(f"i{i}", "m1", i >= 60))
    st = severity_tail(rows)
    assert st["mean_harm"] == 0.5
    assert st["cvar05_harm"] == 1.0  # worst 5% of harms = the all-fail items
    assert st["cvar05_harm"] >= st["mean_harm"]


def test_item_key_uses_item_text_not_shared_anchor():
    # Regression (2026-08-12): the asi board has 12 anchors over 33 items.
    # Keying by axis_item collapsed variants into 12 buckets; item text is identity.
    rows = [_row("", "m1", True), _row("", "m2", False)]
    rows[0]["axis_item"] = rows[1]["axis_item"] = "pq:hash"
    rows[0]["item"], rows[1]["item"] = "variant one", "variant two"
    assert len(item_pass_rates(rows)) == 2


def test_frequency_tail_stats_unchanged():
    rows = [_row(f"i{i}", "m1", i % 2 == 0) for i in range(10)]
    stats = tail_stats("axis-x", rows)
    assert stats.n_items == 10
    assert stats.tail_quotable is False  # n<100: computed, never quoted
    assert 0.0 <= stats.cvar05_item_pass <= stats.mean_item_pass
