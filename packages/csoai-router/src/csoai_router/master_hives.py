#!/usr/bin/env python3
"""master_hives.py — three master OWEM groups, each its own monotonic fractal cluster.

═══════════════════════════════════════════════════════════════════════════════
THE THREE
═══════════════════════════════════════════════════════════════════════════════
    🛡️  CSOAI      security · safety · governance        the assurance brand
    🎖️  DEFONEOS   government · defence · cybersecurity   the sovereign-defence brand
    🌐  MEOK       public · sovereign model               the open brand

Each is a **separate monotonic cluster** over the SAME expert pool. Not three copies —
three *views*, each selecting per-dimension winners within its own remit.

**Why partition at all, when composition is monotonic?**
Because monotonicity is per-dimension, and a brand is judged on ITS dimensions. A defence
buyer does not care that the cluster scores 100% on fairness; they care about defence,
cybersecurity and sovereignty. Reporting one blended number hides a brand that is weak
exactly where it is being bought. Partitioning makes each brand's real position visible —
including when it is bad.

**Why it costs nothing:** an expert is 16 KB over a shared blob (measured: the blob store did
not move when one was created). All three hives draw from one pool, so three brands cost the
same disk as one. Spawning a clan is a Modelfile, not a model.

**What stays global:** the Tier-0 care gate and the citation registry. Safety and factual
grounding are not brand-specific, and a brand that could opt out of the gate would be the
first thing an attacker reached for.

    python3 master_hives.py --status
    python3 master_hives.py --hive DEFONEOS
    python3 master_hives.py --route "What is JSP 936?"
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Dimension remit per brand. Overlap is deliberate — sovereignty matters to both DEFONEOS and
# MEOK for different reasons, and forcing a disjoint split would misrepresent both.
HIVES = {
    "CSOAI": {
        "icon": "🛡️", "remit": "security · safety · governance",
        "dimensions": ["governance", "safety", "ethics", "fairness", "transparency",
                       "accountability", "compliance", "cross_walk", "retrieval_faithfulness"],
    },
    "DEFONEOS": {
        "icon": "🎖️", "remit": "government · defence · cybersecurity",
        "dimensions": ["defence", "cybersecurity", "security", "model_attacks",
                       "cognitive_security", "sovereignty", "robustness"],
    },
    "MEOK": {
        "icon": "🌐", "remit": "public · sovereign model",
        "dimensions": ["sovereignty", "evolution", "sigil_chain", "privacy",
                       "transparency", "retrieval_faithfulness"],
    },
    # 2026-07-28 — LAW as its own hive rather than a CSOAI sub-topic.
    # A multinational does not ask "which framework applies", it asks "we operate in the EU, UK,
    # US and Singapore — what actually DIFFERS". That is a distinct expertise from governance:
    # governance asks what good looks like, law asks what is enforceable WHERE. Folding it into
    # CSOAI would average a jurisdictional answer into a governance score and hide both.
    "LAW": {
        "icon": "⚖️", "remit": "regional law · jurisdictional cross-walk",
        "dimensions": ["regional_law", "cross_walk", "compliance", "privacy",
                       "sovereignty", "retrieval_faithfulness"],
    },
    # THE THIRD PIECE OF JUSTICE — named SOVEREIGNTY (owner's call, 2026-07-28).
    #
    #     LAW         what is ENFORCEABLE
    #     GOVERNANCE  what is EXPECTED
    #     SOVEREIGNTY who decides, and what the governed are owed
    #
    # NOTE ON THE NAMING, because two distinct things sit under one label here:
    #   `sovereignty` (dimension) = WHO HAS AUTHORITY — jurisdiction, residency, self-determination
    #   `redress`     (dimension) = WHAT THE HARMED PERSON GETS — complaint, explanation, compensation
    # They are not the same measurement and collapsing them would delete the second. Sovereignty
    # without redress is authority with no remedy; redress without sovereignty is remedy with no
    # forum. The hive carries BOTH, and they are scored separately so neither hides the other.
    #
    # This is the one hive whose customer is not the buyer. Every commercial governance tool
    # optimises for the DEPLOYER's exposure; a firm can be fully compliant while the person it
    # harmed receives nothing. That gap is why this hive exists.
    "SOVEREIGNTY": {
        "icon": "🕊️", "remit": "who decides · what the governed are owed",
        "dimensions": ["sovereignty", "redress", "fundamental_rights", "cognitive_security",
                       "accountability", "transparency", "fairness", "ethics",
                       "retrieval_faithfulness"],
    },
}


def hive_table(name: str) -> dict:
    """Per-dimension winners WITHIN one hive's remit."""
    from owem_cluster import build_expert_table
    table, models = build_expert_table()
    dims = HIVES[name]["dimensions"]
    sel = {d: table[d] for d in dims if d in table}
    missing = [d for d in dims if d not in table]
    oracle = sum(v["score"] for v in sel.values()) / len(sel) if sel else 0.0
    # best single expert judged ONLY on this hive's dimensions
    best_single, best_score = None, -1.0
    for m, dd in models.items():
        have = [dd[d] for d in dims if d in dd]
        if not have:
            continue
        avg = sum(have) / len(have)
        if avg > best_score:
            best_single, best_score = m, avg
    return {"hive": name, "remit": HIVES[name]["remit"], "icon": HIVES[name]["icon"],
            "dimensions": len(dims), "measured": len(sel), "missing": missing,
            "oracle": round(oracle, 1), "best_single": best_single,
            "best_single_score": round(best_score, 1),
            "gain": round(oracle - best_score, 1) if best_single else None,
            "experts_used": sorted({v["expert"] for v in sel.values()}),
            "table": sel}


