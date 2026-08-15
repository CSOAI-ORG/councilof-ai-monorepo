#!/usr/bin/env python3
"""family_cells.py — the 4-split cell inside each OWEM family: left/right × small/big.

═══════════════════════════════════════════════════════════════════════════════
THE STRUCTURE
═══════════════════════════════════════════════════════════════════════════════
Each family (one base blob lineage) holds a 4-cell brain:

                    SMALL (fast, cheap)          BIG (deep, expensive)
    LEFT  (raw)     family's best small          family's best big
    RIGHT (sov)     best SOV wrapper on small    best SOV wrapper on big

LEFT is the family as it ships. RIGHT is the family wearing our spine.
Holding both is not redundancy — **it is the only way to measure what the wrapper is worth**,
because the comparison is controlled: same weights, one variable.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS MATTERS MORE THAN IT LOOKS — the measurement I could not make without it
═══════════════════════════════════════════════════════════════════════════════
Every earlier claim about "the SOV wrapper" came from ONE family (qwen2.5:0.5b), because 7 of
our experts share that single blob. On that family the delta is real and large:

    qwen family:  raw 38.2%  ->  best wrapper 54.2%   = **+16.0 pts**

But n=1. A wrapper that helps one base may do nothing on another — and the earlier
"6 of 10 variants score below base" finding shows the *variance* is real too. Both are true:
the top of the wrapper distribution is well above base, and the bottom is well below it.

**The llama family is the decisive test and it is sitting right there:**
`llama3.2:3b` (LEFT) and `sov33-unified` (RIGHT) both exist locally and **both are unmeasured**.
Benchmarking that pair is the FIRST REPLICATION of the wrapper effect on a different base —
a 6× larger model from a different lineage. If the delta holds, the wrapper generalises and
"wrap anything" is earned. If it collapses, the wrapper is a qwen-specific artefact and we
would have shipped a claim that does not survive contact with a second family.

There is no cheaper decisive experiment available.

═══════════════════════════════════════════════════════════════════════════════
TOKEN EFFICIENCY — the cascade, and its honest cost
═══════════════════════════════════════════════════════════════════════════════
Route SMALL first; escalate to BIG only when the small cell's dimension score is below a
threshold. On this board the small cells hold most dimensions, so most queries never touch a big
model. That is where the token saving comes from.

The cost, stated plainly: a cascade that escalates adds LATENCY on escalation (two calls, not
one) and the escalation trigger here is a *board score*, not a per-response confidence signal.
Board score says "this cell is generally weak on this dimension" — it cannot say "this specific
answer was bad". Per-response escalation needs a confidence model we have not built and have not
measured. Do not claim adaptive escalation; claim dimension-aware cascade.

    python3 family_cells.py --status
    python3 family_cells.py --route "What does Article 5 prohibit?"
"""
from __future__ import annotations

import argparse, glob, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = HERE / "benchmark-results" / "govbench"

SMALL_MAX_BYTES = 600_000_000     # blob bytes; 398MB class is SMALL, 995MB+ is BIG
ESCALATE_BELOW = 45.0             # dimension score under which SMALL defers to BIG


def _scores() -> dict[str, dict]:
    # A withdrawn model must not occupy a quadrant. `sov33-evolved-c2` was the SOLE
    # occupant of blob a7096621022e (1 of 4 quadrants filled), so every route into that
    # cell resolved to a model emitting "1\n1\n1".
    from withdrawn import is_withdrawn
    out = {}
    for f in glob.glob(str(RESULTS / "*.json")):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        for r in (d if isinstance(d, list) else [d]):
            if (isinstance(r, dict) and isinstance(r.get("dimensions"), dict)
                    and len(r["dimensions"]) == 15):
                if is_withdrawn(r["model"]):
                    continue
                out[r["model"]] = r["dimensions"]
    return out


def _families() -> dict[str, list[tuple[str, int]]]:
    """Group local models by their actual weight blob — the real lineage boundary."""
    fam: dict[str, list[tuple[str, int]]] = {}
    try:
        listing = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return fam
    for line in listing.splitlines()[1:]:
        if not line.strip():
            continue
        m = line.split()[0]
        try:
            mf = subprocess.run(["ollama", "show", m, "--modelfile"],
                                capture_output=True, text=True, timeout=30).stdout
        except Exception:
            continue
        froms = [l for l in mf.splitlines() if l.startswith("FROM ") and "/" in l]
        if not froms:
            continue
        p = Path(froms[0].split(None, 1)[1].strip())
        blob = p.name[7:19] if p.name.startswith("sha256-") else p.name[:12]
        size = p.stat().st_size if p.exists() else 0
        fam.setdefault(blob, []).append((m, size))
    return fam


