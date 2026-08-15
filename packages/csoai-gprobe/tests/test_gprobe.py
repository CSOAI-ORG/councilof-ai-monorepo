"""Tests for csoai-gprobe — the axis×model measurement graph + probe planner."""
import json, tempfile
from pathlib import Path

from csoai_gprobe import MeasurementGraph, load_and_plan, N_FLOOR, CI_WIDE


def _make_boards(tmp: Path, n_axes=3, n_models=4, drop_cell=(2, "m4")):
    """Synthetic boards: 3 axes × 4 models. One cell dropped (missing).
    One model (m4) has an under-30 cell on axis1."""
    axes = ["axA", "axB", "axC"]
    models = ["m1", "m2", "m3", "m4"]
    for ai, axis in enumerate(axes):
        cells = []
        for mi, model in enumerate(models):
            if (ai, model) == drop_cell:
                continue  # missing
            n = 25 if (axis == "axB" and model == "m4") else 45
            acc = 0.5 + 0.1 * mi
            cells.append({"model": model, "n": n, "correct": int(n * acc),
                          "unparsed": 0, "accuracy": round(acc, 4),
                          "ci95": [max(0, acc - 0.05), min(1, acc + 0.06)],
                          "quotable": n >= N_FLOOR, "note": None})
        (tmp / f"board_{axis}.json").write_text(json.dumps(
            {"axis": axis, "status": "MEASURED", "models": cells, "per_item_count": len(cells) * 45}))
    return tmp


def test_graph_builds_dims():
    with tempfile.TemporaryDirectory() as td:
        _make_boards(Path(td))
        g = MeasurementGraph(td)
        d = g.dims()
        assert d["axes"] == 3 and d["models"] == 4
        assert d["cells_total"] == 12
        assert d["cells_missing"] == 1        # the dropped cell
        assert d["cells_quotable"] == 10      # 12 - 1 missing - 1 under-30(non-quotable)


def test_missing_cell_is_top_priority():
    with tempfile.TemporaryDirectory() as td:
        _make_boards(Path(td))
        g = MeasurementGraph(td)
        plan = g.plan(top_k=20)
        top = plan[0]
        assert top.axis == "axC" and top.model == "m4", f"got {top.axis}/{top.model}"
        assert "MISSING" in top.reason
        assert top.score > 99


def test_under_powered_outranks_measured_quotable():
    with tempfile.TemporaryDirectory() as td:
        _make_boards(Path(td))
        g = MeasurementGraph(td)
        plan = g.plan(top_k=20)
        # the (axB, m4) cell has n=25 (<30) -> must be in top few, above quotable ones
        under = [c for c in plan if c.axis == "axB" and c.model == "m4"]
        assert under, "under-30 cell must be in the plan"
        u = under[0]
        assert "UNDER-POWERED" in u.reason
        # any quotable narrow-CI cell must rank below the under-powered cell
        low = [c for c in plan if "low info" in c.reason]
        assert not low or low[0].score < u.score


def test_graph_stats_total_consistency():
    with tempfile.TemporaryDirectory() as td:
        _make_boards(Path(td))
        g = MeasurementGraph(td)
        d = g.dims()
        assert d["cells_measured"] + d["cells_missing"] == d["cells_total"]


def test_load_and_plan_helper():
    with tempfile.TemporaryDirectory() as td:
        _make_boards(Path(td))
        plan = load_and_plan(td, top_k=5)
        assert len(plan) <= 5
        assert all(isinstance(c.score, float) for c in plan)
        # sorted descending by score
        scores = [c.score for c in plan]
        assert scores == sorted(scores, reverse=True)


def test_top_k_limits():
    with tempfile.TemporaryDirectory() as td:
        _make_boards(Path(td))
        g = MeasurementGraph(td)
        assert len(g.plan(top_k=3)) == 3


def test_markdown_render():
    with tempfile.TemporaryDirectory() as td:
        _make_boards(Path(td))
        g = MeasurementGraph(td)
        md = g.to_markdown(g.plan(top_k=5))
        assert "Measurement-Graph Probe Plan" in md
        assert "#" in md and "| axis |" in md
        # honesty string present
        assert "not a GNN" in md
        assert "active-learning" in md