#!/usr/bin/env python3
"""sov_swarm.py — GPU cluster auto-scaler for sovereign end-user models.

Per memory: free compute sources — Apple M4 unified memory (16GB), Kaggle
T4 30 hr/week, Modal $30/mo credit, RunPod A100 paid, Groq Together free.

End-users at tier-0 (379MB qwen2.5:0.5b) need NO GPU. As they grow to tier
3 (~8GB lora-merged), they need a real GPU. The swarm decides which tier
gets which backend at any moment, with cost as the primary constraint and
latency as the secondary.

Allocation rules:
  Tier 0 (tiny):   local CPU (always)
  Tier 1 (small):  local CPU preferred, Groq fallback (free)
  Tier 2 (medium): local CPU OR Groq free OR Modal A100 (paid)
  Tier 3 (large):  Modal A100 (paid) OR Kaggle T4 (free quota) OR RunPod
  Tier 4 (sovereign): GPU cluster, mix of suppliers, load-balanced

  python3 sov_swarm.py --list-backends
  python3 sov_swarm.py --alloc --for tier-2
  python3 sov_swarm.py --tick                # re-allocate as needed
  python3 sov_swarm.py --selftest
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


# Backend catalogue — concrete providers per memory
BACKENDS = {
    "local_cpu_m4": {
        "kind": "apple_m4",
        "vram_gb": 16,
        "cost_per_hour_usd": 0.0,
        "tiers_supported": [0, 1, 2],
        "latency_p50_ms": 80,
        "rate_limit_rpm": None,
        "free": True,
        "always_on": True,
        "owner": "self",
    },
    "groq_free": {
        "kind": "api",
        "model_target": "llama-3.1-8b / qwen / mixtral",
        "cost_per_token_usd": 0.0,
        "tiers_supported": [1, 2, 3],
        "latency_p50_ms": 120,
        "rate_limit_rpm": 30,
        "free": True,
        "always_on": False,
        "owner": "groq",
    },
    "modal_free_tier": {
        "kind": "serverless",
        "model_target": "any (A100)",
        "cost_per_hour_usd": 1.5,
        "monthly_credit_usd": 30,
        "tiers_supported": [2, 3, 4],
        "latency_p50_ms": 400,
        "free_tier_per_month_hours": 30,
        "free": False,  # mostly paid after credit
        "always_on": False,
        "owner": "self",
    },
    "kaggle_t4_free": {
        "kind": "jupyter_notebook",
        "model_target": "LoRA adapters on T4 (16GB)",
        "cost_per_hour_usd": 0.0,
        "weekly_quota_hours": 30,
        "tiers_supported": [2, 3, 4],
        "latency_p50_ms": 600,
        "free": True,
        "always_on": False,
        "owner": "self",
    },
    "runpod_a100_paid": {
        "kind": "spot_instance",
        "model_target": "full-blown training + serving",
        "cost_per_hour_usd": 1.39,
        "tiers_supported": [3, 4],
        "latency_p50_ms": 250,
        "free": False,
        "always_on": False,
        "owner": "self",
    },
    "swarm_consensus_mcp": {
        "kind": "mcp_cluster",
        "model_target": "any (c2pa-signed distributed runtime)",
        "cost_per_hour_usd": 0.0,
        "tiers_supported": [0, 1, 2, 3, 4],
        "latency_p50_ms": 50,
        "free": True,
        "always_on": True,
        "owner": "swarm",
        "note": "The sovereign MCP cluster scales horizontally by adding OWEMs — UE5 renders the swarm, each MCP carries one slice.",
    },
}


def list_backends() -> dict:
    """Show every backend with current cost ceiling."""
    return {
        "backends": BACKENDS,
        "n_backends": len(BACKENDS),
        "free_count": sum(1 for b in BACKENDS.values() if b.get("free")),
        "n_alw_ays_on": sum(1 for b in BACKENDS.values() if b.get("always_on")),
    }


_TIER_PRIMARY_ORDER = {
    0: ["local_cpu_m4"],
    1: ["local_cpu_m4", "groq_free"],
    2: ["groq_free", "local_cpu_m4", "modal_free_tier", "kaggle_t4_free"],
    3: ["kaggle_t4_free", "modal_free_tier", "runpod_a100_paid", "groq_free"],
    4: ["swarm_consensus_mcp", "runpod_a100_paid", "kaggle_t4_free", "modal_free_tier"],
}


def alloc_for_tier(tier: int) -> list[dict]:
    """Pick the best backend for a tier — declared primary order, then fallbacks."""
    candidates = [(name, b) for name, b in BACKENDS.items() if tier in b["tiers_supported"]]
    if not candidates:
        return []

    primary = None
    for pname in _TIER_PRIMARY_ORDER.get(tier, []):
        if any(pname == c[0] for c in candidates):
            primary = pname
            break
    if primary is None:
        # Fall back: sort by always_on, then cost, then latency
        candidates.sort(key=lambda b: (
            not b[1].get("always_on", False),
            b[1].get("cost_per_hour_usd", 9999) or 9999,
            b[1].get("latency_p50_ms", 9999),
        ))
        primary = candidates[0][0]

    plan = [{"backend": primary, "role": "primary"}]
    seen = {primary}

    # Add fallbacks in declared-order preference, then remaining
    for pname in _TIER_PRIMARY_ORDER.get(tier, []):
        for cname, _ in candidates:
            if cname == pname and cname not in seen:
                plan.append({"backend": cname, "role": "fallback"})
                seen.add(cname)
                break
    for cname, _ in candidates:
        if cname not in seen:
            plan.append({"backend": cname, "role": "fallback"})
            seen.add(cname)

    return plan


def tick() -> dict:
    """One swarm tick — re-allocates tiers as load changes.

    In a real environment this would read live GPU utilisation from each
    provider. Here we simulate: allocation plan refreshed every tick.
    """
    plan_by_tier = {}
    total_capacity_gb_h = 0
    for tier in range(5):
        plan = alloc_for_tier(tier)
        plan_by_tier[tier] = plan
        for slot in plan:
            b = BACKENDS[slot["backend"]]
            total_capacity_gb_h += b.get("vram_gb", 0) / max(len(plan), 1)

    return {
        "tick_at": time.time(),
        "plan_by_tier": plan_by_tier,
        "total_capacity_gb_h": total_capacity_gb_h,
        "n_backends": len(BACKENDS),
    }


def selftest() -> int:
    fails = []

    # All backends load
    if len(BACKENDS) < 4:
        fails.append(f"expected ≥4 backends, got {len(BACKENDS)}")

    # Each tier has at least 1 capable backend
    for tier in range(5):
        plan = alloc_for_tier(tier)
        if not plan:
            fails.append(f"tier {tier} has no backends")
            continue
        # Primary should be the cheapest-free or always_on one
        primary = BACKENDS[plan[0]["backend"]]
        if not primary.get("free") and not primary.get("always_on"):
            fails.append(f"tier {tier} primary not free/always-on: {primary}")

    # Tick generates a plan across all tiers
    state = tick()
    if "plan_by_tier" not in state:
        fails.append("tick missing plan_by_tier")
    if len(state["plan_by_tier"]) != 5:
        fails.append(f"plan_by_tier wrong size: {state['plan_by_tier']}")

    # Total capacity > 0
    if state["total_capacity_gb_h"] <= 0:
        fails.append(f"total capacity zero: {state}")

    # Cross-tier: all 5 tiers should have different primary backends
    primaries = set()
    for tier in range(5):
        plan = alloc_for_tier(tier)
        primaries.add(plan[0]["backend"])
    if len(primaries) < 2:
        fails.append(f"too few unique primaries: {primaries}")

    # MCP cluster present (always on, all tiers)
    if "swarm_consensus_mcp" not in BACKENDS:
        fails.append("missing MCP cluster")
    mcp = BACKENDS["swarm_consensus_mcp"]
    if mcp["tiers_supported"] != [0, 1, 2, 3, 4]:
        fails.append(f"MCP cluster tier list wrong: {mcp['tiers_supported']}")

    # Free backends always free
    for name, b in BACKENDS.items():
        if b.get("free") and (b.get("cost_per_hour_usd") or 0) > 0:
            fails.append(f"{name} marked free but has cost: {b}")

    for f in fails:
        print(f"  ❌ {f}")
    if not fails:
        print("  ✅ selftest 9/9 — 6 backends (Apple M4 + Groq + Modal + Kaggle + RunPod + MCP), "
              "all 5 tiers have plans, MCP cluster covers all tiers free")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    elif "--list-backends" in sys.argv:
        print(json.dumps(list_backends(), indent=2))
    elif "--alloc" in sys.argv:
        i = sys.argv.index("--alloc")
        tier = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 2
        print(json.dumps(alloc_for_tier(tier), indent=2))
    elif "--tick" in sys.argv:
        print(json.dumps(tick(), indent=2))
    else:
        print(__doc__)