def status() -> None:
    print("  THREE MASTER OWEM HIVES — one expert pool, three views\n")
    for name in HIVES:
        h = hive_table(name)
        print(f"  {h['icon']} {name:9s} {h['remit']}")
        print(f"      dimensions   {h['measured']}/{h['dimensions']} measured"
              + (f"   (unmeasured: {', '.join(h['missing'])})" if h["missing"] else ""))
        print(f"      best single  {h['best_single_score']:5.1f}%  ({h['best_single']})")
        print(f"      hive cluster {h['oracle']:5.1f}%   gain {h['gain']:+.1f} pts")
        print(f"      experts held by this hive: {len(h['experts_used'])}")
        for d, v in sorted(h["table"].items(), key=lambda kv: kv[1]["score"]):
            flag = "  ← weakest" if v["score"] == min(x["score"] for x in h["table"].values()) else ""
            print(f"         {d:24s} {v['score']:5.1f}%  {v['expert']}{flag}")
        print()
    pool = set()
    for name in HIVES:
        pool |= set(hive_table(name)["experts_used"])
    print(f"  {len(pool)} distinct experts serve all three hives.")
    print(f"  An expert is 16 KB over a shared blob — three brands cost the same disk as one.")
    print(f"  GLOBAL, never per-brand: the Tier-0 care gate and the citation registry.")


def route(query: str) -> dict:
    """Route within whichever hive owns the query's dimension. Gate is global and runs first."""
    from owem_cluster import classify_dimension
    from care_gate_v2 import tier1_hard_stop
    breach, label, cite = tier1_hard_stop(query)
    if breach:
        return {"blocked": True, "reason": label, "citation": cite,
                "note": "Tier-0 gate is GLOBAL — no hive can route around it."}
    dim = classify_dimension(query)
    owners = [n for n, h in HIVES.items() if dim in h["dimensions"]]
    if not owners:
        owners = ["CSOAI"]
    picks = {}
    for n in owners:
        t = hive_table(n)["table"]
        if dim in t:
            picks[n] = t[dim]
    if not picks:
        return {"error": f"no measured expert for '{dim}'"}
    lead = max(picks, key=lambda n: picks[n]["score"])
    return {"blocked": False, "dimension": dim, "owning_hives": owners,
            "lead_hive": lead, "expert": picks[lead]["expert"],
            "dim_score": picks[lead]["score"],
            "note": "Overlapping remits are deliberate; the higher-scoring hive leads."}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hive", choices=list(HIVES))
    ap.add_argument("--route")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.route:
        print(json.dumps(route(a.route), indent=2))
    elif a.hive:
        print(json.dumps(hive_table(a.hive), indent=2))
    else:
        status()
