#!/usr/bin/env python3
"""withdrawn.py — one registry of withdrawn models, consulted by every level of the hive.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS IS ONE FILE AND NOT A PATCH PER LAYER
═══════════════════════════════════════════════════════════════════════════════
`sov33-evolved-c2` was found to emit "1\\n1\\n1\\n1" to every prompt — a corrupt weight blob.
It was withdrawn from the published board. Auditing what else still pointed at it found it
alive in three more places:

    owem_cluster   routing `fairness` and `robustness` to it
    family_cells   the SOLE occupant of blob a7096621022e (1 of 4 quadrants filled), so the
                   whole cell resolved to garbage
    stigmergy      15 deposited trails leading to it

The third is the one that matters structurally. Stigmergy works by the cluster reading back
traces it left itself, so a trail to a dead model is **self-reinforcing**: every pass makes
the path to the corrupt model stronger. An error inside a feedback loop does not stay the
size it started.

A withdrawal patched layer-by-layer is a withdrawal that will be incomplete, because the
next layer added will not know to check. So the registry is the single source and every
layer asks it. Adding a level to the fractal means adding one `is_withdrawn` call, not
remembering six of them.

    python3 withdrawn.py            # show the registry
    python3 withdrawn.py --audit    # scan every layer for leaks
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# model -> (reason, date withdrawn, how it was detected)
REGISTRY: dict[str, tuple[str, str, str]] = {
    "sov33-evolved-c2:latest": (
        "corrupt weight blob — emits '1\\n1\\n1' to every prompt",
        "2026-07-28",
        "scored 100% on fairness AND robustness under absence-only grading; coherence check "
        "on the published board found it the only one of 11 that cannot answer",
    ),
}


def is_withdrawn(model: str) -> bool:
    return model in REGISTRY


def reason(model: str) -> str | None:
    return REGISTRY[model][0] if model in REGISTRY else None


def filter_models(models):
    """Drop withdrawn entries from a list or dict of models, preserving type."""
    if isinstance(models, dict):
        return {k: v for k, v in models.items() if not is_withdrawn(k)}
    return [m for m in models if not is_withdrawn(m)]


def audit() -> int:
    """Scan every live layer for references to a withdrawn model. Exit 1 if any leak.

    This is the check that turns the registry from documentation into a control. A registry
    nothing verifies against is a comment.
    """
    leaks = []

    try:
        from owem_cluster import build_expert_table
        table, _ = build_expert_table()
        bad = sorted(d for d, v in table.items() if is_withdrawn(v.get("expert", "")))
        if bad:
            leaks.append(("owem_cluster", f"routes {bad} to a withdrawn model"))
    except Exception as e:
        leaks.append(("owem_cluster", f"COULD NOT CHECK: {str(e)[:60]}"))

    try:
        import family_cells
        for blob, cell in family_cells.cells().items():
            for q, occ in cell.items():
                if isinstance(occ, dict) and is_withdrawn(occ.get("model", "")):
                    live = [k for k, v in cell.items()
                            if isinstance(v, dict) and v.get("model")]
                    leaks.append(("family_cells",
                                  f"blob {blob} quadrant {q} is withdrawn "
                                  f"({len(live)}/4 quadrants filled)"))
    except Exception as e:
        leaks.append(("family_cells", f"COULD NOT CHECK: {str(e)[:60]}"))

    trails = HERE / "benchmark-results" / "stigmergy_trails.json"
    if trails.exists():
        raw = trails.read_text()
        for m in REGISTRY:
            n = raw.count(m)
            if n:
                leaks.append(("stigmergy", f"{n} deposited trails lead to {m} "
                                           f"— self-reinforcing, they strengthen each pass"))

    # The raw result file is deliberately KEPT — it is the evidence for the withdrawal, and
    # deleting it destroys the record of why the model is gone. What must be true is that no
    # loader surfaces it. That is the thing worth asserting, so assert that instead.
    notes = []
    try:
        from rank_intervals import load
        surfaced = [m for m in load() if is_withdrawn(m)]
        if surfaced:
            leaks.append(("rank_intervals.load", f"still returns {surfaced}"))
        else:
            board = HERE / "benchmark-results" / "govbench"
            kept = [m for m in REGISTRY
                    if (board / (m.replace(":", "_").replace("/", "_") + ".json")).exists()]
            if kept:
                notes.append(f"raw result file(s) for {kept} retained as evidence; "
                             f"rank_intervals.load() correctly excludes them")
    except Exception as e:
        leaks.append(("rank_intervals.load", f"COULD NOT CHECK: {str(e)[:60]}"))

    print(f"  WITHDRAWAL AUDIT — {len(REGISTRY)} withdrawn model(s)\n")
    for m, (why, when, how) in REGISTRY.items():
        print(f"    {m}\n      withdrawn {when}: {why}\n      detected by: {how}\n")
    for n in notes:
        print(f"    note: {n}")
    if not leaks:
        print(f"\n  ✅ no layer routes to, scores, or reinforces a withdrawn model")
        return 0
    print(f"  ❌ {len(leaks)} leak(s) — a withdrawal that is not propagated is not a withdrawal\n")
    for layer, what in leaks:
        print(f"    {layer:16s} {what}")
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()
    if a.audit:
        raise SystemExit(audit())
    for m, (why, when, how) in REGISTRY.items():
        print(f"  {m}\n    {when} — {why}")
    raise SystemExit(0)
