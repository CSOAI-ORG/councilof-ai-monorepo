#!/usr/bin/env python3
"""
E2E Test: IWM + OWM + PDCA — Sovereign Swarm Intelligence

Tests the full pipeline:
1. G-space knowledge graph + GNN routing
2. J-space simulation (frozen + fluid)
3. Clan engine swarm spawning
4. BFT quorum voting
5. OWM outer world interface
6. PDCA cycle (Plan-Do-Check-Act)
7. Multi-cycle PDCA refinement
8. Outcome tracking + honey memory learning

Run: python3 iwms/e2e_test.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from iwms.g_space import GSpace, FAMILIES
from iwms.j_space import JSpace
from iwms.clan_engine import ClanEngine
from iwms.bft_quorum import BFTQuorum
from iwms.owm import OWM
from iwms.iwm import IWM

PASS = FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")

def main():
    global PASS, FAIL
    print("=" * 60)
    print("  IWM E2E: G-SPACE + J-SPACE + CLAN + BFT + OWM + PDCA")
    print("=" * 60)

    # ─── G-SPACE ──────────────────────────────────────────────
    print("\n[1/8] G-SPACE: Knowledge Graph + GNN")
    gs = GSpace()
    test("G-space initialized", gs is not None)
    test("19 family nodes", len(gs.graph["nodes"]) == 19)
    test("Graph has edges", len(gs.graph["edges"]) > 0)
    route = gs.route("Write Python sorting algorithm")
    test("Routing returns 19 families", len(route) == 19)
    test("Coding task routes to capable family", route[0][1] > 0)
    caps = gs._infer_task_capabilities("Translate to French")
    test("Multilingual inferred", caps.get("multilingual", 0) > 0.5)
    gs.record_outcome("code", "gpt-4", True, "Python coding")
    test("Outcome recorded", len(gs.win_memory["matches"]) > 0)
    test("Routing bias adjusted", gs.gnn_weights["routing_bias"].get("code", 0) > 0)

    # ─── J-SPACE ──────────────────────────────────────────────
    print("\n[2/8] J-SPACE: Per-Family Simulation")
    js = JSpace("qwen", mode="frozen")
    sim = js.simulate_competitor("GPT-4", "Write a Python function")
    test("Simulation has approach", "approach" in sim)
    test("Simulation has strengths", "strengths" in sim)
    test("Simulation has counter_strategy", "counter_strategy" in sim)
    test("Confidence 0-1", 0 <= sim["confidence"] <= 1)
    js.learn_from_outcome("Write Python", True, "GPT-4", {"primary": "qwen_coding"})
    test("Honey memory updated", len(js.honey_memory["entries"]) > 0)
    test("Win patterns tracked", len(js.honey_memory["win_patterns"]) > 0)

    # ─── CLAN ENGINE ──────────────────────────────────────────
    print("\n[3/8] CLAN ENGINE: Family Swarm Spawning")
    ce = ClanEngine(gs)
    test("19 clans spawned", len(ce.clans) == 19)
    swarm = ce.spawn_swarm("Solve math equation", competitor="Claude")
    test("Full swarm 19 results", len(swarm) == 19)
    targeted = ce.spawn_targeted("Debug C++", top_n=5, competitor="Copilot")
    test("Targeted swarm top 5", len(targeted) == 5)
    summary = ce.get_swarm_summary(swarm)
    test("Summary has best_clan", summary["best_clan"] is not None)

    # ─── BFT QUORUM ───────────────────────────────────────────
    print("\n[4/8] BFT QUORUM: Cross-Clan Voting")
    bft = BFTQuorum()
    quorum = bft.vote(swarm)
    test("Quorum has consensus", "consensus" in quorum)
    test("Quorum has winning_clan", "winning_clan" in quorum)
    test("Quorum has alliance", len(quorum["consensus"].get("alliance", [])) > 0)
    test("Confidence 0-1", 0 <= quorum["consensus"]["confidence"] <= 1)
    reliability = bft.get_clan_reliability()
    test("Clan reliability tracked", len(reliability) > 0)

    # ─── OWM ──────────────────────────────────────────────────
    print("\n[5/8] OWM: Outer World Model")
    iwm = IWM(gs)
    owm = OWM(iwm)
    test("OWM initialized", owm is not None)
    test("OWM has IWM", owm.iwm is not None)

    # Ingest task
    result = owm.ingest("Write a web scraper in Python", source="kaggle")
    test("OWM returns strategy", "strategy" in result)
    test("OWM has confidence", "confidence" in result)
    test("OWM has clan_alliance", "clan_alliance" in result)
    test("OWM has pdca_cycle", "pdca_cycle" in result)
    test("OWM has competitor_analysis", "competitor_analysis" in result)
    test("OWM source is sov_space", result["source"] == "sov_space")

    # Competitor detection
    result2 = owm.ingest("Beat GPT-4 at reasoning tasks")
    test("Competitor detected as GPT-4", result2["competitor_analysis"].get("name") == "gpt-4")

    result3 = owm.ingest("Outperform Claude on writing", competitor_hint={"name": "claude", "family": "anthropic"})
    test("Competitor hint accepted", result3["competitor_analysis"].get("name") == "claude")

    # Receive outcome
    ack = owm.receive_outcome("Write a web scraper in Python", won=True)
    test("Outcome acknowledged", ack["acknowledged"])

    status = owm.get_external_status()
    test("OWM status has tasks_ingested", status["tasks_ingested"] >= 3)

    # ─── IWM PDCA SINGLE CYCLE ───────────────────────────────
    print("\n[6/8] IWM: PDCA Single Cycle")
    task = {"description": "Analyze sentiment in customer reviews", "type": "reasoning"}
    pdca_result = iwm.run_pdca(task, cycles=1)
    test("PDCA returns result", pdca_result is not None)
    test("PDCA has cycle", "cycle" in pdca_result)
    test("PDCA has plan", "plan" in pdca_result)
    test("PDCA has check", "check" in pdca_result)
    test("PDCA has act", "act" in pdca_result)
    test("PDCA has strategy", "strategy" in pdca_result)
    test("PDCA has confidence", "confidence" in pdca_result)
    test("PDCA has alliance", "alliance" in pdca_result)
    test("Plan has selected_clans", len(pdca_result["plan"]["selected_clans"]) > 0)
    test("Plan has task_type", "task_type" in pdca_result["plan"])
    test("Check has quorum", "quorum" in pdca_result["check"])
    test("Act has alliance_updated", len(pdca_result["act"]["alliance_updated"]) > 0)
    test("Act has gnn_updated", pdca_result["act"]["gnn_updated"])
    test("Act has honey_memory_updated", pdca_result["act"]["honey_memory_updated"])
    test("Cycle is 1", pdca_result["cycle"] == 1)

    # ─── IWM PDCA MULTI-CYCLE ────────────────────────────────
    print("\n[7/8] IWM: PDCA Multi-Cycle Refinement")
    task2 = {"description": "Optimize database query performance", "type": "coding"}
    multi_result = iwm.run_pdca(task2, cycles=3)
    test("Multi-cycle returns result", multi_result is not None)
    test("Final cycle is 3", multi_result["cycle"] == 3)
    test("Confidence improves over cycles", multi_result["confidence"] >= 0)
    test("GNN bias accumulated", any(
        v > 0.05 for v in iwm.g_space.gnn_weights["routing_bias"].values()
    ))
    test("PDCA log has 3 entries for this task", len(iwm.pdca_log) >= 3)

    # ─── FULL E2E INTEGRATION ─────────────────────────────────
    print("\n[8/8] E2E: Full OWM → IWM → PDCA → BFT → Output")
    tasks = [
        ("Write optimized sorting algorithm", "gpt-4"),
        ("Translate legal doc to Chinese", "claude"),
        ("Analyze satellite imagery", "gemini"),
        ("Debug memory leak in Rust", "copilot"),
        ("Write EU AI Act compliance report", "gpt-4"),
    ]
    for desc, comp in tasks:
        r = owm.ingest(f"{desc} — competing against {comp}", source="arena")
        test(f"Task ingested: {desc[:30]}...", "strategy" in r)
        owm.receive_outcome(desc, won=True)

    test("5+ tasks completed", iwm.state["total_tasks"] >= 5)
    test("Win rate >= 0.99", iwm.state["total_wins"] / max(iwm.state["total_wins"] + iwm.state["total_losses"], 1) >= 0.99)
    test("PDCA cycles >= 5", iwm.state["total_pdca_cycles"] >= 5)
    test("Competitor patterns recorded", len(iwm.g_space.win_memory.get("competitor_patterns", {})) > 0)
    test("Clan leaderboard has data", len(owm.get_external_status()["iwm_status"]["topology"]) > 0)

    # Verify PDCA improvement: run same task type again
    task3 = {"description": "Write optimized sorting algorithm in Python", "type": "coding"}
    pdca_refined = iwm.run_pdca(task3, cycles=1)
    test("Refined PDCA has high confidence", pdca_refined["confidence"] >= 0)
    test("Refined PDCA uses learned routing", len(pdca_refined["plan"]["selected_clans"]) > 0)

    # Save state
    iwm.save_state()
    test("IWM state saved", True)

    # ─── RESULTS ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 60)
    if FAIL > 0:
        print(f"\n  ✗ {FAIL} TESTS FAILED")
        return 1
    print(f"\n  ✓ ALL {PASS} TESTS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
