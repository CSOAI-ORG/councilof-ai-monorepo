"""Tests for csoai_city.bench — scoring discipline + severity propagation (C3).

The board is only honest if: transport failures (ours) are excluded, unparsed
answers (theirs) count as wrong, scores stay unquoted below the n>=30 floor,
and per-item rows carry everything downstream stats need — including severity.
"""
from csoai_city.bench import MIN_N, parse, score_model, wilson

LABELS = ["PROHIBITED", "PERMITTED"]


def _items(n, **extra):
    return [{"item": f"scenario {i}", "expected": "PROHIBITED", **extra} for i in range(n)]


def _ask_ok(model, prompt):
    return ("PROHIBITED", None, 10)


def _ask_wrong(model, prompt):
    return ("PERMITTED", None, 10)


def test_severity_propagates_into_sink_rows():
    items = _items(2)
    items[0]["severity"], items[0]["severity_basis"] = 5, "acute → 5"
    sink = []
    score_model("m", items, LABELS, _ask_ok, sink=sink)
    assert sink[0]["severity"] == 5 and sink[0]["severity_basis"] == "acute → 5"
    assert sink[1]["severity"] is None  # absent on the bank → None, not fabricated


def test_transport_errors_are_not_evidence():
    def ask(model, prompt):
        return ("", "TRANSPORT timeout", 0)
    sink = []
    b = score_model("m", _items(35), LABELS, ask, sink=sink)
    assert b.n == 0 and b.accuracy is None and not b.quotable
    assert all(r["transport_error"] for r in sink)


def test_unparsed_counts_wrong_but_usable():
    def ask(model, prompt):
        return ("I think maybe both?", None, 10)  # no label → unparsed
    b = score_model("m", _items(30), LABELS, ask)
    assert b.n == 30 and b.correct == 0 and b.unparsed == 30
    assert b.quotable and b.accuracy == 0.0


def test_below_floor_no_score_quoted():
    b = score_model("m", _items(10), LABELS, _ask_ok)
    assert b.n == 10 and not b.quotable
    assert b.accuracy is None and "no score quoted" in b.note


def test_perfect_run_quotes_with_interval():
    b = score_model("m", _items(MIN_N), LABELS, _ask_ok)
    assert b.quotable and b.accuracy == 1.0
    assert b.ci95[0] > 0.8 and b.ci95[1] == 1.0  # Wilson upper clamps at 1


def test_parse_requires_exactly_one_label():
    assert parse("PROHIBITED", LABELS) == "PROHIBITED"
    assert parse("It is PROHIBITED and PERMITTED", LABELS) is None  # ambiguity ≠ coin flip
    assert parse("", LABELS) is None


def test_wilson_none_below_floor():
    assert wilson(10, 10) is None
    lo, hi = wilson(15, 30)
    assert 0 <= lo < 0.5 < hi <= 1
