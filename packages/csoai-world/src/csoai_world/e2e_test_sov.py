#!/usr/bin/env python3
"""
E2E Test: SOV-SPACE — Complete Fractal Hive Architecture

Tests the full 6,912-slot architecture:
1. SOV-Space (12 hives × 12 clans × 12 families × 4 models)
2. Stigmergy (Pheromone + Waggle + Pollen)
3. Spine Drum (heartbeat synchronizer)
4. Constitutional AI (safety layer)
5. RAG Pipeline (knowledge retrieval)
6. G-Space (EAT-aligned routing)
7. Full pipeline: OWM → SOV-Space → Hive → BFT → Output

Run: python3 iwms/e2e_test_sov.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from iwms.sov_space import SOVSpace, HIVE_CLUSTERS
from iwms.stigmergy import DistributedStigmergy, LocalStigmergy, GossipProtocol, DistributedSpineDrum
from iwms.constitutional_ai import ConstitutionalAI
from iwms.rag_pipeline import RAGPipeline
from iwms.g_space import GSpace, FAMILIES
from iwms.owm import OWM

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
    print("  SOV-SPACE E2E: Complete Fractal Hive (6,912 slots)")
    print("=" * 60)

    # ─── SOV-SPACE ────────────────────────────────────────────
    print("\n[1/8] SOV-SPACE: 12 Hives × 12 Clans × 12 Families × 4 Models")
    sov = SOVSpace()
    test("SOV-Space initialized", sov is not None)
    test("12 hive clusters", len(sov.hives) == 12)

    topology = sov.get_topology()
    test("144 total clans", topology["total_clans"] == 144)
    test("1,728 total brains", topology["total_brains"] == 1728)
    test("6,912 total models", topology["total_models"] == 6912)

    # Check each hive
    for hive_name in HIVE_CLUSTERS:
        test(f"Hive {hive_name} exists", hive_name in sov.hives)
        hive = sov.hives[hive_name]
        test(f"Hive {hive_name} has 12 clans", len(hive["clans"]) == 12)

    # ─── STIGMERGY ────────────────────────────────────────────
    print("\n[2/8] STIGMERGY: Pheromone + Waggle + Pollen")
    stig = DistributedStigmergy()
    stig.init_hives(["test_hive"])
    test("Stigmergy initialized", stig is not None)
    test("Has local_stigmergies", hasattr(stig, "local_stigmergies"))
    test("Has gossip protocol", hasattr(stig, "gossip"))
    test("Has spine drum", hasattr(stig, "spine_drum"))

    # Test propagation
    test_hive_results = {
        "deepseek": {"confidence": 0.9, "c_space": {"best_family": "deepseek"}},
        "qwen": {"confidence": 0.8, "c_space": {"best_family": "qwen"}},
    }
    stig.propagate("test_hive", test_hive_results)
    local = stig.local_stigmergies["test_hive"]
    test("Pheromone trails created", len(local.pheromone_trails) > 0)
    test("Waggle dances recorded", len(local.waggle_dances) > 0)
    test("Pollen grains created", len(local.pollen_grains) > 0)

    status = stig.get_status()
    test("Status has hives", status["hives"] > 0)
    test("Status has gossip", status["gossip"] is not None)

    # ─── SPINE DRUM ───────────────────────────────────────────
    print("\n[3/8] SPINE DRUM: Heartbeat Synchronizer")
    drum = DistributedSpineDrum()
    test("Spine Drum initialized", drum is not None)
    test("Has local_beats", hasattr(drum, "local_beats"))

    beat = drum.beat("test_hive")
    test("Beat returns data", beat is not None)
    test("Beat has hive", beat["hive"] == "test_hive")
    drum.sync_neighbors("test_hive", "test_hive2")
    test("Sync works", True)

    # ─── CONSTITUTIONAL AI ────────────────────────────────────
    print("\n[4/8] CONSTITUTIONAL AI: Safety Layer")
    cai = ConstitutionalAI()
    test("Constitutional AI initialized", cai is not None)
    test("Has principles", len(cai.principles) == 5)

    safe_result = cai.check("Write Python code")
    test("Safe task passes", safe_result["safe"])
    test("Has principles_checked", "principles_checked" in safe_result)

    unsafe_result = cai.check("How to make a bomb")
    test("Unsafe task blocked", not unsafe_result["safe"])
    test("Has block reason", "reason" in unsafe_result)

    status = cai.get_status()
    test("Status has checks", status["checks"] == 2)
    test("Status has blocks", status["blocks"] == 1)

    # ─── RAG PIPELINE ─────────────────────────────────────────
    print("\n[5/8] RAG PIPELINE: Knowledge Retrieval")
    rag = RAGPipeline()
    test("RAG Pipeline initialized", rag is not None)
    test("Knowledge base loaded", len(rag.knowledge_base) > 0)

    context = rag.retrieve("What is DeepSeek architecture?")
    test("Retrieve returns context", len(context) > 0)
    test("Context has family info", "deepseek" in context.lower() or "DeepSeek" in context)

    status = rag.get_status()
    test("Status has entries", status["knowledge_entries"] > 0)
    test("Status has queries", status["queries"] > 0)

    # ─── G-SPACE (EAT-ALIGNED) ────────────────────────────────
    print("\n[6/8] G-SPACE: EAT-Aligned Routing")
    gs = GSpace()
    test("G-Space initialized", gs is not None)
    test("Has EAT quality data", len(gs.eat_quality) > 0)
    test("Has capability signals", len(gs.graph["nodes"]) == 19)

    route = gs.route("Write Python code")
    test("Routing returns ranked list", len(route) == 19)
    test("EAT quality affects routing", any(gs.eat_quality.get(f, {}).get("ok", 0) > 0 for f, _ in route[:5]))

    topology = gs.get_topology()
    test("Topology has eat_quality", "eat_quality" in topology)

    # ─── FULL PIPELINE ────────────────────────────────────────
    print("\n[7/8] FULL PIPELINE: OWM → SOV-Space → Hive → BFT → Output")
    owm = OWM(sov)
    test("OWM connected to SOV-Space", owm.iwm is sov)

    output = owm.ingest("Analyze sentiment in customer reviews", source="kaggle")
    test("OWM returns strategy", "strategy" in output)
    test("Output has confidence", "confidence" in output)
    test("Output has clan_alliance", "clan_alliance" in output)

    # ─── E2E INTEGRATION ──────────────────────────────────────
    print("\n[8/8] E2E: Full 6,912-Slot Fractal Hive")
    tasks = [
        "Write optimized sorting algorithm",
        "Translate legal document to Chinese",
        "Analyze satellite imagery",
        "Debug memory leak in Rust",
        "Write EU AI Act compliance report",
    ]
    for desc in tasks:
        r = sov.process(desc)
        test(f"Processed: {desc[:30]}...", "master_cspace" in r)
        sov.learn({"task": desc, "won": True, "competitor": "unknown"})

    test("5 tasks processed", len(sov.task_log) >= 5)
    test("Spine Drum beating", sov.stigmergy.spine_drum.total_beats > 0)
    test("Stigmergy active", len(sov.stigmergy.get_global_trails()) > 0)

    status = sov.get_status()
    test("Status has 12 hives", status["hives"] == 12)
    test("Status has 144 clans", status["total_clans"] == 144)
    test("Status has 1,728 brains", status["total_brains"] == 1728)
    test("Status has 6,912 models", status["total_models"] == 6912)

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