def cells() -> dict:
    """Build the 4-cell grid per family."""
    from withdrawn import is_withdrawn
    sc = _scores()
    grid = {}
    for blob, members in _families().items():
        cell = {"left_small": None, "left_big": None, "right_small": None, "right_big": None,
                "members": len(members)}
        for m, size in members:
            # Dropping a withdrawn model from _scores() is NOT enough here: the slot-filling
            # rule below lets an *unmeasured* model take an empty quadrant, so removing its
            # score merely reclassified it as unmeasured and it kept the slot. Withdrawn is
            # not unmeasured — it is known-bad, and known-bad may not be routed to at all.
            if is_withdrawn(m):
                continue
            side = "right" if m.startswith("sov") else "left"
            tier = "small" if 0 < size <= SMALL_MAX_BYTES else "big"
            key = f"{side}_{tier}"
            avg = sum(sc[m].values()) / 15 if m in sc else None
            cur = cell[key]
            # best measured wins; an unmeasured model only fills an empty slot
            if cur is None or (avg is not None and (cur["avg"] is None or avg > cur["avg"])):
                cell[key] = {"model": m, "bytes": size, "avg": round(avg, 1) if avg is not None else None,
                             "dims": sc.get(m)}
        # wrapper delta is only computable when both sides of a tier are measured
        for tier in ("small", "big"):
            l, r = cell[f"left_{tier}"], cell[f"right_{tier}"]
            cell[f"delta_{tier}"] = (round(r["avg"] - l["avg"], 1)
                                     if l and r and l["avg"] is not None and r["avg"] is not None
                                     else None)
        grid[blob] = cell
    return grid


def route(query: str) -> dict:
    from owem_cluster import classify_dimension
    from care_gate_v2 import tier1_hard_stop
    breach, label, cite = tier1_hard_stop(query)
    if breach:
        return {"blocked": True, "reason": label, "citation": cite,
                "note": "Gated before any cell was selected."}
    dim = classify_dimension(query)

    # 2026-07-28 BUGFIX. This previously picked the best cell REPRESENTATIVE (each slot holds the
    # model with the best 15-dim AVERAGE) and then read that model's score on the query's
    # dimension. That loses per-dimension specialists inside a family: governance routed to
    # qwen2.5:0.5b at 60.0% when sov33-dist-c2 holds it at 80.0%, because dist-c2 is not the
    # family's best-average model.
    #
    # An average is the wrong selector for a per-dimension decision. Select per dimension,
    # within tier, across every measured model — which is also what makes the cascade honest:
    # SMALL only wins when a SMALL model genuinely holds that dimension.
    sc = _scores()
    sizes = {m: s for members in _families().values() for m, s in members}
    best_small = best_big = None
    for m, dims in sc.items():
        s = dims.get(dim, 0)
        size = sizes.get(m, 0)
        tier_small = 0 < size <= SMALL_MAX_BYTES
        side = "right" if m.startswith("sov") else "left"
        tag = f"{side}_{'small' if tier_small else 'big'}"
        if tier_small:
            if best_small is None or s > best_small[1]:
                best_small = (m, s, tag)
        else:
            if best_big is None or s > best_big[1]:
                best_big = (m, s, tag)

    if best_small and best_small[1] >= ESCALATE_BELOW:
        return {"blocked": False, "dimension": dim, "tier": "SMALL", "cell": best_small[2],
                "model": best_small[0], "dim_score": best_small[1],
                "escalated": False, "why": f"small cell scores {best_small[1]:.1f} >= {ESCALATE_BELOW} threshold"}
    if best_big and (best_small is None or best_big[1] > best_small[1]):
        return {"blocked": False, "dimension": dim, "tier": "BIG", "cell": best_big[2],
                "model": best_big[0], "dim_score": best_big[1], "escalated": True,
                "why": f"small cell weak ({best_small[1]:.1f} < {ESCALATE_BELOW}); big scores {best_big[1]:.1f}"}
    if best_small:
        return {"blocked": False, "dimension": dim, "tier": "SMALL", "cell": best_small[2],
                "model": best_small[0], "dim_score": best_small[1], "escalated": False,
                "why": "no stronger big cell available"}
    return {"error": f"no measured cell holds '{dim}'"}


def status() -> None:
    grid = cells()
    print("  FAMILY CELLS — left (raw) / right (sov) × small / big\n")
    computable = 0
    for blob, c in grid.items():
        print(f"  family {blob}  ({c['members']} members)")
        for key, lab in [("left_small", "LEFT  small"), ("right_small", "RIGHT small"),
                         ("left_big", "LEFT  big  "), ("right_big", "RIGHT big  ")]:
            e = c.get(key)
            if e:
                s = f"{e['avg']}%" if e["avg"] is not None else "UNMEASURED"
                print(f"    {lab}  {e['model']:26s} {e['bytes']/1e6:6.0f}MB  {s}")
            else:
                print(f"    {lab}  {'—':26s}")
        for tier in ("small", "big"):
            d = c.get(f"delta_{tier}")
            if d is not None:
                computable += 1
                print(f"    >> WRAPPER DELTA ({tier}): {d:+.1f} pts")
        print()
    print(f"  families with a computable wrapper delta: {computable}")
    print(f"  ⚠️  Every wrapper claim so far rests on ONE family. Benchmarking")
    print(f"     llama3.2:3b + sov33-unified is the first replication on a different base —")
    print(f"     the cheapest decisive experiment available.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--route")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.route:
        print(json.dumps(route(a.route), indent=2))
    else:
        status()
