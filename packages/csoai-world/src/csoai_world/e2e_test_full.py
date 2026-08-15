#!/usr/bin/env python3
"""
E2E Test: OWEM Fractal Hive — Full SOV Architecture

Tests:
1. OWEM Sandwich Brain (4-layer: OWM frozen/fluid + IWM frozen/fluid)
2. 12-Clan Hive with fractal layers
3. SOV Router (task decomposition + distribution)
4. Stigmergy connections between OWEMs
5. C-space visual representation
6. BFT quorum from C-space
7. Full pipeline: OWM → SOV → Hive → BFT → Output

Run: python3 iwms/e2e_test_full.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from iwms.g_space import GSpace, FAMILIES
from iwms.j_space import JSpace
from iwms.bft_quorum import BFTQuorum
from iwms.owm import OWM
from iwms.iwm import IWM
from iwms.owem_brain import OWEMBrain, OWMBrainLayer, MiniSOVRouter
from iwms.owem_hive import OWEMHive, CLAN_LAYERS, StigmergyLayer
from iwms.sov_router import SOVRouter

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
    print("  OWEM FRACTAL HIVE E2E TEST")
    print("=" * 60)

    # ─── OWEM SANDWICH BRAIN ──────────────────────────────────
    print("\n[1/7] OWEM SANDWICH BRAIN (4-layer)")
    brain = OWEMBrain("deepseek", clan_id=0)
    test("Brain initialized", brain is not None)
    test("Brain has family", brain.family == "deepseek")
    test("Brain has UID", brain.uid == "owem-0-deepseek")
    test("OWM-FROZEN layer exists", brain.owm_frozen is not None)
    test("OWM-FLUID layer exists", brain.owm_fluid is not None)
    test("IWM-FROZEN layer exists", brain.iwm_frozen is not None)
    test("IWM-FLUID layer exists", brain.iwm_fluid is not None)
    test("Mini-SOV router exists", brain.sov_router is not None)
    test("4 layers total", all([brain.owm_frozen, brain.owm_fluid, brain.iwm_frozen, brain.iwm_fluid]))

    # Process a task
    j_card = brain.process("Solve a differential equation", {"name": "gpt-4"})
    test("Process returns J-card", j_card is not None)
    test("J-card has UID", j_card["uid"] == "owem-0-deepseek")
    test("J-card has 4 layer results", len(j_card["layer_results"]) == 4)
    test("J-card has routed result", "routed" in j_card)
    test("J-card has confidence", 0 <= j_card["confidence"] <= 1)
    test("Router selected best layer", j_card["routed"]["selected_layer"] is not None)
    test("Router has all scores", len(j_card["routed"]["all_scores"]) == 4)

    # Learn
    brain.learn({"task": "Solve equation", "won": True, "competitor": "gpt-4", "strategy": {"primary": "math"}})
    test("OWM-FLUID learned", brain.owm_fluid.learn_count > 0)
    test("IWM-FLUID learned", brain.iwm_fluid.learn_count > 0)

    status = brain.get_status()
    test("Status has all 4 layers", all(k in status for k in ["owm_frozen", "owm_fluid", "iwm_frozen", "iwm_fluid"]))

    # ─── OWEM HIVE ────────────────────────────────────────────
    print("\n[2/7] OWEM HIVE (12-clan fractal)")
    hive = OWEMHive()
    test("Hive initialized", hive is not None)
    test("12 clan layers", len(hive.clans) == 12)
    test("All clans have 4 brains", all(len(c["brains"]) == 4 for c in hive.clans.values()))
    test("48 total OWEM brains", sum(len(c["brains"]) for c in hive.clans.values()) == 48)
    test("192 total layers (48×4)", sum(len(c["brains"]) * 4 for c in hive.clans.values()) == 192)

    # Check clan structure
    for clan_name, config in CLAN_LAYERS.items():
        test(f"Clan {clan_name} exists", clan_name in hive.clans)
        test(f"Clan {clan_name} has specialist", hive.clans[clan_name]["specialist"] == config["specialist"])

    # Process task through hive
    hive_results = hive.process_task("Write Python code", {"name": "copilot"})
    test("Hive returns 12 clan results", len(hive_results) == 12)
    test("Each clan has c_space", all("c_space" in r for r in hive_results.values()))
    test("Each clan has best_family", all("best_family" in r for r in hive_results.values()))
    test("Each clan has confidence", all("confidence" in r for r in hive_results.values()))

    # Stigmergy
    test("Stigmergy has signals", len(hive.stigmergy.signals) > 0)
    test("Stigmergy has pheromone trails", len(hive.stigmergy.pheromone_trails) > 0)
    strongest = hive.stigmergy.get_strongest_trails(5)
    test("Strongest trails returned", len(strongest) > 0)

    topology = hive.get_topology()
    test("Topology has 12 clans", topology["total_clans"] == 12)
    test("Topology has 48 brains", topology["total_brains"] == 48)

    # ─── SOV ROUTER ───────────────────────────────────────────
    print("\n[3/7] SOV ROUTER (task decomposition)")
    sov = SOVRouter()
    test("SOV router initialized", sov is not None)
    test("SOV has hive", sov.hive is not None)
    test("SOV has BFT quorum", sov.bft is not None)
    test("SOV has G-space", sov.g_space is not None)

    # Process through SOV
    result = sov.process("Analyze sentiment in customer reviews", {"name": "claude"})
    test("SOV returns strategy", "strategy" in result)
    test("SOV has subtasks", result["subtasks"] > 0)
    test("SOV has master C-space", "master_cspace" in result)
    test("SOV has quorum", "quorum" in result)
    test("SOV has confidence", "confidence" in result)
    test("SOV has alliance", "alliance" in result)

    # Task decomposition
    subtasks = sov._decompose_task("Write optimized sorting algorithm")
    test("Task decomposed into subtasks", len(subtasks) > 1)
    test("Main subtask exists", any(s["id"] == "main" for s in subtasks))
    test("Knowledge subtask added", any(s["id"] == "knowledge" for s in subtasks))

    # Clan routing
    clans = sov._route_to_clans({"target_clan": "coding"})
    test("Routes to coding clan", "coding" in clans)

    # Master C-space
    master = result["master_cspace"]
    test("Master C-space has subtasks", len(master["subtasks"]) > 0)
    test("Master C-space has clan_contributions", len(master["clan_contributions"]) > 0)
    test("Master C-space has avg_confidence", 0 <= master["avg_confidence"] <= 1)

    # ─── STIGMERGY ────────────────────────────────────────────
    print("\n[4/7] STIGMERGY LAYER")
    stig = StigmergyLayer()
    test("Stigmergy initialized", stig is not None)
    stig.propagate({"clan1": {"confidence": 0.8, "best_family": "deepseek"}, "clan2": {"confidence": 0.6, "best_family": "qwen"}})
    test("Signals propagated", len(stig.signals) > 0)
    test("Pheromone trails created", len(stig.pheromone_trails) > 0)
    summary = stig.get_signal_summary()
    test("Summary has total_signals", summary["total_signals"] > 0)

    # ─── BFT FROM C-SPACE ─────────────────────────────────────
    print("\n[5/7] BFT QUORUM FROM C-SPACE")
    bft = BFTQuorum()
    test_cspace = {
        "clan_contributions": {
            "reasoning": {"total_confidence": 2.5, "count": 3},
            "coding": {"total_confidence": 2.0, "count": 2},
            "knowledge": {"total_confidence": 1.5, "count": 2},
        },
        "avg_confidence": 0.7,
    }
    quorum = bft.vote_from_cspace(test_cspace)
    test("BFT from C-space returns result", quorum is not None)
    test("Quorum has consensus", "consensus" in quorum)
    test("Quorum has winning_clan", "winning_clan" in quorum)
    test("Quorum has alliance", len(quorum["consensus"]["alliance"]) > 0)

    # ─── FULL PIPELINE ────────────────────────────────────────
    print("\n[6/7] FULL PIPELINE: OWM → SOV → HIVE → BFT → OUTPUT")
    owm = OWM(sov)
    test("OWM connected to SOV", owm.iwm is sov)

    # Ingest through OWM
    output = owm.ingest("Debug memory leak in Rust codebase", source="kaggle")
    test("OWM returns strategy", "strategy" in output)
    test("Output has confidence", "confidence" in output)
    test("Output has clan_alliance", "clan_alliance" in output)
    test("Output source is sov_space", output["source"] == "sov_space")

    # Competitor detection
    output2 = owm.ingest("Beat GPT-4 at reasoning tasks")
    test("Competitor detected", output2["competitor_analysis"].get("name") == "gpt-4")

    # ─── E2E INTEGRATION ──────────────────────────────────────
    print("\n[7/7] E2E: Full Fractal Hive Against Competitor")
    tasks = [
        ("Write optimized sorting algorithm", "gpt-4"),
        ("Translate legal document to Chinese", "claude"),
        ("Analyze satellite imagery", "gemini"),
        ("Debug memory leak in Rust", "copilot"),
        ("Write EU AI Act compliance report", "gpt-4"),
    ]
    for desc, comp in tasks:
        r = sov.process(desc, {"name": comp})
        test(f"SOV processed: {desc[:30]}...", "strategy" in r)
        sov.learn({"task": desc, "won": True, "competitor": comp, "clan": "reasoning", "family": "deepseek"})

    test("5 tasks processed", len(sov.task_log) >= 5)
    test("C-space history recorded", len(sov.c_space_history) >= 5)
    test("Hive stigmergy active", len(sov.hive.stigmergy.signals) > 0)
    test("Strongest trails exist", len(sov.hive.stigmergy.get_strongest_trails(5)) > 0)

    # Verify fractal structure
    status = sov.get_status()
    test("Hive has 12 clans", status["hive_topology"]["total_clans"] == 12)
    test("Hive has 48 brains", status["hive_topology"]["total_brains"] == 48)
    test("Stigmergy has signals", status["stigmergy"]["total_signals"] > 0)

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
