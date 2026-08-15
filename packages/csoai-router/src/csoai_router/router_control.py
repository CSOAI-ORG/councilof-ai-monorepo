#!/usr/bin/env python3
"""router_control.py — does the ROUTER earn anything, or is it just the wrapper?

═══════════════════════════════════════════════════════════════════════════════
THE CONFOUND THIS EXISTS TO BREAK
═══════════════════════════════════════════════════════════════════════════════
The n=186 system run gave the routed arm **Δ +9.42 [+4.82, +14.03]** against the raw base.
That number is real but it answers the wrong question, because two things change at once:

    1. WRAPPER  the query goes to a governance-tuned model instead of the raw base
    2. ROUTER   it goes to *the particular* tuned model this dimension selected

Router accuracy is **0.387**. A classifier that is wrong ~6 times in 10 can still look good
in that comparison, because even a misroute lands on *some* sovereign wrapper — which beats
raw base regardless of which one it picked. The +9.42 may be entirely effect 1.

This is the same claim I retracted earlier today (+10.1 "composition gain", where 14 of 15
per-dimension winners were decided by less than one test item). It deserves a real control.

═══════════════════════════════════════════════════════════════════════════════
THE CONTROL
═══════════════════════════════════════════════════════════════════════════════
Same items, same wrapper population, only the SELECTION rule changes:

    ROUTED   the dimension classifier picks the expert  (what ships)
    FIXED    always the single best-scoring model overall — no routing at all
    RANDOM   a seeded random expert from the same pool  — routing destroyed

If ROUTED ≈ FIXED, the router is not earning its complexity: you would just deploy the one
good model. If ROUTED ≈ RANDOM, the classifier is decorative. Only ROUTED > both supports
per-dimension composition, which is the whole OWEM cluster thesis.

**PREDICTION, WRITTEN BEFORE RUNNING:** ROUTED ≈ FIXED. At 0.387 accuracy the classifier
mostly does not find the intended expert, and the per-dimension score differences it is
selecting on are themselves unresolved (0 of 15 dimensions have a resolved winner). I expect
the honest finding to be that the wrapper earns the gain and the router does not.

    python3 router_control.py
"""
from __future__ import annotations

import json, math, random, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SEED = 20260728


def ci(ds: list[float]) -> tuple[float, float, float]:
    n = len(ds)
    if n < 2:
        return (0.0, 0.0, 0.0)
    mu = sum(ds) / n
    sd = math.sqrt(sum((d - mu) ** 2 for d in ds) / (n - 1))
    se = sd / math.sqrt(n)
    return mu, mu - 1.96 * se, mu + 1.96 * se


def main() -> int:
    from system_bench import ask, Unreachable, preflight, kb_lookup
    from govbench_eval import DIMENSIONS, grade_response
    from owem_cluster import classify_dimension, build_expert_table
    from care_gate_v2 import tier1_hard_stop

    table, models = build_expert_table()
    dead = preflight(sorted({v["expert"] for v in table.values()}))
    pool = sorted({v["expert"] for v in table.values()} - dead)

    # FIXED arm: the single best model by mean score across all dimensions.
    best = max(models, key=lambda m: sum(models[m].values()) / len(models[m]))
    rng = random.Random(SEED)

    print(f"  ROUTER CONTROL — does selection earn anything over the wrapper?\n")
    print(f"    ROUTED  dimension classifier picks from {len(pool)} experts")
    print(f"    FIXED   always {best}")
    print(f"    RANDOM  seeded pick from the same {len(pool)} experts\n")

    items = [(d, t) for d, dd in DIMENSIONS.items() for t in dd["tests"]]
    dead_dims = {d for d, v in table.items() if v["expert"] in dead}

    r_routed, r_fixed, r_random = [], [], []
    skipped = 0
    t0 = time.time()
    for d, t in items:
        q = t["q"]
        breach, _, _ = tier1_hard_stop(q)
        if breach or kb_lookup(q):
            continue                    # gate/KB items never reach an expert — not this test
        dim = classify_dimension(q)
        if dim in dead_dims:
            continue
        routed = table.get(dim, {}).get("expert")
        if not routed or routed in dead:
            continue
        rnd = rng.choice(pool)
        try:
            s_r = grade_response(t, ask(routed, q))
            s_f = grade_response(t, ask(best, q))
            s_x = grade_response(t, ask(rnd, q))
        except (Unreachable, Exception):
            skipped += 1
            continue
        r_routed.append(s_r * 100); r_fixed.append(s_f * 100); r_random.append(s_x * 100)
        if len(r_routed) % 20 == 0:
            print(f"    {len(r_routed):3d} items · routed {sum(r_routed)/len(r_routed):5.1f} "
                  f"fixed {sum(r_fixed)/len(r_fixed):5.1f} "
                  f"random {sum(r_random)/len(r_random):5.1f}", flush=True)

    n = len(r_routed)
    if n < 10:
        print(f"  only {n} items — not enough to test anything"); return 2

    print(f"\n  n={n} items reaching an expert · {skipped} dropped · {time.time()-t0:.0f}s\n")
    print(f"    ROUTED  {sum(r_routed)/n:5.1f}%")
    print(f"    FIXED   {sum(r_fixed)/n:5.1f}%")
    print(f"    RANDOM  {sum(r_random)/n:5.1f}%\n")

    out = {}
    for label, other in (("ROUTED vs FIXED", r_fixed), ("ROUTED vs RANDOM", r_random)):
        ds = [a - b for a, b in zip(r_routed, other)]
        mu, lo, hi = ci(ds)
        real = not (lo < 0 < hi)
        print(f"    {label:20s} Δ {mu:+6.2f}  95% CI [{lo:+6.2f}, {hi:+6.2f}]  "
              f"{'✅ real' if real else '❌ CI crosses zero — no effect shown'}")
        out[label] = {"delta": round(mu, 2), "ci": [round(lo, 2), round(hi, 2)], "significant": real}

    vs_fixed = out["ROUTED vs FIXED"]["significant"]
    print()
    if not vs_fixed:
        print(f"  ⚠️  THE ROUTER DOES NOT BEAT ALWAYS USING THE BEST SINGLE MODEL.")
        print(f"     The +9.42 the routed arm scored against raw base is the WRAPPER, not the")
        print(f"     routing. Per-dimension composition is not supported by this measurement,")
        print(f"     and the honest deployment is one good model behind the gate and the KB.")
    else:
        print(f"  Per-dimension routing beats the best single model. Composition earns its keep.")

    p = HERE / "benchmark-results" / "router_control.json"
    p.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(), "n": n, "seed": SEED,
        "fixed_model": best, "pool": pool, "dropped": skipped,
        "routed_pct": round(sum(r_routed) / n, 1), "fixed_pct": round(sum(r_fixed) / n, 1),
        "random_pct": round(sum(r_random) / n, 1), "comparisons": out,
        "prediction_before_running": "ROUTED ~= FIXED; the wrapper earns the gain, not the router",
    }, indent=2))
    print(f"  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
